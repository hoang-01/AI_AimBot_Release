@echo off
chcp 65001 > nul
echo ===================================================
echo    ROCKET LAUNCHER - AI HEADSHOT (PYTHON OPTIMIZED)
echo ===================================================

:: 1. Kích hoạt môi trường ảo (nếu có)
if exist "venv_train\Scripts\activate.bat" (
    echo [INFO] Dang kich hoat moi truong ao...
    call venv_train\Scripts\activate.bat
) else (
    echo [WARN] Khong tim thay venv_train, chay bang Python he thong...
)

:: 2. Chạy Script chính từ thư mục src
echo [INFO] Dang khoi dong AI Engine...
python src/main.py

:: 3. Giữ cửa sổ nếu crash
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Chuong trinh bi dong dot ngot!
    pause
)
pause
