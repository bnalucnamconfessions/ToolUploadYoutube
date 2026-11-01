@echo off
chcp 65001 >nul
setlocal
title Kiem tra Lenovo Xiao Xin Pad Pro GT

set "ADB="
if exist "%~dp0adb.exe" set "ADB=%~dp0adb.exe"
if not defined ADB (
    where adb.exe >nul 2>nul && set "ADB=adb"
)
if not defined ADB (
    echo [LOI] Khong tim thay adb.exe. Copy file .bat nay vao thu muc Platform-Tools ^(noi co adb.exe^) roi chay lai.
    pause
    exit /b 1
)

set "LOG=%~dp0log_kiem_tra_may.txt"
"%ADB%" start-server >nul 2>nul

> "%LOG%" echo ==== KIEM TRA LENOVO XIAO XIN PAD PRO GT ====
>>"%LOG%" echo Ngay kiem tra: %date% %time%
>>"%LOG%" echo.
>>"%LOG%" echo --- Danh sach thiet bi ADB ---
"%ADB%" devices >> "%LOG%" 2>&1
>>"%LOG%" echo.
>>"%LOG%" echo --- Thong tin may (doi chieu TB710FU / Android / ZUI) ---
for %%P in (ro.product.model ro.product.device ro.build.version.release ro.build.version.sdk ro.build.display.id ro.build.fingerprint ro.product.cpu.abi) do (
    for /f "delims=" %%V in ('"%ADB%" shell getprop %%P 2^>nul') do >>"%LOG%" echo %%P = %%V
)
>>"%LOG%" echo.
>>"%LOG%" echo --- Bo nho trong ---
"%ADB%" shell df -h /data >> "%LOG%" 2>&1
>>"%LOG%" echo.
>>"%LOG%" echo --- Trang thai chan cai dat / xac minh goi ---
for %%S in (global:package_verifier_enable global:verifier_verify_adb_installs secure:install_non_market_apps) do (
    for /f "tokens=1,2 delims=:" %%A in ("%%S") do (
        for /f "delims=" %%V in ('"%ADB%" shell settings get %%A %%B 2^>nul') do >>"%LOG%" echo %%S = %%V
    )
)
>>"%LOG%" echo.
>>"%LOG%" echo --- App nao duoc phep cai APK khong xac dinh (op 10066 / REQUEST_INSTALL_PACKAGES) ---
"%ADB%" shell appops query-op REQUEST_INSTALL_PACKAGES allow >> "%LOG%" 2>&1

type "%LOG%"
echo.
echo Da luu log tai: %LOG%
echo Hay gui file log nay kem anh chup thong bao loi khi can ho tro.
pause
endlocal
