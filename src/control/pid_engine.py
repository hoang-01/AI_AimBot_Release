import numpy as np
import time

class PIDEngine:
    def __init__(self, kp=0.45, kd=0.1, smoothing=0.2, deadzone_x=1.5, brake_force=0.35, brake_radius=20.0):
        self.kp = kp
        self.kd = kd
        self.smoothing = smoothing
        self.deadzone_x = deadzone_x
        self.brake_force = brake_force
        self.brake_radius = brake_radius
        
        self.sx = 0.0
        self.sy = 0.0
        self.prev_ex = 0.0
        self.rx = 0.0
        
        # Biến đếm viên đạn để phục vụ No-recoil
        self.shot_index = 0
        self.last_shot_time = 0.0

    def reset_state(self):
        self.sx = 0.0
        self.sy = 0.0
        self.prev_ex = 0.0
        self.rx = 0.0
        self.shot_index = 0
        self.last_shot_time = 0.0

    def update_shot_index(self, rpm: int):
        """Tính toán viên đạn thứ mấy dựa trên tốc độ bắn (RPM) khi đang sấy súng"""
        t_now = time.perf_counter()
        if self.last_shot_time == 0.0:
            self.last_shot_time = t_now
            self.shot_index = 0
            return
            
        time_per_shot = 60.0 / rpm
        elapsed = t_now - self.last_shot_time
        
        # Nếu khoảng cách giữa 2 lần cập nhật quá lâu (nhả chuột), reset
        if elapsed > 0.3:
            self.reset_state()
            self.last_shot_time = t_now
            return
            
        if elapsed >= time_per_shot:
            shots_fired = int(elapsed / time_per_shot)
            self.shot_index += shots_fired
            self.last_shot_time += shots_fired * time_per_shot

    def calculate_move(self, target, cx, cy, recoil_dx, recoil_dy) -> tuple:
        """
        Tính toán bước nhảy di chuyển chuột thô (mx, my) gửi cho HID:
        - mx: Tích hợp PID khóa trục X và phần dư recoil_dx của súng.
        - my: Chỉ di chuyển theo recoil_dy của súng (No-recoil).
        """
        mx, my = 0, 0
        
        # 1. Tính toán chuyển động ngắm bắn AI (Aim Assist) - Chỉ thực hiện trên Trục X
        if target:
            tx, ty = target
            
            # Làm mượt (Smoothing)
            self.sx = self.sx * self.smoothing + tx * (1.0 - self.smoothing) if self.sx != 0.0 else tx
            
            # Tính sai số (Error)
            ex = self.sx - cx
            
            # Tính toán PID
            vx = self.kp * ex + self.kd * (ex - self.prev_ex)
            self.prev_ex = ex
            
            dist = abs(ex)
            
            # Áp dụng phanh chuột (Mouse Brake)
            if self.brake_force > 0.01 and dist <= self.brake_radius:
                target_scale = max(0.1, dist / self.brake_radius)
                factor = 1.0 - (self.brake_force * (1.0 - target_scale))
                vx *= factor

            # Tránh vọt lố (Anti-overshoot)
            if abs(vx) > dist and dist > 0:
                vx = np.sign(vx) * dist

            # Kiểm tra vùng chết (Deadzone) để triệt tiêu jitter
            if abs(ex) < self.deadzone_x:
                vx = 0.0
                self.rx = 0.0
                
            self.rx += vx
            mx = int(self.rx)
            self.rx -= mx
        else:
            self.sx = 0.0
            self.prev_ex = 0.0
            
        # 2. Tích hợp phần dịch chuyển bù giật (No-recoil)
        # my là lực ghì dọc (recoil_dy)
        # recoil_dx sẽ được cộng trực tiếp vào mx (nếu có lệch ngang của súng)
        mx += recoil_dx
        my += recoil_dy
        
        # Giới hạn dải di chuyển của chuột HID từ -127 đến 127
        mx = max(-127, min(127, mx))
        my = max(-127, min(127, my))
        
        return mx, my
