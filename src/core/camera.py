import dxcam
import time
import ctypes
import queue
from src.utils.logger import Logger

class DXCamera:
    def __init__(self, cfg, capture_queue, reflex_queue):
        self.cfg = cfg
        self.capture_queue = capture_queue
        self.reflex_queue = reflex_queue
        self.camera = None
        self.is_running = False
        
        self._init_dxcam()

    def _init_dxcam(self):
        Logger.info("🎬 [THREAD] DXCam Turbo: Initializing...")
        try:
            self.camera = dxcam.create(device_idx=0, output_idx=0, output_color="BGR")
        except Exception as e:
            Logger.error(f"Failed to create DXCam: {e}")
            self.camera = None

    def start(self):
        if not self.camera: return
        self.is_running = True
        
        # Calculate ROI
        screen_w, screen_h = ctypes.windll.user32.GetSystemMetrics(0), ctypes.windll.user32.GetSystemMetrics(1)
        L, T = (screen_w - self.cfg.FOV_WIDTH)//2, (screen_h - self.cfg.FOV_HEIGHT)//2
        
        Logger.info(f"📷 ROI: {self.cfg.FOV_WIDTH}x{self.cfg.FOV_HEIGHT} at ({L},{T}) on Screen {screen_w}x{screen_h}")
        
        # Start DXCam video mode
        self.camera.start(region=(L, T, L + self.cfg.FOV_WIDTH, T + self.cfg.FOV_HEIGHT), 
                          target_fps=self.cfg.MAX_INFERENCE_FPS, 
                          video_mode=True)
        
        self._loop()

    def _loop(self):
        cx, cy = self.cfg.FOV_WIDTH // 2, self.cfg.FOV_HEIGHT // 2
        rw = self.cfg.REFLEX_ZONE_W // 2
        rh = self.cfg.REFLEX_ZONE_H // 2
        
        while self.is_running:
            try:
                # Key Polling (Directly using WinAPI for speed in this critical loop)
                # Note: Ideally this should be passed in or handled via event flags, but direct polling is fast.
                aim_on = (ctypes.windll.user32.GetAsyncKeyState(self.cfg.AIM_KEY) & 0x8000)
                fire_on = (ctypes.windll.user32.GetAsyncKeyState(self.cfg.AUTO_FIRE_KEY) & 0x8000)
                reflex_on = (ctypes.windll.user32.GetAsyncKeyState(self.cfg.REFLEX_KEY) & 0x8000)
                
                if aim_on or fire_on or reflex_on:
                    img = self.camera.get_latest_frame()
                    if img is not None:
                        if aim_on or fire_on:
                            if self.capture_queue.full(): self.capture_queue.get_nowait()
                            self.capture_queue.put(img)
                        
                        if reflex_on:
                            # REFLEX ROI Dynamic inside the captured frame
                            # IMPORTANT: Check bounds!
                            y1, y2 = max(0, cy-rh), min(self.cfg.FOV_HEIGHT, cy+rh+1)
                            x1, x2 = max(0, cx-rw), min(self.cfg.FOV_WIDTH, cx+rw+1)
                            
                            reflex_img = img[y1:y2, x1:x2]
                            if self.reflex_queue.full(): self.reflex_queue.get_nowait()
                            self.reflex_queue.put(reflex_img)
                    else:
                        pass # No frame yet
                else:
                    time.sleep(0.005) # Sleep when inactive
            except Exception as e:
                Logger.error(f"Camera Loop Error: {e}")
                time.sleep(1)

    def stop(self):
        self.is_running = False
        if self.camera:
            self.camera.stop()
