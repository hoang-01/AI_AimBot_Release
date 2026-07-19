import numpy as np

class TargetSelector:
    def __init__(self, fov_w=320, fov_h=320, limit_min=85.0, limit_max=235.0):
        self.fov_w = fov_w
        self.fov_h = fov_h
        self.cx = fov_w / 2.0
        self.cy = fov_h / 2.0
        self.limit_min = limit_min
        self.limit_max = limit_max

    def select_target(self, boxes, classes, right_click, left_click_hold_time, left_shift) -> tuple:
        """
        Lọc và lựa chọn điểm bắn tối ưu (tx, ty) theo quy tắc ưu tiên:
        - Chuột Phải + Shift: Ưu tiên Người (Body)
        - Sấy (Chuột Trái > 0.15s): Ưu tiên Người (Body)
        - Ngắm thường (Chuột Phải): Ưu tiên Đầu (Head)
        """
        if len(boxes) == 0:
            return None

        # 1. Mặt nạ lọc toạ độ nằm trong vùng giới hạn ở tâm FOV
        bxs = boxes[:, 0]
        bys = boxes[:, 1]
        in_limit = (bxs >= self.limit_min) & (bxs <= self.limit_max) & (bys >= self.limit_min) & (bys <= self.limit_max)
        
        filtered_boxes = boxes[in_limit]
        filtered_classes = classes[in_limit]
        
        if len(filtered_boxes) == 0:
            return None

        heads = []
        bodies = []
        
        for box, cls_id in zip(filtered_boxes, filtered_classes):
            if cls_id == 0:
                heads.append(box)
            elif cls_id == 1:
                bodies.append(box)

        # 2. Quy luật quyết định mục tiêu
        aim_active = (right_click and left_click_hold_time > 0.0) or (right_click and left_shift)
        if not aim_active:
            return None

        # Trường hợp 1: Nhấn giữ Shift -> Kéo cứng vào Người
        if right_click and left_shift:
            if len(bodies) > 0:
                best_body = min(bodies, key=lambda b: (b[0] - self.cx)**2 + (b[1] - self.cy)**2)
                bx, by, bw, bh = best_body
                aim_x = bx
                aim_y = (by + bh / 2.0) - bh * 0.50  # 50% từ dưới lên
                return (aim_x, aim_y)
            elif len(heads) > 0:
                best_head = min(heads, key=lambda b: (b[0] - self.cx)**2 + (b[1] - self.cy)**2)
                bx, by, bw, bh = best_head
                aim_x = bx
                aim_y = (by + bh / 2.0) - bh * 0.20  # 20% ĐẦU từ dưới lên
                return (aim_x, aim_y)

        # Trường hợp 2: Đang sấy (Chuột trái giữ lâu > 0.15 giây) -> Kéo vào Thân
        elif left_click_hold_time > 0.15:
            if len(bodies) > 0:
                best_body = min(bodies, key=lambda b: (b[0] - self.cx)**2 + (b[1] - self.cy)**2)
                bx, by, bw, bh = best_body
                aim_x = bx
                aim_y = (by + bh / 2.0) - bh * 0.50  # 50% từ dưới lên
                return (aim_x, aim_y)
            elif len(heads) > 0:
                best_head = min(heads, key=lambda b: (b[0] - self.cx)**2 + (b[1] - self.cy)**2)
                bx, by, bw, bh = best_head
                aim_x = bx
                aim_y = (by + bh / 2.0) - bh * 0.20
                return (aim_x, aim_y)

        # Trường hợp 3: Bấm giữ chuột phải thông thường -> Ưu tiên bám ĐẦU
        else:
            if len(heads) > 0:
                best_head = min(heads, key=lambda b: (b[0] - self.cx)**2 + (b[1] - self.cy)**2)
                bx, by, bw, bh = best_head
                aim_x = bx
                aim_y = (by + bh / 2.0) - bh * 0.20  # 20% ĐẦU từ dưới lên
                return (aim_x, aim_y)
            elif len(bodies) > 0:
                best_body = min(bodies, key=lambda b: (b[0] - self.cx)**2 + (b[1] - self.cy)**2)
                bx, by, bw, bh = best_body
                aim_x = bx
                aim_y = (by + bh / 2.0) - bh * 0.70  # 70% NGƯỜI từ dưới lên (bám thân cao)
                return (aim_x, aim_y)

        return None
