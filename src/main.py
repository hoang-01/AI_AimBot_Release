import os
import sys
import time
import gc
import threading
import ctypes
import numpy as np
import torch

# Thiết lập đường dẫn tương đối để Python có thể import các module trong thư mục src/
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from infrastructure.camera import SmartCamera
from infrastructure.mouse import CH552Mouse
from infrastructure.inputs import KeyTracker
from processing.ai_engine import AIEngine
from processing.ui_tracker import UIStateTracker
from control.recoil_db import RecoilProfileManager
from control.target_select import TargetSelector
from control.pid_engine import PIDEngine
from gui.config import ConfigManager

class SharedState:
    def __init__(self):
        self._lock = threading.Lock()
        self.latest_frame = None
        self.weapon_id = "default"
        self.stance = "standing"
        self.ammo_active = True
        self.attachments = []
        self.scope_zoom = 1.0

    def update_frame(self, frame):
        with self._lock:
            self.latest_frame = frame

    def get_latest_full_frame(self):
        with self._lock:
            return self.latest_frame

    def update_ui_state(self, weapon_id, stance, ammo_active, attachments=None, scope_zoom=1.0):
        with self._lock:
            self.weapon_id = weapon_id
            self.stance = stance
            self.ammo_active = ammo_active
            if attachments is not None:
                self.attachments = attachments
            self.scope_zoom = scope_zoom

    def get_ui_state(self):
        with self._lock:
            return self.weapon_id, self.stance, self.ammo_active, self.attachments, self.scope_zoom

def setup_dll_paths():
    """Tự động đăng ký đường dẫn CUDA/TensorRT DLL."""
    try:
        cwd = os.getcwd()
        if os.path.exists(cwd):
            os.add_dll_directory(cwd)
        for path in sys.path:
            if not os.path.exists(path):
                continue
            torch_lib = os.path.join(path, "torch", "lib")
            if os.path.exists(torch_lib):
                os.add_dll_directory(torch_lib)
            trt_lib = os.path.join(path, "tensorrt_libs")
            if os.path.exists(trt_lib):
                os.add_dll_directory(trt_lib)
    except Exception as e:
        print(f"[WARN DLL]: {e}")

