import sys
import time
import queue
import threading
import hid

class CH552Mouse:
    def __init__(self, vid=0x1209, pid=0xC563, secret_key="MASH_KEY_HARDWARE_LOCKED_2026"):
        self.vid = vid
        self.pid = pid
        self.secret_key = secret_key
        self.device = None
        self.connected = False
        self.cmd_queue = queue.Queue(maxsize=1)
        self.writer_thread = None
        self.is_running = False
        self.connect()

    def connect(self):
        try:
            if self.device:
                self.device.close()
            
            # Tìm cổng USBRaw (usage_page = 0xff00)
            target_path = None
            for d in hid.enumerate(self.vid, self.pid):
                if d.get("usage_page") == 0xff00:
                    target_path = d.get("path")
                    break
            
            if target_path:
                self.device = hid.device()
                self.device.open_path(target_path)
                self.device.set_nonblocking(1)
                
                # Xác thực bảo mật khóa phần cứng
                prod_str = self.device.get_product_string()
                if prod_str == self.secret_key:
                    self.connected = True
                    print(f"[OK] Da ket noi phan cung gia lap chuot CH552 ({self.vid:04X}:{self.pid:04X})")
                    if not self.is_running:
                        self.is_running = True
                        self.writer_thread = threading.Thread(target=self._write_loop, daemon=True)
                        self.writer_thread.start()
                else:
                    print("[STOP] Khoa bao mat phan cung khong khop!")
                    sys.exit(1)
            else:
                self.connected = False
        except Exception as e:
            self.connected = False
            print(f"[ERR] Loi ket noi chuot HID: {e}")

    def _write_loop(self):
        OBFUSCATION_KEY = 0xAB
        while self.is_running:
            try:
                # Chờ lệnh mới từ hàng đợi (block tối đa 0.5 giây nếu không có hoạt động)
                x, y = self.cmd_queue.get(timeout=0.5)
                if not self.connected:
                    continue
                # Mã hóa XOR 0xAB để giải mã chính xác trong Firmware CH552
                enc_x = (x & 0xFF) ^ OBFUSCATION_KEY
                enc_y = (y & 0xFF) ^ OBFUSCATION_KEY
                enc_b = 0 ^ OBFUSCATION_KEY
                
                cmd = [0x03, enc_x, enc_y, enc_b]
                self.device.write(cmd)
            except queue.Empty:
                continue
            except Exception as e:
                self.connected = False
                print(f"[ERR] Loi ghi HID trong luong phu: {e}")
                time.sleep(0.1)

    def move(self, x, y):
        if not self.connected:
            self.connect()
            return
        
        # Chỉ giữ lệnh mới nhất để tránh trễ dồn (Lag buildup)
        if self.cmd_queue.full():
            try:
                self.cmd_queue.get_nowait()
            except queue.Empty:
                pass
        self.cmd_queue.put((x, y))

    def close(self):
        self.is_running = False
        if self.device:
            self.device.close()
