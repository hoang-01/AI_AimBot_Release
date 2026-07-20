import os
import sys
import time
import ctypes
import hid

# Cấu hình phần cứng CH552 Dongle
VID = 0x1209
PID = 0xC563
SECRET_KEY = "MASH_KEY_HARDWARE_LOCKED_2026"
OBFUSCATION_KEY = 0xAB

# Khai báo thông số AUG chuẩn hóa mới
# Mảng mẫu cơ sở (mẫu cơ bản của AUG)
# Mảng mẫu cơ sở (mẫu cơ bản của AUG đo trực tiếp từ biểu đồ súng trần)
# Giá trị gốc đã bao gồm lực giật mạnh viên đầu ở phần tử đầu tiên (47 so với trung bình 32-36)
AUG_BASE_PATTERN = [
    47, 32, 30, 32, 34, 36, 34, 34, 32, 34, 
    36, 34, 34, 34, 36, 34, 32, 34, 34, 36,
    34, 36, 34, 36, 34, 36, 34, 36, 34, 36,
    34, 36, 34, 36, 34, 36, 34, 36, 34, 36
]
FIRE_RATE_MS = 84  # Tốc độ bắn của AUG (khoảng thời gian trễ ms giữa các phát)

# Các thông số vật lý thực tế từ cấu hình mới của bạn
VERTICAL_RECOIL_BASE = 1.40         # Vertical Recoil cơ bản mới của AUG (1.40)
FIRST_SHOT_MULTIPLIER = 1.00        # Đặt là 1.0 vì lực giật viên đầu đã được nạp sẵn vào mảng thô phía trên
TOTAL_CLIMB_PX = 680                # Tổng độ cao leo mới (680 px)

# Hệ số bù trừ độ nhạy ngắm trong game
SENSITIVITY_MULTIPLIER = 1.5

# Hệ số nhân phụ kiện
MULTIPLIER_DOWN = 0.52              # Nằm bắn (down)
MULTIPLIER_THUMB = 0.85             # Tay cầm thumb (thumb)
MULTIPLIER_NO_SCOPE = 1.0           # Ống ngắm (no_scope)
MULTIPLIER_COMPENSATE = 0.784       # Đầu nòng compensator

# Thiết lập độ chính xác thời gian tối đa trên Windows (1ms)
try:
    ctypes.windll.winmm.timeBeginPeriod(1)
except Exception:
    pass

# Tính toán tổng hệ số phụ kiện
total_attachment_multiplier = (
    MULTIPLIER_DOWN * 
    MULTIPLIER_THUMB * 
    MULTIPLIER_NO_SCOPE * 
    MULTIPLIER_COMPENSATE
)

# Tính toán mảng độ giật thực tế sau khi áp dụng hệ số nhân chuẩn hóa và bù nhạy
scaled_pattern = []
for shot_idx, dy in enumerate(AUG_BASE_PATTERN):
    # Lực dọc cơ bản nhân với hệ số Vertical Recoil, hệ số phụ kiện và hệ số bù độ nhạy
    dy_scaled = dy * (VERTICAL_RECOIL_BASE / 1.33) * total_attachment_multiplier * SENSITIVITY_MULTIPLIER
    
    # Nhân thêm hệ số viên đầu (được đặt bằng 1.0 vì đã nạp sẵn vào mảng)
    dy_scaled *= FIRST_SHOT_MULTIPLIER
        
    scaled_pattern.append(max(1, int(dy_scaled)))

class TestCH552Mouse:
    def __init__(self):
        self.device = None
        self.connected = False
        self.connect()

    def connect(self):
        try:
            target_path = None
            for d in hid.enumerate(VID, PID):
                if d.get("usage_page") == 0xff00:
                    target_path = d.get("path")
                    break
            
            if target_path:
                self.device = hid.device()
                self.device.open_path(target_path)
                self.device.set_nonblocking(1)
                
                prod_str = self.device.get_product_string()
                if prod_str == SECRET_KEY:
                    self.connected = True
                    print(f"[OK] Da ket noi va xac thuc dongle CH552.")
                else:
                    print("[ERR] Khoa phan cung khong khop!")
                    sys.exit(1)
            else:
                print("[ERR] Khong tim thay thiet bi CH552 Raw HID.")
        except Exception as e:
            print(f"[ERR] Loi ket noi hid: {e}")

    def move(self, x, y):
        if not self.connected or not self.device:
            return
        try:
            # Ma hoa XOR truyen xuong firmware
            enc_x = (x & 0xFF) ^ OBFUSCATION_KEY
            enc_y = (y & 0xFF) ^ OBFUSCATION_KEY
            enc_b = 0 ^ OBFUSCATION_KEY
            
            cmd = [0x03, enc_x, enc_y, enc_b]
            self.device.write(cmd)
        except Exception as e:
            print(f"[ERR] Loi ghi command: {e}")
            self.connected = False

