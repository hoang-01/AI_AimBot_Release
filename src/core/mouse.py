import hid
import time
import math
import ctypes
import numpy as np
import queue
from src.utils.logger import Logger

VID = 0x1209
PID = 0xC563 

class ArduinoHID:
    def __init__(self):
        self.device = None
        self.connected = False
        self.current_buttons = 0 
        self.connect()
        
    def connect(self):
        try:
            if self.device: self.device.close()
            
            target_path = None
            devices = hid.enumerate(VID, PID)
            for d in devices:
                if d.get('usage_page') == 0xff00:
                    target_path = d.get('path')
                    break
            
            if target_path:
                self.device = hid.device()
                self.device.open_path(target_path)
                self.device.set_nonblocking(1)
                self.connected = True
                Logger.success(f"HID Device Connected: {VID:04X}:{PID:04X}")
            else:
                self.connected = False
                # Logger.warning(f"Waiting for Device {VID:04X}:{PID:04X}...")
                
        except Exception as e:
            self.connected = False
            # Logger.error(f"Connect Error: {e}")

    def move(self, x, y):
        if not self.connected: 
            self.connect()
            return
        
        try:
            OBFUSCATION_KEY = 0xAB
            enc_x = (int(x) & 0xFF) ^ OBFUSCATION_KEY
            enc_y = (int(y) & 0xFF) ^ OBFUSCATION_KEY
            enc_b = self.current_buttons ^ OBFUSCATION_KEY
            cmd = [0x03, enc_x, enc_y, enc_b]
            self.device.write(cmd)
        except Exception as e:
            self.connected = False
            Logger.error(f"HID Write Error: {e}")

    def fire(self, state):
        if not self.connected: return
        try:
            OBFUSCATION_KEY = 0xAB
            self.current_buttons = 1 if state else 0
            enc_b = self.current_buttons ^ OBFUSCATION_KEY
            cmd = [0x03, 0 ^ OBFUSCATION_KEY, 0 ^ OBFUSCATION_KEY, enc_b]
            self.device.write(cmd)
            return 1
        except Exception as e:
            Logger.error(f"HID Fire Error: {e}")
            self.connected = False
            return 0

