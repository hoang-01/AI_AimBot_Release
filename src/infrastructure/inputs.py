import ctypes

class KeyTracker:
    def __init__(self):
        # Cache GetAsyncKeyState của Win32 API
        self.get_async_key_state = ctypes.windll.user32.GetAsyncKeyState
        
        # Virtual Key Codes
        self.VK_LBUTTON = 0x01   # Chuột TRÁI
        self.VK_RBUTTON = 0x02   # Chuột PHẢI
        self.VK_LSHIFT = 0xA0    # SHIFT TRÁI
        self.VK_SHIFT = 0x10     # Phím SHIFT chung
        
    def is_key_pressed(self, vk_code: int) -> bool:
        """Kiểm tra xem phím có đang được đè xuống hay không"""
        return (self.get_async_key_state(vk_code) & 0x8000) != 0

    def is_aim_active(self, macro_enabled: bool, aim_key: int, fire_key: int, shift_key: int) -> bool:
        """Kiểm tra điều kiện kích hoạt Aim Assist"""
        if not macro_enabled:
            return False
            
        right_click = self.is_key_pressed(aim_key)
        left_click = self.is_key_pressed(fire_key)
        left_shift = self.is_key_pressed(shift_key) or self.is_key_pressed(self.VK_SHIFT)
        
        return (right_click and left_click) or (right_click and left_shift)
