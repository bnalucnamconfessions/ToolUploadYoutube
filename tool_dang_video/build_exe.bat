@echo off
chcp 65001 >nul
echo ========================================
echo   Build YouTube Upload Tool - file EXE
echo ========================================
cd /d "%~dp0"

:: Cài PyInstaller nếu chưa có
pip show pyinstaller >nul 2>&1 || pip install pyinstaller

echo.
echo Đang đóng gói (có thể mất vài phút)...
echo.
pyinstaller --noconfirm YouTubeUploadTool.spec

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Build that bai. Kiem tra loi phia tren.
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Build xong.
echo   File exe: dist\YouTubeUploadTool.exe
echo ========================================
echo.
echo Ban co the copy dist\YouTubeUploadTool.exe sang may khac (can cai Chrome).
echo Double-click file exe de chay, khong can cai Python.
echo.
echo Khi chay exe, thu muc debug_logs (cung cap voi exe) se luu console.log, crash.log, debug-57c0c7.log de gui cho dev khi bao loi.
echo.
pause
