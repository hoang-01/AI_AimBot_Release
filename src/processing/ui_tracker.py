import os
import time
import threading
import cv2
import numpy as np

class UIStateTracker(threading.Thread):
    def __init__(self, shared_state, templates_dir="templates"):
        super().__init__(daemon=True)
        self.shared_state = shared_state
        self.templates_dir = templates_dir
        self.running = True
        self.templates = {
            "weapons": {},
            "stances": {},
            "attachments": {}
        }
        self.roi_coordinates = {
            "weapon": (0, 0, 100, 100),       # Toạ độ (left, top, right, bottom) mẫu, cần hiệu chuẩn
            "stance": (0, 0, 50, 50),
            "ammo": (0, 0, 80, 40),
            "attachments": []                 # Danh sách các toạ độ slot phụ kiện
        }
        self._load_templates()

    def _load_templates(self):
        """Tải toàn bộ tệp ảnh mẫu ở dạng ảnh xám"""
        for category in ["weapons", "stances", "attachments"]:
            dir_path = os.path.join(self.templates_dir, category)
            if not os.path.exists(dir_path):
                continue
            for file_name in os.listdir(dir_path):
                if file_name.lower().endswith(('.png', '.jpg', '.jpeg')):
                    name = os.path.splitext(file_name)[0]
                    file_path = os.path.join(dir_path, file_name)
                    # Đọc ở dạng ảnh xám (0)
                    img = cv2.imread(file_path, 0)
                    if img is not None:
                        self.templates[category][name] = img
        print(f"[UI] Da tai {sum(len(v) for v in self.templates.values())} anh mau UI.")

    def set_roi(self, category, coords):
        """Cập nhật toạ độ ROI sau khi hiệu chuẩn"""
        self.roi_coordinates[category] = coords

    def crop_and_preprocess(self, frame, coords):
        """Cắt ảnh theo toạ độ và chuyển đổi sang ảnh xám"""
        left, top, right, bottom = coords
        # Giới hạn an toàn
        h, w = frame.shape[:2]
        left, right = max(0, left), min(w, right)
        top, bottom = max(0, top), min(h, bottom)
        
        crop = frame[top:bottom, left:right]
        if crop.size == 0:
            return None
        return cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

    def match_template(self, crop_gray, category, threshold=0.8) -> str:
        """So khớp ảnh xám đã cắt với danh mục mẫu tương ứng, trả về tên trùng khớp nhất"""
        if crop_gray is None or not self.templates[category]:
            return "unknown"
            
        scores = {}
        for name, template in self.templates[category].items():
            # Đảm bảo ảnh mẫu nhỏ hơn hoặc bằng ảnh cần quét
            th, tw = template.shape[:2]
            ch, cw = crop_gray.shape[:2]
            if th > ch or tw > cw:
                # Resize tạm thời ảnh mẫu hoặc bỏ qua
                continue
                
            res = cv2.matchTemplate(crop_gray, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(res)
            scores[name] = max_val
            
        if not scores:
            return "unknown"
            
        best_match = max(scores, key=scores.get)
        if scores[best_match] >= threshold:
            return best_match
        return "unknown"

    def check_ammo_active(self, frame) -> bool:
        """Kiểm tra xem vùng chứa đạn có sáng đèn/hoạt động không bằng màu sắc hoặc nhị phân"""
        crop_gray = self.crop_and_preprocess(frame, self.roi_coordinates["ammo"])
        if crop_gray is None:
            return True # Fallback coi như có đạn
            
        # Tính độ sáng trung bình của vùng đạn
        mean_val = np.mean(crop_gray)
        # Nếu màn hình tối om (ví dụ hết đạn chữ màu xám tối) -> Trả về False
        return mean_val > 40

    def run(self):
        """Luồng phụ quét UI với chu kỳ 100ms (10 FPS)"""
        while self.running:
            # Ở đây trong thực tế ta sẽ truyền Frame chụp từ camera.py
            # Để demo luồng, ta sẽ đọc từ Shared State nếu có frame mới được đẩy từ luồng chính
            frame = self.shared_state.get_latest_full_frame()
            if frame is not None:
                # 1. Nhận dạng Vũ khí
                weapon_crop = self.crop_and_preprocess(frame, self.roi_coordinates["weapon"])
                weapon_id = self.match_template(weapon_crop, "weapons")
                
                # 2. Nhận dạng Tư thế
                stance_crop = self.crop_and_preprocess(frame, self.roi_coordinates["stance"])
                stance_name = self.match_template(stance_crop, "stances")
                
                # 3. Kiểm tra đạn hoạt động
                ammo_active = self.check_ammo_active(frame)
                
                # 4. Cập nhật trạng thái
                self.shared_state.update_ui_state(
                    weapon_id=weapon_id,
                    stance=stance_name,
                    ammo_active=ammo_active
                )
                
            time.sleep(0.1) # 10 FPS
