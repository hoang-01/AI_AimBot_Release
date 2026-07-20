import os
import cv2
import numpy as np

def get_sorted_centers(mask):
    # Tìm các đường biên (contours) của các chấm tròn đạn
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    centers = []
    for c in contours:
        # Lọc theo diện tích để tránh nhiễu lưới hoặc chữ số
        area = cv2.contourArea(c)
        if 5 < area < 200:
            M = cv2.moments(c)
            if M["m00"] != 0:
                cX = int(M["m10"] / M["m00"])
                cY = int(M["m01"] / M["m00"])
                centers.append((cX, cY))
    
    # Sắp xếp các chấm từ dưới lên trên (cY giảm dần do hệ tọa độ ảnh gốc 0,0 ở góc trái trên)
    centers = sorted(centers, key=lambda p: p[1], reverse=True)
    return centers

def print_recoil_deltas(name, centers):
    print(f"\n=== KET QUA PHAN TICH DO GIAT: {name} ({len(centers)} diem) ===")
    if len(centers) < 2:
        print("Khong du diem de tinh toan.")
        return
    
    dy_list = []
    dx_list = []
    for i in range(1, len(centers)):
        # Tọa độ ảnh cY giảm dần khi đi lên -> dy = cY[i-1] - cY[i] để ra số dương kéo xuống
        dy = centers[i-1][1] - centers[i][1]
        dx = centers[i][0] - centers[i-1][0] # Độ lệch ngang
        dy_list.append(dy)
        dx_list.append(dx)
        print(f"Phat {i} -> {i+1}: dy = {dy} px, dx = {dx} px")
        
    print(f"Mang dy cho macro: {dy_list}")

def detect_recoil_pixels(image_path):
    possible_paths = [
        image_path,
        os.path.join(os.path.dirname(__file__), image_path),
        os.path.join(os.path.dirname(__file__), "..", image_path)
    ]
    
    img = None
    resolved_path = ""
    for path in possible_paths:
        abs_path = os.path.abspath(path)
        if os.path.exists(abs_path):
            resolved_path = abs_path
            img = cv2.imread(abs_path)
            break
            
    if img is None:
        print(f"[ERR] Khong the tim thay file anh tai cac duong dan sau:")
        for path in possible_paths:
            print(f"  -> {os.path.abspath(path)}")
        print("\n[HUONG DAN] Vui long tai anh bieu do ve, dat ten la 'recoil_chart.png' va luu vao mot trong cac duong dan tren.")
        return

    print(f"[OK] Da tim thay va nap anh tai: {resolved_path}")
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # 1. Lọc màu Cam (AKM/AUG)
    lower_orange = np.array([5, 100, 100])
    upper_orange = np.array([20, 255, 255])
    mask_orange = cv2.inRange(hsv, lower_orange, upper_orange)

    # 2. Lọc màu Xanh lá (M416)
    lower_green = np.array([35, 100, 100])
    upper_green = np.array([85, 255, 255])
    mask_green = cv2.inRange(hsv, lower_green, upper_green)

    akm_centers = get_sorted_centers(mask_orange)
    m416_centers = get_sorted_centers(mask_green)

    print_recoil_deltas("Duong Dan Cam (AKM/AUG)", akm_centers)
    print_recoil_deltas("Duong Dan Xanh (M416)", m416_centers)

if __name__ == "__main__":
    detect_recoil_pixels("recoil_chart.png")
