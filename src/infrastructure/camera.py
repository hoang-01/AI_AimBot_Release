import sys
import dxcam

class SmartCamera:
    def __init__(self, region):
        self.region = region  # (left, top, right, bottom)
        self.left, self.top, self.right, self.bottom = region
        self.width = self.right - self.left
        self.height = self.bottom - self.top
        self.dxcam_inst = None
        self.last_frame_ticks = 0 # Đánh dấu tick của khung hình đã xử lý gần nhất
        self._init_camera()

    def _init_camera(self):
        try:
            print(f"[CAM] Dang khoi tao DXCam GPU (ROI {self.width}x{self.height})...")
            # Tắt video_mode (để tránh tự nhân bản ảnh cũ khi màn hình không đổi)
            self.dxcam_inst = dxcam.create(device_idx=0, output_idx=0, output_color="BGR")
            self.dxcam_inst.start(region=self.region, target_fps=144, video_mode=False)
            print("[OK] Kich hoat DXCAM luong nen thanh cong (Khong nhan ban anh cu)!")
        except Exception as e:
            print(f"[ERR] DXCam khoi tao khong thanh cong: {e}")
            sys.exit(1)

    def get_frame(self):
        if self.dxcam_inst is not None:
            try:
                # Đọc tick của khung hình mới nhất trên GPU/DXCam
                current_ticks = self.dxcam_inst.latest_frame_ticks
                # Nếu tick trùng với khung hình trước -> Không có ảnh mới
                if current_ticks == self.last_frame_ticks:
                    return None
                
                # Cập nhật tick mới
                self.last_frame_ticks = current_ticks
                # Lấy frame mới nhất (chắc chắn có sẵn nên sẽ không block)
                return self.dxcam_inst.get_latest_frame()
            except Exception as e:
                print(f"[ERR] Loi doc frame DXCam: {e}")
        return None

    def release(self):
        if self.dxcam_inst is not None:
            try:
                self.dxcam_inst.stop()
                self.dxcam_inst.release()
                del self.dxcam_inst
            except Exception:
                pass
        print("[BYE] Da giai phong SmartCamera.")
