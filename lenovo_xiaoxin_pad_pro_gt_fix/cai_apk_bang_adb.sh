#!/usr/bin/env bash
# Cai APK vao Lenovo Xiao Xin Pad Pro GT (TB710FU) qua ADB - macOS/Linux
# Cach dung: ./cai_apk_bang_adb.sh file.apk   (hoac keo file vao terminal)
set -u

if command -v adb >/dev/null 2>&1; then
  ADB="adb"
elif [ -x "$(dirname "$0")/adb" ]; then
  ADB="$(dirname "$0")/adb"
else
  echo "[LOI] Khong tim thay adb. Tai Android SDK Platform-Tools tai:"
  echo "  https://developer.android.com/tools/releases/platform-tools"
  exit 1
fi

APK="${1:-}"
if [ -z "$APK" ]; then
  read -r -p "Duong dan file APK: " APK
fi
if [ ! -f "$APK" ]; then
  echo "[LOI] Khong tim thay file: $APK"
  exit 1
fi

echo "Dang kiem tra ket noi may tinh bang..."
"$ADB" start-server >/dev/null 2>&1
"$ADB" devices
echo
echo "Neu danh sach trong hoac bao 'unauthorized': cam lai cap, chon Truyen file,"
echo "bat Go loi USB va bam 'Cho phep' tren man hinh may tinh bang."
echo

# Tat xac minh goi cai dat (lop chan thuong gap tren ROM ZUI Trung Quoc)
"$ADB" shell settings put global package_verifier_enable 0 >/dev/null 2>&1
"$ADB" shell settings put global verifier_verify_adb_installs 0 >/dev/null 2>&1

echo "Dang cai: $APK"
if ! "$ADB" install -r -g --bypass-low-target-sdk-block "$APK"; then
  echo
  echo "Lan 1 chua duoc, thu lai khong kem co tuong thich Android moi..."
  "$ADB" install -r -g "$APK"
fi

echo
echo "Thay chu 'Success' la cai xong. Neu thay INSTALL_FAILED_... thi xem"
echo "bang dich loi trong HUONG_DAN_SUA_LOI.md muc 4."
