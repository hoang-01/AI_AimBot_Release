import os
import json

DEFAULT_CONFIG = {
    "camera": {
        "fov_width": 320,
        "fov_height": 320,
        "lock_region_w": 150,
        "lock_region_h": 150
    },
    "detection": {
        "model_path": "models/v7/best_v7_fp16_preprocessed.onnx",
        "conf_threshold": 0.7,
        "target_fps": 144
    },
    "pid": {
        "kp": 0.45,
        "kd": 0.1,
        "smoothing": 0.2,
        "deadzone_x": 1.5,
        "brake_force": 0.35,
        "brake_radius": 20.0
    },
    "hardware": {
        "vid": 0x1209,
        "pid": 0xC563,
        "secret_key": "MASH_KEY_HARDWARE_LOCKED_2026"
    },
    "macro": {
        "enabled": True,
        "aim_key": 0x02,
        "fire_key": 0x01,
        "shift_key": 0xA0,
        "key_off": 0x50,
        "key_on": 0x4F
    }
}

class ConfigManager:
    def __init__(self, config_path="config/settings.json"):
        self.config_path = config_path
        self.config = DEFAULT_CONFIG
        self.load_config()

    def load_config(self):
        """Đọc file cấu hình JSON, nếu không có tạo mặc định"""
        try:
            dir_name = os.path.dirname(self.config_path)
            if dir_name and not os.path.exists(dir_name):
                os.makedirs(dir_name, exist_ok=True)
                
            if os.path.exists(self.config_path):
                with open(self.config_path, "r", encoding="utf-8") as f:
                    user_cfg = json.load(f)
                    # Cập nhật đè lên cấu hình mặc định để tránh thiếu trường
                    for section, values in user_cfg.items():
                        if section in self.config:
                            self.config[section].update(values)
            else:
                self.save_config()
        except Exception as e:
            print(f"[WARN] Loi nap cau hinh, dung mac dinh: {e}")

    def save_config(self):
        """Ghi cấu hình hiện tại ra file JSON"""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            print(f"[OK] Da luu cau hinh tai: {self.config_path}")
        except Exception as e:
            print(f"[ERR] Loi ghi file cau hinh: {e}")

    def get(self, section, key):
        return self.config.get(section, {}).get(key, DEFAULT_CONFIG.get(section, {}).get(key))

    def update(self, section, key, value):
        if section not in self.config:
            self.config[section] = {}
        self.config[section][key] = value
        self.save_config()
