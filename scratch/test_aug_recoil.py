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

# Khai báo thông số AUG của bạn
AUG_BASE_PATTERN = [
    26, 45, 25, 25, 32, 36, 36, 36, 45, 45, 
    52, 52, 52, 52, 52, 56, 56, 56, 56, 56, 
    58, 58, 58, 58, 56, 56, 56, 56, 56, 56, 
    57, 57, 57, 57, 57, 60, 60, 60, 58, 58
]
FIRE_RATE_MS = 84  # Tốc độ bắn của AUG (khoảng thời gian trễ ms giữa các phát)

# Hệ số nhân phụ kiện
MULTIPLIER_HOLD = 1.33
MULTIPLIER_DOWN = 0.52              # Nằm bắn (down)
MULTIPLIER_THUMB = 0.85             # Tay cầm thumb (thumb)
MULTIPLIER_NO_SCOPE = 1.0           # Ống ngắm (no_scope)
MULTIPLIER_COMPENSATE = 0.784       # Đầu nòng compensator

# Tính toán tổng hệ số nhân dọc (Vertical Multiplier)
total_vertical_multiplier = (
    MULTIPLIER_HOLD * 
    MULTIPLIER_DOWN * 
    MULTIPLIER_THUMB * 
    MULTIPLIER_NO_SCOPE * 
    MULTIPLIER_COMPENSATE
)

# Tính toán mảng độ giật thực tế sau khi áp dụng hệ số nhân
# Công thức: dy_thực_tế = dy_gốc * total_vertical_multiplier
scaled_pattern = [int(dy * total_vertical_multiplier) for dy in AUG_BASE_PATTERN]

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
    print(f"1. He so Hold:        {MULTIPLIER_HOLD}")
    print(f"2. Tu the (Down):     {MULTIPLIER_DOWN}")
    print(f"3. Tay cam (Thumb):   {MULTIPLIER_THUMB}")
    print(f"4. Ong ngam (1x):     {MULTIPLIER_NO_SCOPE}")
    print(f"5. Dau nong (Comp):   {MULTIPLIER_COMPENSATE}")
    print(f"--> Tong he so nhan:  {total_vertical_multiplier:.6f}\n")
    
    print("Mảng độ giật gốc:")
    print(AUG_BASE_PATTERN)
    print("\nMảng độ giật thực tế sau khi tính (sẽ gửi cho chuột):")
    print(scaled_pattern)
    print("-" * 60)

    mouse = TestCH552Mouse()
    if not mouse.connected:
        print("[ERR] Chuot chua san sang. Ket thuc.")
        return

    # Cu phap WinAPI kiem tra phim F4
    get_async_key_state = ctypes.windll.user32.GetAsyncKeyState
    KEY_F4 = 0x73  # Phim F4 de chay test
    
    print("\n[READY] Nhan F4 trong game de chay thu mot loat say say (40 vien) cua AUG.")
    print("Nhan Ctrl + C de thoat script test.")

    try:
        while True:
            # Neu phim F4 duoc nhan xuong
            if (get_async_key_state(KEY_F4) & 0x8000) != 0:
                print("\n[RUNNING] Dang thuc hien say thu AUG...")
                
                # Duyet qua tung vien trong mang
                for shot_idx, dy in enumerate(scaled_pattern):
                    t_shot_start = time.perf_counter()
                    
                    if dy > 0:
                        # Kéo chuột đi xuống (Y = dy, X = 0)
                        # Luu y: dy trong file patterm.json la so nguyen duong tuong ung keo chuot xuong duoi
                        mouse.move(0, dy)
                    
                    # Tinh toan thoi gian nghi giua cac vien de khong lam lech chu ky sấy
                    elapsed = (time.perf_counter() - t_shot_start) * 1000.0
                    sleep_time_ms = FIRE_RATE_MS - elapsed
                    if sleep_time_ms > 0:
                        time.sleep(sleep_time_ms / 1000.0)
                        
                print("[DONE] Say xong 40 vien. Cho phim F4 tiep theo.")
                time.sleep(0.5)  # Tranh trigger lap lai khi bam phim
            
            time.sleep(0.01)
            
    except KeyboardInterrupt:
        print("\n[STOP] Da dung chuong trinh test.")

if __name__ == "__main__":
    main()
