from setuptools import setup
from Extension import Extension
from Cython.Build import cythonize

# Định nghĩa danh sách các module lõi cần biên dịch sang mã máy nhị phân (.pyd) để bảo vệ mã nguồn
extensions = [
    # Tầng Xử Lý & Nhận Dạng
    "processing/ai_engine.py",
    "processing/ui_tracker.py",
    
    # Tầng Nghiệp Vụ & Điều Khiển
    "control/pid_engine.py",
    "control/recoil_db.py",
    "control/target_select.py"
]

setup(
    name="AI_Aim_NoRecoil_Core",
    ext_modules=cythonize(
        extensions,
        compiler_directives={'language_level': "3"}
    ),
)
