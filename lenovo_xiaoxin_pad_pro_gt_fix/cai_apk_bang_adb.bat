@echo off
chcp 65001 >nul
setlocal
title Cai APK vao Lenovo Xiao Xin Pad Pro GT bang ADB

rem --- Tim adb.exe: uu tien cung thu muc voi file .bat nay, sau do den PATH ---
set "ADB="
if exist "%~dp0adb.exe" set "ADB=%~dp0adb.exe"
if not defined ADB (
    where adb.exe >nul 2>nul && set "ADB=adb"
)
if not defined ADB (
    echo [LOI] Khong tim thay adb.exe.
    echo Hay tai Android SDK Platform-Tools tu:
    echo   https://developer.android.com/tools/releases/platform-tools
    echo Giai nen, roi copy file .bat nay vao CUNG thu muc co adb.exe va chay lai.
    pause
    exit /b 1
)

rem --- Lay duong dan APK: keo-tha len file .bat, hoac go/duong dan khi duoc hoi ---
set "APK=%~1"
if not defined APK (
    echo Keo file .apk tha len file .bat nay, hoac dan duong dan file APK vao ben duoi.
    set /p "APK=Duong dan file APK: "
)
set "APK=%APK:"=%"
if not exist "%APK%" (
    echo [LOI] Khong tim thay file: %APK%
    pause
    exit /b 1
)

echo.
echo Dang kiem tra ket noi may tinh bang...
"%ADB%" start-server >nul 2>nul
"%ADB%" devices
echo.
echo Neu danh sach tren trong, hoac may bao "unauthorized":
echo  1. Cam lai cap USB, chon che do Truyen file tren may tinh bang.
echo  2. Bat Go loi USB trong Tuy chon nha phat trien.
echo  3. Bam "Cho phep" tren hop thoai hien tren man hinh may tinh bang.
echo.

rem --- Tat xac minh goi cai dat (lop chan thuong gap tren ROM ZUI Trung Quoc) ---
"%ADB%" shell settings put global package_verifier_enable 0 >nul 2>nul
"%ADB%" shell settings put global verifier_verify_adb_installs 0 >nul 2>nul

echo Dang cai: %APK%
"%ADB%" install -r -g --bypass-low-target-sdk-block "%APK%"
if errorlevel 1 (
    echo.
    echo Lan 1 chua duoc, thu lai khong kem co tuong thich Android moi...
    "%ADB%" install -r -g "%APK%"
)

echo.
echo ---------------------------------------------------------------
echo Neu thay chu "Success" o tren: cai dat THANH CONG, kiem tra man hinh chinh cua may.
echo Neu thay dong INSTALL_FAILED_... : xem bang dich loi trong HUONG_DAN_SUA_LOI.md muc 4.
echo ---------------------------------------------------------------
pause
endlocal
