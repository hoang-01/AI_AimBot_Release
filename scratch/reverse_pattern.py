# Script tinh nguoc mang dan co so (Standing / No attachments)
# tu mang dan da test chuan trong game voi cac phu kien.

# 1. Nhap mang dan da test chuan trong game cua ban tai day
# Day la luc keo chuot thuc te (mickeys) ma ban thay sấy chuẩn nhat
WORKING_PATTERN = [
    45, 44, 30, 30, 30, 48, 45, 45, 43, 45, 
    48, 45, 45, 45, 48, 45, 43, 45, 45, 48,
    45, 48, 45, 48, 45, 48, 45, 48, 45, 48,
    45, 48, 45, 48, 45, 48, 45, 48, 45, 48
]

# 2. Cau hinh phu kien ban da dung khi test trong game
SENSITIVITY_MULTIPLIER = 1.0        # Do nhay chuot cua ban trong script
VERTICAL_RECOIL_BASE = 1.50         # Do giat doc co ban cua AUG (1.50)

# Chon he so tu the ban da dung luc test (Chon 1 trong 2):
# MULTIPLIER_STANCE = 0.80          # Neu ban ngoi ban (squat)
# MULTIPLIER_STANCE = 0.52          # Neu ban nam ban (down)
MULTIPLIER_STANCE = 0.80            # Mac dinh dat la ngoi ban nhu ban vua test

MULTIPLIER_GRIP = 0.85              # Tay cam thumb
MULTIPLIER_SCOPE = 1.0              # Red dot (1x)
MULTIPLIER_MUZZLE = 0.784           # Dau nong compensator

# 3. Tinh toan he so nhan phu kien
total_multiplier = (
    (VERTICAL_RECOIL_BASE / 1.33) *
    MULTIPLIER_STANCE *
    MULTIPLIER_GRIP *
    MULTIPLIER_SCOPE *
    MULTIPLIER_MUZZLE *
    SENSITIVITY_MULTIPLIER
)

print(f"--> Tong he so dang ap dung khi test: {total_multiplier:.6f}")

# 4. Tinh nguoc lai mang goc (base pattern: dung ban + khong phu kien)
# Cong thuc: base = working / total_multiplier
base_pattern = []
for dy in WORKING_PATTERN:
    base_val = dy / total_multiplier
    base_pattern.append(round(base_val))

print("\n=== MANG GOC SINH NGUOC (Dung ban + Sung tran) ===")
print("Hay copy mang nay dan vao AUG_BASE_PATTERN trong code:")
print(base_pattern)