def main():
    print("=" * 60)
    print("               TEST NO-RECOIL AUG CH552 DONGLE")
    print("=" * 60)
    print(f"1. Vert Recoil Base:  {VERTICAL_RECOIL_BASE}")
    print(f"2. First Shot Mult:   {FIRST_SHOT_MULTIPLIER}")
    print(f"3. Tu the (Down):     {MULTIPLIER_DOWN}")
    print(f"4. Tay cam (Thumb):   {MULTIPLIER_THUMB}")
    print(f"5. Ong ngam (1x):     {MULTIPLIER_NO_SCOPE}")
    print(f"6. Dau nong (Comp):   {MULTIPLIER_COMPENSATE}")
    print(f"--> Tong he so phu kien: {total_attachment_multiplier:.6f}\n")
    
    print("Mảng độ giật gốc:")
    print(AUG_BASE_PATTERN)
    print("\nMảng độ giật thực tế sau khi tính (sẽ gửi cho chuột):")
    print(scaled_pattern)
    print("-" * 60)

    mouse = TestCH552Mouse()
    if not mouse.connected:
        print("[ERR] Chuot chua san sang. Ket thuc.")
        return

    # Cú pháp WinAPI kiểm tra trạng thái phím chuột
    get_async_key_state = ctypes.windll.user32.GetAsyncKeyState
    VK_LBUTTON = 0x01  # Chuột TRÁI
    VK_RBUTTON = 0x02  # Chuột PHẢI
    
    def is_shooting():
        left = (get_async_key_state(VK_LBUTTON) & 0x8000) != 0
        right = (get_async_key_state(VK_RBUTTON) & 0x8000) != 0
        return left and right

    # Các tham số hiệu năng mới từ cấu hình của bạn
    MOVE_INTERVAL_MS = 5.0          # Chu kỳ di chuyển bước chuột phụ (5ms)
    MAX_SPEED = 100.0              # Tốc độ di chuyển tối đa cho phép
    MAX_ACCEL_COUNT = 90            # Giới hạn gia tốc tăng tốc tối đa
    SLEEP_TIME_MS = 15.0            # Thời gian hồi nghỉ sau khi nhả chuột
    
    print("\n[READY] Nhấn giữ đồng thời CHUỘT TRÁI + CHUỘT PHẢI trong game để chạy thử một loạt sấy (40 viên) của AUG.")
    print("Nhấn Ctrl + C để thoát script test.")

    try:
        while True:
            if is_shooting():
                print("\n[RUNNING] Đang thực hiện sấy thử AUG...")
                
                ry = 0.0
                interrupted = False
                
                # Duyệt qua từng viên trong mảng
                for shot_idx, dy in enumerate(scaled_pattern):
                    if not is_shooting():
                        interrupted = True
                        break
                        
                    # Tính toán số lượng bước phụ dựa trên MOVE_INTERVAL_MS (5ms mỗi bước)
                    # Với FIRE_RATE_MS = 84ms, sẽ có: 84 / 5.0 = 16.8 bước -> 16 bước
                    sub_steps = int(FIRE_RATE_MS / MOVE_INTERVAL_MS)
                    sub_delay_ms = FIRE_RATE_MS / float(sub_steps)
                    
                    # Tính toán lực kéo trên mỗi bước 5ms
                    step_dy = dy / float(sub_steps)
                    
                    # Biến gia tốc (Acceleration tracker) giới hạn bởi MAX_ACCEL_COUNT
                    accel_counter = 0
                    
                    for step in range(sub_steps):
                        t_step_start = time.perf_counter()
                        
                        if not is_shooting():
                            interrupted = True
                            break
                        
                        # Áp dụng gia tốc dần dần cho bước di chuyển chuột
                        current_step_dy = step_dy
                        if accel_counter < MAX_ACCEL_COUNT:
                            # Tăng tốc mượt dần
                            factor = min(1.0, (accel_counter + 1) / float(MAX_ACCEL_COUNT))
                            current_step_dy *= factor
                            accel_counter += 1
                        
                        # Giới hạn tốc độ kéo tối đa (MAX_SPEED) để tránh rung lắc đột ngột
                        if current_step_dy > MAX_SPEED:
                            current_step_dy = MAX_SPEED
                            
                        ry += current_step_dy
                        my = int(ry)
                        
                        if my > 0:
                            mouse.move(0, my)
                            ry -= my
                            
                        # Vòng lặp ngủ hiệu năng cao căn chính xác chu kỳ MOVE_INTERVAL_MS (5ms)
                        target_time = t_step_start + (sub_delay_ms / 1000.0)
                        rem = target_time - time.perf_counter()
                        if rem > 0.002:
                            time.sleep(rem - 0.001)
                        while time.perf_counter() < target_time:
                            pass
                            
                    if interrupted:
                        break
                        
                if interrupted:
                    print("[INFO] Đã ngắt sấy ngay lập tức do nhả chuột.")
                    # Áp dụng sleepTime (15ms) để hồi súng sau khi nhả sấy
                    time.sleep(SLEEP_TIME_MS / 1000.0)
                else:
                    print("[DONE] Sấy xong toàn bộ 40 viên.")
            
            time.sleep(0.01)
            
    except KeyboardInterrupt:
        print("\n[STOP] Da dung chuong trinh test.")

if __name__ == "__main__":
    main()