def main():
    setup_dll_paths()
    
    # 1. Nạp cấu hình
    cfg = ConfigManager()
    
    # Thiết lập độ ưu tiên tiến trình HIGH
    try:
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x00000080)
        ctypes.windll.winmm.timeBeginPeriod(1)
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        print("[OK] Toi uu hoa Window Class va Period: HIGH")
    except Exception as e:
        print(f"[WARN] Khong the thiet lap do uu tien: {e}")

    # 2. Khởi tạo hạ tầng
    mouse = CH552Mouse(
        vid=cfg.get("hardware", "vid"),
        pid=cfg.get("hardware", "pid"),
        secret_key=cfg.get("hardware", "secret_key")
    )
    if not mouse.connected:
        print("[WARN] Khong tim thấy chuot HID CH552. Vui long cam thiet bi.")
        sys.exit(1)
        
    keys = KeyTracker()

    # 3. Tính toán toạ độ Camera ROI
    screen_w = ctypes.windll.user32.GetSystemMetrics(0)
    screen_h = ctypes.windll.user32.GetSystemMetrics(1)
    fov_w = cfg.get("camera", "fov_width")
    fov_h = cfg.get("camera", "fov_height")
    
    left = (screen_w - fov_w) // 2
    top = (screen_h - fov_h) // 2
    right = left + fov_w
    bottom = top + fov_h
    camera = SmartCamera(region=(left, top, right, bottom))

    # 4. Khởi tạo Processing Engine
    ai = AIEngine(
        model_path=cfg.get("detection", "model_path"),
        conf_threshold=cfg.get("detection", "conf_threshold")
    )
    
    shared_state = SharedState()
    
    # Kích hoạt luồng quét UI phụ (10 FPS)
    ui_tracker = UIStateTracker(shared_state)
    # Hiệu chuẩn ROI mẫu góc dưới bên phải màn hình (Ví dụ toạ độ súng/đạn)
    ui_tracker.set_roi("weapon", (screen_w - 250, screen_h - 120, screen_w - 50, screen_h - 50))
    ui_tracker.set_roi("stance", (screen_w - 300, screen_h - 120, screen_w - 250, screen_h - 70))
    ui_tracker.set_roi("ammo", (screen_w - 150, screen_h - 80, screen_w - 50, screen_h - 50))
    ui_tracker.start()

    # 5. Khởi tạo Logic Nghiệp Vụ
    # Vùng giới hạn bám 150x150 ở trung tâm FOV
    limit_w = cfg.get("camera", "lock_region_w")
    limit_h = cfg.get("camera", "lock_region_h")
    limit_min = (fov_w - limit_w) / 2.0
    limit_max = fov_w - limit_min
    
    selector = TargetSelector(fov_w, fov_h, limit_min, limit_max)
    
    recoil_db = RecoilProfileManager()
    
    pid = PIDEngine(
        kp=cfg.get("pid", "kp"),
        kd=cfg.get("pid", "kd"),
        smoothing=cfg.get("pid", "smoothing"),
        deadzone_x=cfg.get("pid", "deadzone_x"),
        brake_force=cfg.get("pid", "brake_force"),
        brake_radius=cfg.get("pid", "brake_radius")
    )

    # 6. Vòng lặp chính điều khiển (Aim + No-Recoil 144 FPS)
    TARGET_FPS = cfg.get("detection", "target_fps")
    FRAME_TIME = 1.0 / TARGET_FPS
    cx, cy = fov_w / 2.0, fov_h / 2.0
    
    macro_enabled = cfg.get("macro", "enabled")
    aim_key = cfg.get("macro", "aim_key")
    fire_key = cfg.get("macro", "fire_key")
    shift_key = cfg.get("macro", "shift_key")
    key_off = cfg.get("macro", "key_off")
    key_on = cfg.get("macro", "key_on")
    
    key_o_prev = False
    key_p_prev = False
    prev_aim_active = False
    left_fire_start_time = 0.0
    
    gc.disable()
    print("\n[SYSTEM] HE THONG DANG HOAT DONG! San sang bám AI va tu dong bù giat.")
    
    try:
        with torch.inference_mode():
            while True:
                t_loop_start = time.perf_counter()
                
                # Kiểm tra phím nóng bật/tắt Macro (O/P)
                key_o = keys.is_key_pressed(key_off)
                key_p = keys.is_key_pressed(key_on)
                if key_o and not key_o_prev:
                    macro_enabled = False
                    print("[MACRO] [OFF] Da tat Macro.")
                key_o_prev = key_o
                
                if key_p and not key_p_prev:
                    macro_enabled = True
                    print("[MACRO] [ON] Da bat lai Macro.")
                key_p_prev = key_p

                # Kiểm tra phím điều hướng ngắm bắn
                right_click = keys.is_key_pressed(aim_key)
                left_click = keys.is_key_pressed(fire_key)
                left_shift = keys.is_key_pressed(shift_key)
                
                aim_active = keys.is_aim_active(macro_enabled, aim_key, fire_key, shift_key)
                
                # Đếm thời gian sấy súng
                if left_click:
                    if left_fire_start_time == 0.0:
                        left_fire_start_time = time.perf_counter()
                    left_click_hold_time = time.perf_counter() - left_fire_start_time
                else:
                    left_fire_start_time = 0.0
                    left_click_hold_time = 0.0

                if not aim_active:
                    pid.reset_state()
                    if prev_aim_active:
                        gc.enable()
                        gc.collect()
                        gc.disable()
                    prev_aim_active = False
                    time.sleep(0.005)
                    continue

                prev_aim_active = True

                # Chụp khung hình mới
                frame = camera.get_frame()
                if frame is None:
                    time.sleep(0.001)
                    continue
                
                # Cập nhật frame cho luồng phụ UI tracker quét
                shared_state.update_frame(frame)

                # Chạy AI phát hiện vật thể
                boxes, classes = ai.detect(frame)
                
                # Lấy trạng thái UI đã quét (Weapon, Stance, Ammo)
                weapon_id, stance, ammo_active, attachments, scope_zoom = shared_state.get_ui_state()

                # Xác định mục tiêu bắn (Đầu/Thân)
                target = selector.select_target(boxes, classes, right_click, left_click_hold_time, left_shift)

                # Tính toán lực ghì giật súng (No-recoil)
                recoil_dx, recoil_dy = 0, 0
                if left_click and ammo_active and weapon_id != "unarmed":
                    # Lấy thông tin súng hiện tại
                    gun_info = recoil_db.db.get(weapon_id, recoil_db.db["default"])
                    rpm = gun_info["rpm"]
                    
                    # Cập nhật đếm viên đạn theo thời gian trôi qua
                    pid.update_shot_index(rpm)
                    
                    # Lấy độ giật tương ứng
                    recoil_dx, recoil_dy = recoil_db.get_recoil_delta(
                        weapon_id=weapon_id,
                        shot_index=pid.shot_index,
                        stance=stance,
                        attachments=attachments,
                        scope_zoom=scope_zoom
                    )

                # Tính toán vận tốc chuột tích hợp PID ngắm và No-recoil
                mx, my = pid.calculate_move(target, cx, cy, recoil_dx, recoil_dy)

                # Gửi chuyển động vật lý đến cổng HID
                if mx != 0 or my != 0:
                    mouse.move(mx, my)

                # Khóa FPS
                elapsed = time.perf_counter() - t_loop_start
                rem = FRAME_TIME - elapsed
                if rem > 0.0005:
                    time.sleep(rem - 0.0002)
                while (time.perf_counter() - t_loop_start) < FRAME_TIME:
                    time.sleep(0.0)

    except KeyboardInterrupt:
        print("\n[STOP] Dang dung he thong...")
    finally:
        gc.enable()
        camera.release()
        mouse.close()
        ui_tracker.running = False
        print("[BYE] Giai phong thanh cong.")
        os._exit(0)

if __name__ == "__main__":
    main()