class MouseController:
    def __init__(self, cfg, result_queue, fire_command_queue, shared_state):
        self.cfg = cfg
        self.result_queue = result_queue
        self.fire_queue = fire_command_queue
        self.state = shared_state
        self.is_running = False
        self.arduino = ArduinoHID()
        
        # Internal State
        self.px, self.py = 0, 0
        self.rx, self.ry = 0.0, 0.0
        self.sx, self.sy = 0, 0 # Smoothing accumulators
        self.rcs_last_x, self.rcs_last_y = 0.0, 0.0
        self.fire_start_time = 0

    def start(self):
        self.is_running = True
        self._loop()
        
    def _fire_loop(self):
        """Dedicated fire loop to prevent blocking mouse movement"""
        Logger.info("🔫 [THREAD] Auto-Fire Engine Active...")
        last_fire_time = 0
        while self.is_running:
            try:
                state = self.fire_queue.get(timeout=1)
                if state:
                    now = time.perf_counter()
                    if (now - last_fire_time) >= self.cfg.TRIGGER_DELAY:
                        if self.arduino.connected:
                            Logger.info("🔥 [FIRE] Mouse Down")
                            self.arduino.fire(True)
                            time.sleep(0.050) 
                            self.arduino.fire(False)
                            Logger.info("❄️ [FIRE] Mouse Up")
                            time.sleep(0.050) 
                        last_fire_time = now
            except queue.Empty:
                continue
            except Exception as e:
                Logger.error(f"FIRE THREAD ERROR: {e}")
                time.sleep(0.01)

    def get_pattern_offset(self, pattern, hold_time):
        if not pattern: return 0.0, 0.0
        for i in range(len(pattern) - 1):
            p1, p2 = pattern[i], pattern[i+1]
            if p1[0] <= hold_time <= p2[0]:
                ratio = (hold_time - p1[0]) / (p2[0] - p1[0])
                return p1[1] + (p2[1] - p1[1]) * ratio, p1[2] + (p2[2] - p1[2]) * ratio
        return pattern[-1][1], pattern[-1][2]

    def _loop(self):
        Logger.info("🖱️ [THREAD] Mouse Engine: Hybrid System Online...")
        
        cx, cy = self.cfg.FOV_WIDTH / 2.0, self.cfg.FOV_HEIGHT / 2.0
        delay_s = 1.0 / self.cfg.POLLING_RATE_HZ
        
        while self.is_running:
            t_loop_start = time.perf_counter()
            try:
                # 1. Connection Check
                if not self.arduino.connected:
                    self.arduino.connect()
                    if not self.arduino.connected: 
                        time.sleep(1)
                        continue

                # 2. Key Polling
                aim_on = (ctypes.windll.user32.GetAsyncKeyState(self.cfg.AIM_KEY) & 0x8000)
                click_on = (ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000)
                fire_on = (ctypes.windll.user32.GetAsyncKeyState(self.cfg.AUTO_FIRE_KEY) & 0x8000)
                reflex_on = (ctypes.windll.user32.GetAsyncKeyState(self.cfg.REFLEX_KEY) & 0x8000)
                active_trigger = (aim_on or fire_on or reflex_on)
                
                self.state["active"] = active_trigger

                # 3. RCS / AIM OFFSET
                rcs_vx, rcs_vy, aim_ox, aim_oy = 0.0, 0.0, 0.0, 0.0
                if click_on:
                    if self.fire_start_time == 0: self.fire_start_time = time.perf_counter()
                    
                    # Apply Rate Multiplier (Speeds up or slows down the pattern progression)
                    hold_t_raw = time.perf_counter() - self.fire_start_time
                    hold_t = hold_t_raw * getattr(self.cfg, "RCS_TIMING_VAL", 1.0)
                    
                    # Get Base Offsets
                    rcs_x, rcs_y = self.get_pattern_offset(self.cfg.RCS_PATTERN, hold_t)
                    aim_ox, aim_oy = self.get_pattern_offset(self.cfg.AIM_PATTERN, hold_t)
                    
                    # Apply Strength Multiplier (Strengthens or weakens the Y-pull)
                    strength = getattr(self.cfg, "RCS_STRENGTH_VAL", 1.0)
                    rcs_y *= strength
                    aim_oy *= strength
                    
                    rcs_vx, rcs_vy = rcs_x - self.rcs_last_x, rcs_y - self.rcs_last_y
                else: 
                    self.fire_start_time, self.rcs_last_x, self.rcs_last_y = 0, 0.0, 0.0

                # 4. AI DATA
                ai_vx, ai_vy = 0.0, 0.0
                should_fire = False
                
                try: data = self.result_queue.get(timeout=0.0001)
                except: data = None

                if data and (aim_on or fire_on):
                    tx, ty, tw, th, cls_id = data  # Now includes class_id from inference
                    # SMOOTHING Logic
                    self.sx = self.sx * self.cfg.SMOOTHING + tx * (1 - self.cfg.SMOOTHING) if self.sx != 0 else tx
                    self.sy = self.sy * self.cfg.SMOOTHING + ty * (1 - self.cfg.SMOOTHING) if self.sy != 0 else ty
                    
                    ex, ey = (self.sx + aim_ox) - cx, (self.sy + aim_oy) - cy
                    ai_vx = (self.cfg.PID_KP * ex + self.cfg.PID_KD * (ex - self.px))
                    ai_vy = (self.cfg.PID_KP * ey + self.cfg.PID_KD * (ey - self.py))
                    self.px, self.py = ex, ey
                    
                    dist = np.sqrt(ex**2 + ey**2)
                    # BRAKING LOGIC (Fixed)
                    brake_radius = 40.0 # Pixels from head to start braking
                    if self.cfg.MOUSE_BRAKE_FORCE > 0.01 and dist <= brake_radius:
                         # Calculate scale: 0.0 (at center) to 1.0 (at radius)
                         target_scale = max(0.1, dist / brake_radius)
                         # Interpolate based on Brake Force: 0.0 (No Effect) -> 1.0 (Full Target Scale)
                         # Scale = 1.0 * (1 - Force) + Target * Force
                         factor = 1.0 - (self.cfg.MOUSE_BRAKE_FORCE * (1.0 - target_scale))
                         
                         ai_vx *= factor
                         ai_vy *= factor
                    
                    # Anti-overshoot
                    move_mag = np.sqrt(ai_vx**2 + ai_vy**2)
                    if move_mag > dist and dist > 0:
                        ai_vx = (ai_vx / move_mag) * dist
                        ai_vy = (ai_vy / move_mag) * dist

                    if abs(ex) < self.cfg.DEADZONE_X and abs(ey) < self.cfg.DEADZONE_Y: 
                        ai_vx, ai_vy = 0, 0
                    
                    # TRIGGER ZONE
                    if fire_on:
                        tw_z, th_z = tw * self.cfg.TRIGGER_ZONE, th * self.cfg.TRIGGER_ZONE
                        if abs(tx - cx) <= tw_z/2 and abs(ty - cy) <= th_z/2:
                            should_fire = True
                else:
                    self.sx, self.sy, self.px, self.py = 0, 0, 0, 0

                # 5. REFLEX TRIGGER
                if reflex_on and self.state.get("reflex_fire", False):
                    should_fire = True

                # 6. MOUSE EXECUTION
                if active_trigger:
                    self.rx += (rcs_vx + ai_vx); self.ry += (rcs_vy + ai_vy)
                    mx, my = int(self.rx), int(self.ry)
                    if mx != 0 or my != 0:
                        mx = max(-127, min(127, mx))
                        my = max(-127, min(127, my))
                        if self.arduino.connected: 
                            self.arduino.move(mx, my)
                            self.rx -= mx; self.ry -= my
                        if click_on: 
                            self.rcs_last_x, self.rcs_last_y = rcs_x, rcs_y # Fixed from self.rcs_x (error in orig logic?) -> No, local rcs_x

                # 7. FIRE EXECUTION
                if should_fire:
                    if self.fire_queue.empty():
                        self.fire_queue.put(True)

                # 8. PRECISION LOOP
                elapsed = time.perf_counter() - t_loop_start
                rem = delay_s - elapsed
                if rem > 0.0005: time.sleep(rem - 0.0003)
                while (time.perf_counter() - t_loop_start) < delay_s: pass

            except Exception as e:
                # Logger.error(f"Mouse Loop Error: {e}")
                time.sleep(0.01)

    def stop(self):
        self.is_running = False
