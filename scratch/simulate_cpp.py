# Script de mo phong logic C++ va tinh ra mang dan base pattern 40 vien cua python

def simulate():
    # Tham so C++
    base_speed = 2.95
    accel_step = 0.02075
    max_accel_count = 90
    sleep_time_ms = 15.0
    fire_rate_ms = 84.0
    num_bullets = 40
    
    # 1. Mo phong cac buoc 15ms trong chu ky sấy
    total_time_ms = num_bullets * fire_rate_ms
    steps = int(total_time_ms / sleep_time_ms) # 3360 / 15 = 224 steps
    
    accel = 0.0
    accel_count = 0
    
    # Mang luu speed tai tung step 15ms
    step_speeds = []
    for i in range(steps):
        if accel_count < max_accel_count:
            accel += accel_step
            accel_count += 1
        
        move_speed = base_speed + accel
        step_speeds.append(move_speed)
        
    # 2. Gom nhom cac step 15ms vao tung khoang 84ms cua 40 vien dan
    bullet_moves = []
    for bullet_idx in range(num_bullets):
        start_time = bullet_idx * fire_rate_ms
        end_time = (bullet_idx + 1) * fire_rate_ms
        
        # Tinh toan phan tram thoi gian ma moi buoc 15ms chiem trong khoang 84ms nay
        total_move_in_bullet = 0.0
        
        for step_idx, speed in enumerate(step_speeds):
            step_start = step_idx * sleep_time_ms
            step_end = (step_idx + 1) * sleep_time_ms
            
            # Giao lo (overlap) giua [step_start, step_end] va [start_time, end_time]
            overlap_start = max(start_time, step_start)
            overlap_end = min(end_time, step_end)
            
            if overlap_end > overlap_start:
                # Tỉ lệ dong gop cua buoc nay vao vien dan hien tai
                fraction = (overlap_end - overlap_start) / sleep_time_ms
                total_move_in_bullet += speed * fraction
                
        bullet_moves.append(total_move_in_bullet)
        
    print("=== KET QUA MO PHONG C++ (Tong di chuyen thuc te moi vien) ===")
    print([round(x, 2) for x in bullet_moves])
    print(f"Tong cong chuot keo (mickeys): {sum(bullet_moves):.2f}")
    
    # 3. Tinh nguoc lai mang base pattern dung ban + sung tran
    # Gia su C++ nay dang chay cho trang thai: Ngoi (0.80) + Thumb (0.85) + Comp (0.784)
    # Tức là: final = base * total_multiplier
    # -> base = final / total_multiplier
    MULTIPLIER_STANCE = 0.80
    MULTIPLIER_GRIP = 0.85
    MULTIPLIER_MUZZLE = 0.784
    VERTICAL_RECOIL_BASE = 1.50 # Tu cau hinh
    
    total_multiplier = (
        (VERTICAL_RECOIL_BASE / 1.33) *
        MULTIPLIER_STANCE *
        MULTIPLIER_GRIP *
        MULTIPLIER_MUZZLE
    )
    
    base_pattern = [round(x / total_multiplier) for x in bullet_moves]
    print(f"\n=== MANG GOC QUY DOI NGUOC (Ngoi + Thumb + Comp) ===")
    print(base_pattern)
    print(f"Tong luc: {sum(base_pattern)}")

if __name__ == "__main__":
    simulate()
