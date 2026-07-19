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
AUG_BASE_PATTERN = [
    28, 45, 29, 30, 32, 36, 36, 36, 45, 45, 
    52, 52, 52, 52, 52, 56, 56, 56, 56, 56, 
    56, 56, 56, 56, 56, 56, 56, 56, 56, 56, 
    57, 57, 57, 57, 57, 56, 56, 56, 56, 56
]
FIRE_RATE_MS = 84  # Tốc độ bắn của AUG (khoảng thời gian trễ ms giữa các phát)

# Các thông số vật lý thực tế từ cấu hình mới của bạn
VERTICAL_RECOIL_BASE = 1.40         # Vertical Recoil cơ bản mới của AUG (1.40)
FIRST_SHOT_MULTIPLIER = 1.50        # Hệ số giật viên đầu tiên (1.50)
TOTAL_CLIMB_PX = 680                # Tổng độ cao leo mới (680 px)

# Hệ số bù trừ độ nhạy ngắm trong game (Tăng lên nếu ghì chưa đủ, giảm đi nếu ghì quá đà xuống đất)
# Mặc định thiết lập 1.20 để phù hợp với độ nhạy chuột của bạn
SENSITIVITY_MULTIPLIER = 1.20

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
    
    # Phát bắn thứ 2 (viên nảy đầu tiên thực tế từ phát 1 sang 2) áp dụng First Shot Multiplier (1.50)
    if shot_idx == 1:
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

    print("\n[READY] Nhấn giữ đồng thời CHUỘT TRÁI + CHUỘT PHẢI trong game để chạy thử một loạt sấy (40 viên) của AUG.")
    print("Nhấn Ctrl + C để thoát script test.")

    try:
        while True:
            if is_shooting():
                print("\n[RUNNING] Đang thực hiện sấy thử AUG...")
                
                # Bộ tích lũy sai số float để chia nhỏ chuyển động
                ry = 0.0
                interrupted = False
                
                # Duyệt qua từng viên trong mảng
                for shot_idx, dy in enumerate(scaled_pattern):
                    # Kiểm tra ngắt trước khi nạp viên mới
                    if not is_shooting():
                        interrupted = True
                        break
                        
                    # Băm nhỏ phát bắn thành 5 bước phụ để tăng độ mượt ghì chuột
                    SUB_STEPS = 5
                    sub_delay_ms = FIRE_RATE_MS / SUB_STEPS  # 84 / 5 = 16.8 ms
                    step_dy = dy / float(SUB_STEPS)
                    
                    for step in range(SUB_STEPS):
                        t_step_start = time.perf_counter()
                        
                        # Kiểm tra ngắt ngay trong từng bước phụ (phản hồi trễ tối đa chỉ 16ms)
                        if not is_shooting():
                            interrupted = True
                            break
                        
                        # Tích lũy dịch chuyển chuột dọc
                        ry += step_dy
                        my = int(ry)
                        
                        if my > 0:
                            mouse.move(0, my)
                            ry -= my  # Khấu trừ phần chẵn đã dịch chuyển
                            
                        # Vòng lặp ngủ độ chính xác cao (Spin-wait loop) để đảm bảo thời gian bước chính xác tuyệt đối
                        target_time = t_step_start + (sub_delay_ms / 1000.0)
                        
                        # Cho phép ngủ ngắn nếu thời gian chờ còn dài (>2ms) để giảm tải CPU
                        rem = target_time - time.perf_counter()
                        if rem > 0.002:
                            time.sleep(rem - 0.001)
                            
                        # Vòng lặp bận rỗng cực ngắn để căn chính xác mili-giây cuối
                        while time.perf_counter() < target_time:
                            pass
                            
                    if interrupted:
                        break
                        
                if interrupted:
                    print("[INFO] Đã ngắt sấy ngay lập tức do nhả chuột.")
                else:
                    print("[DONE] Sấy xong toàn bộ 40 viên.")
            
            time.sleep(0.01)
            
    except KeyboardInterrupt:
        print("\n[STOP] Da dung chuong trinh test.")

if __name__ == "__main__":
    main()
