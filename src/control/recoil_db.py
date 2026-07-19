import numpy as np

# Cơ sở dữ liệu mẫu cho súng và phụ kiện
RECOIL_DATABASE = {
    "rifle_ak": {
        "rpm": 600,             # Tốc độ bắn (Rounds Per Minute)
        "base_pattern": [       # Danh sách độ lệch thô (dx, dy) từng phát sấy súng
            (0, 8), (0, 10), (1, 12), (-1, 13), (2, 12), 
            (0, 11), (-1, 10), (1, 11), (-2, 10), (2, 9),
            (0, 8), (1, 8), (-1, 8), (0, 8), (0, 8),
            (0, 7), (0, 7), (1, 7), (-1, 7), (0, 7),
            (0, 6), (0, 6), (0, 6), (0, 6), (0, 6),
            (0, 5), (0, 5), (0, 5), (0, 5), (0, 5)
        ],
        "factors": {
            "compensator": 0.85,    # Giảm 15% giật
            "vertical_grip": 0.80,  # Giảm 20% giật dọc
            "horizontal_grip": 0.90 # Giảm 10% giật ngang
        }
    },
    "default": {
        "rpm": 600,
        "base_pattern": [(0, 0)] * 30,
        "factors": {}
    }
}

class RecoilProfileManager:
    def __init__(self):
        self.db = RECOIL_DATABASE
        self.stance_multipliers = {
            "standing": 1.0,
            "crouching": 0.8,    # Ngồi giảm 20% độ giật
            "prone": 0.5         # Nằm giảm 50% độ giật
        }
        
    def get_recoil_delta(self, weapon_id: str, shot_index: int, stance: str, attachments: list, scope_zoom: float = 1.0) -> tuple:
        """
        Tính toán khoảng di chuyển (dx, dy) cần ghì lại dựa trên:
        Súng hiện tại, Phát bắn thứ i, Tư thế, Phụ kiện, và Độ thu phóng Ống ngắm.
        """
        gun_info = self.db.get(weapon_id, self.db["default"])
        pattern = gun_info["base_pattern"]
        
        # Nếu bắn vượt quá độ dài pattern, lấy viên cuối cùng để duy trì ghì ổn định
        idx = min(shot_index, len(pattern) - 1)
        base_dx, base_dy = pattern[idx]
        
        # 1. Tính hệ số tư thế (Stance factor)
        k_stance = self.stance_multipliers.get(stance, 1.0)
        
        # 2. Tính hệ số phụ kiện tích lũy (Attachments factor)
        k_att_x = 1.0
        k_att_y = 1.0
        
        for att in attachments:
            factor = gun_info["factors"].get(att, 1.0)
            if "vertical" in att or "compensator" in att:
                k_att_y *= factor
            if "horizontal" in att or "compensator" in att:
                k_att_x *= factor
                
        # 3. Tính hệ số Zoom ống ngắm (Scope zoom)
        k_scope = scope_zoom # Tỷ lệ thuận với độ zoom màn hình
        
        # 4. Tính lực bù cuối cùng
        final_dx = int(base_dx * k_stance * k_att_x * k_scope)
        final_dy = int(base_dy * k_stance * k_att_y * k_scope)
        
        return final_dx, final_dy
