# Lenovo Xiao Xin Pad Pro GT — Kiểm tra máy & Sửa lỗi không cài được app từ bên ngoài (APK)

> **Quan trọng — đọc trước:** Máy tính bảng của bạn không kết nối vật lý với máy tính đang chạy
> trợ lý này (đã kiểm tra: không có thiết bị ADB/USB nào), nên không ai thao tác trực tiếp
> lên máy của bạn từ xa được. Tài liệu + bộ script này là cách sửa thật: bạn làm trên máy
> (Cách A, 2 phút) hoặc cắm máy vào PC Windows rồi chạy script có sẵn (Cách B — gần như
> luôn thành công vì ADB bỏ qua lớp chặn "nguồn không xác định" trên máy).
> Làm xong Cách A mà vẫn lỗi thì chạy Cách B và gửi lại file log cho người hỗ trợ.

---

## 1. Kiểm tra máy: Lenovo Xiao Xin Pad Pro GT (TB710FU)

Thông số chuẩn của dòng này để đối chiếu với máy của bạn:

| Hạng mục | Thông số |
|---|---|
| Mã máy (Model) | **TB710FU** |
| Màn hình | 11.1" LCD 3200×2000, 144Hz, ~800 nit |
| Chip | Snapdragon 8 Gen 3 (SM8650-AB), GPU Adreno 750 |
| RAM / Bộ nhớ | 8GB hoặc 12GB LPDDR5X / 128GB hoặc 256GB UFS, có khe microSD |
| Pin | 8.860 mAh, sạc nhanh 68W |
| Camera | Sau 13MP AF, trước 8MP |
| Hệ điều hành lúc bán | Android 15, giao diện **ZUI 16** (bản Trung Quốc) — máy cập nhật sau này có thể lên Android 16 / ZUI 17 (ZUXOS) |
| Thân máy | 458g, mỏng 5,99mm, 4 loa JBL Dolby Atmos |
| Phiên bản | Chủ yếu là **bản nội địa Trung Quốc (ROM CN/ZUI)**; bản "quốc tế" bán ngoài thường do shop tự cài thêm Google Play |

**Tự kiểm tra trên máy của bạn (30 giây):**
`Cài đặt (设置) → Giới thiệu về máy tính bảng (关于平板电脑)` và đối chiếu:
- **Model có phải TB710FU không** — nếu không, bạn đang cầm dòng khác (ví dụ TB375FC là Pad Pro 12.7), cách sửa gần giống nhưng đừng nạp nhầm firmware.
- **Phiên bản Android / ZUI** — ghi lại con số này, nó quyết định tên menu bên dưới.
- Vào `Cài đặt → Bộ nhớ` xem còn trống bao nhiêu GB (thiếu bộ nhớ cũng làm cài đặt thất bại lặng lẽ).

---

## 2. Vì sao không cài được app từ bên ngoài? (7 nguyên nhân, theo độ thường gặp)

Máy ROM Trung Quốc ZUI chặn cài APK ở **nhiều lớp hơn máy quốc tế**, nên "đã bật nguồn không
xác định rồi vẫn không cài được" là chuyện rất thường gặp:

| # | Hiện tượng bạn thấy | Nguyên nhân gốc | Cách sửa |
|---|---|---|---|
| 1 | Bấm file APK → báo *"Vì lý do bảo mật… cấm cài ứng dụng không rõ nguồn gốc"* / `出于安全考虑…` | Chưa cấp quyền **Cài đặt ứng dụng không xác định** cho *đúng app đã tải/mở file* (Chrome, Zalo, Trình quản lý file…). Android 8+ cấp quyền **theo từng app**, không còn 1 công tắc chung | Cách A bước 1 |
| 2 | Đã cho phép rồi, bấm Cài đặt vẫn bị chặn / quay về màn hình chính, hoặc báo *"xác minh thất bại"* | **Trung tâm bảo mật ZUI (安全中心)** quét & xác minh APK online trước khi cài; APK không có trong cơ sở dữ liệu Lenovo, không có mạng, hoặc chưa đăng nhập tài khoản Lenovo thì xác minh fail → chặn | Cách A bước 2, hoặc Cách B (ADB) |
| 3 | Báo *"Đã xảy ra sự cố khi phân tích cú pháp gói"* / `解析包错误` | File tải chưa xong/bị hỏng, bị đổi đuôi (`.apk.1`, `.bin`), hoặc app yêu cầu Android mới hơn máy | Tải lại file, kiểm tra đuôi `.apk`; xem §4 |
| 4 | Báo *"Ứng dụng chưa được cài đặt / App not installed"* | Xung đột chữ ký với bản đã cài, bộ nhớ đầy, hoặc APK không có bản cho kiến trúc máy (máy này **arm64-v8a**) | Gỡ bản cũ rồi cài lại; giải phóng bộ nhớ; tải bản `arm64-v8a`/universal |
| 5 | Tải được nhưng là file `.apks` / `.apkm` / `.xapk` bấm vào không chạy | Đó là gói **split APK** (thường tải từ APKPure/APKMirror), trình cài mặc định của máy không mở được | §4: dùng SAI / APKMirror Installer |
| 6 | App cài xong mở lên văng ngay / báo thiếu Google Play Services | ROM CN gốc **không có sẵn Google Mobile Services** đầy đủ; app phụ thuộc GMS (map, đăng nhập Google, thông báo đẩy) sẽ lỗi | §5 |
| 7 | Nút *Cài đặt* bị mờ, hoặc báo *"Quản trị viên thiết bị / chính sách bảo mật cấm"* | Đang bật chế độ trẻ em/thanh thiếu niên (青少年模式), quản lý thiết bị, hoặc app quản trị (MDM) của nơi bán/công ty đang khóa | Tắt chế độ trẻ em; `Cài đặt → Bảo mật → Quản trị viên thiết bị` tắt app lạ; liên hệ nơi bán nếu máy bị khóa MDM |

> Chụp lại **nguyên văn dòng báo lỗi** (kể cả tiếng Trung) là cách nhanh nhất để biết bạn
> đang dính số mấy trong bảng trên.

---

## 3. Cách A — Sửa trực tiếp trên máy (làm trước, không cần PC)

### Bước 1: Cấp quyền cài APK cho đúng app nguồn
Đây là hướng dẫn chính thức của Lenovo cho dòng Xiao Xin Pad:

1. Mở **Cài đặt (设置)** → ở ô tìm kiếm trên cùng gõ `未知应用` hoặc **"không xác định"**.
2. Chọn **Cài đặt ứng dụng không xác định (安装未知应用)**.
3. Chọn **đúng app bạn dùng để tải/mở file APK** — ví dụ Chrome, Zalo, Telegram,
   hoặc **Trình quản lý file (文件管理)** — rồi bật **Cho phép cài đặt ứng dụng (允许安装应用)**.
   - Tải bằng app nào thì phải bật cho app đó. Bật cho Chrome nhưng mở file bằng
     Quản lý file thì vẫn bị chặn — lỗi này rất nhiều người mắc.
4. Quay lại file APK, bấm cài lại.

Đường menu đầy đủ nếu tìm kiếm không ra:
`Cài đặt → Quản lý ứng dụng (应用管理) → Quyền ứng dụng đặc biệt (特殊应用权限) → Cài đặt ứng dụng không xác định (安装未知来源应用)`

### Bước 2: Nếu vẫn bị Trung tâm bảo mật chặn
1. Kết nối Wi-Fi (quá trình xác minh APK của ZUI cần internet), thử cài lại và **đợi hết
   đếm ngược cảnh báo rủi ro** (thường 5 giây) rồi mới bấm tiếp tục — bấm vội là bị hủy.
2. Đăng nhập **tài khoản Lenovo** trong `Cài đặt → Tài khoản` — một số bản ZUI yêu cầu
   đăng nhập mới cho qua bước xác minh cài đặt.
3. Tạm tắt chế độ **Thuần khiết/Trẻ em** nếu đang bật: tìm trong Cài đặt `青少年模式` /
   `纯净模式` và tắt.
4. Xóa dữ liệu trình cài đặt bị kẹt: `Cài đặt → Quản lý ứng dụng → (menu ⋮ → Hiện ứng dụng hệ thống) → Trình cài đặt gói (软件包安装程序) → Bộ nhớ → Xóa dữ liệu`, rồi khởi động lại máy và thử lại.
5. Cập nhật ZUI lên bản mới nhất: `Cài đặt → Giới thiệu → Cập nhật hệ thống (系统更新)`.

### Bước 3: Kiểm tra file APK trước khi cài
- File phải tải xong 100%, đúng đuôi `.apk` (đổi tên bỏ `.1`/`.bin` ở cuối nếu bị trình duyệt tự thêm).
- Còn trống **ít nhất gấp 2–3 lần** dung lượng APK trong bộ nhớ trong.
- Chỉ tải từ nguồn tin cậy: trang chủ của app, APKMirror (chữ ký đã kiểm chứng). Không cài APK "mod/crack" không rõ nguồn — đây cũng là nhóm hay bị ZUI chặn nhất vì chữ ký lạ.

Vẫn không được → sang Cách B. Cách B đi đường ADB nên **bỏ qua hoàn toàn** lớp chặn ở Bước 1–2.

---

## 4. Cách B — Cài bằng máy tính qua ADB (cách chắc chắn nhất) ⭐

Kèm theo trong thư mục này:

| File | Dùng để làm gì |
|---|---|
| `kiem_tra_may.bat` | Chạy 1 lần: tự lấy Model, phiên bản Android/ZUI, kiến trúc chip, bộ nhớ trống, trạng thái chặn cài đặt → xuất file `log_kiem_tra_may.txt` để gửi người hỗ trợ |
| `cai_apk_bang_adb.bat` | **Kéo-thả file `.apk` lên file .bat này** (hoặc double-click rồi chọn) → tự cài vào máy, nếu lỗi thì dịch mã lỗi ra tiếng Việt |
| `cai_apk_bang_adb.sh` | Bản tương tự cho macOS/Linux |

### Chuẩn bị (chỉ làm 1 lần)
1. Trên PC Windows: tải **Android SDK Platform-Tools** (gói chứa `adb.exe`) từ
   https://developer.android.com/tools/releases/platform-tools → giải nén →
   **copy 2 file `.bat` trong thư mục này vào cùng thư mục vừa giải nén** (nơi có `adb.exe`).
2. Trên máy tính bảng, bật **Gỡ lỗi USB (USB调试)**:
   - `Cài đặt → Giới thiệu về máy tính bảng` → chạm **7 lần** vào **Phiên bản ZUI (ZUI版本)**
     cho đến khi báo đã bật chế độ nhà phát triển.
   - Quay ra `Cài đặt → Cài đặt chung (通用设置) → Tùy chọn nhà phát triển (开发者选项)`
     → bật **Gỡ lỗi USB (USB调试)**. (Một số bản ZUI nằm ở `Cài đặt → Hệ thống → Tùy chọn nhà phát triển`.)
   - Nếu thấy thêm mục **"Gỡ lỗi USB (cài đặt bảo mật)" / USB安装** thì bật luôn.
3. Cắm cáp USB (cáp sạc theo máy là được), trên máy tính bảng chọn chế độ **Truyền file**,
   và khi hộp thoại *"Cho phép gỡ lỗi USB?"* hiện lên thì tích **Luôn cho phép** → **Cho phép**.

### Chạy
- Kiểm tra máy: double-click `kiem_tra_may.bat` → đọc/gửi file `log_kiem_tra_may.txt`.
- Cài app: **kéo file `.apk` thả lên `cai_apk_bang_adb.bat`**. Thấy chữ `Success` là xong,
  app sẽ xuất hiện ngoài màn hình chính của máy tính bảng dù trước đó bị chặn.

### Script báo lỗi thì đọc ở đây
| Dòng lỗi ADB | Nghĩa là gì | Xử lý |
|---|---|---|
| `no devices/emulators found` / `unauthorized` | Chưa cắm cáp, chưa chọn Truyền file, hoặc chưa bấm Cho phép gỡ lỗi USB trên màn hình máy | Rút cắm lại, nhìn màn hình máy bấm **Cho phép** |
| `INSTALL_FAILED_UPDATE_INCOMPATIBLE` | Đã có bản cũ với chữ ký khác | Gỡ app cũ trên máy trước (sẽ mất dữ liệu app), chạy lại |
| `INSTALL_FAILED_VERSION_DOWNGRADE` | File APK cũ hơn bản đang có trong máy | Cài bản mới hơn, hoặc gỡ bản cũ trước |
| `INSTALL_FAILED_DEPRECATED_SDK_VERSION` / `not compatible` | App quá cũ, bị Android 15 chặn (targetSdk quá thấp) | Xin nhà phát triển bản mới; script đã tự thử lại với cờ bỏ qua chặn này, nếu vẫn fail là app thật sự không tương thích |
| `INSTALL_FAILED_NO_MATCHING_ABIS` | APK không có bản arm64 | Tải bản `arm64-v8a` hoặc bản universal |
| `INSTALL_FAILED_INSUFFICIENT_STORAGE` | Hết bộ nhớ | Dọn bộ nhớ trong rồi chạy lại |
| `INSTALL_FAILED_VERIFICATION_FAILURE` | Máy vẫn bật xác minh gói cài đặt | Script đã tự tắt xác minh qua ADB; nếu vẫn báo, khởi động lại máy rồi chạy lại |

---

## 5. Các trường hợp đặc biệt

**File `.apks` / `.apkm` / `.xapk` (split APK):** đừng đổi đuôi thành `.apk`.
Cài app **SAI (Split APKs Installer)** hoặc **APKMirror Installer** (tải bằng Cách B file APK
gốc của chúng trước), rồi dùng app đó mở file split. Nhiều app trên APKPure giờ chỉ xuất dạng này.

**App cần Google Play / Google Services:** nếu máy bạn là ROM CN chưa có CH Play,
đừng cài các file "Google Installer" trôi nổi (đa số đã cũ và bị ZUI chặn).
Thứ tự nên làm: (1) kiểm tra trong `Cài đặt → Quản lý ứng dụng` xem đã có
*Google Play Services / Cửa hàng Google Play* chưa — nhiều shop đã cài sẵn;
(2) nếu chưa có, nhờ đúng nơi bán máy hỗ trợ cài GMS/firmware quốc tế (ROW) cho TB710FU —
đây là việc liên quan firmware, tự làm sai có rủi ro brick máy và mất bảo hành,
nên không nằm trong phạm vi bộ script này.

**Cài xong nên tắt lại quyền** "Cài đặt ứng dụng không xác định" cho trình duyệt/Zalo
để tránh app lạ tự cài. Quyền này không ảnh hưởng các app đã cài.

---

## 6. Cần gửi gì nếu vẫn chưa sửa được?

Chạy `kiem_tra_may.bat` và gửi lại 3 thứ:
1. File `log_kiem_tra_may.txt` (tự sinh ra cạnh file .bat),
2. Ảnh chụp **nguyên văn thông báo lỗi** lúc cài trên máy,
3. Tên app + nơi bạn tải file APK (link càng tốt).

Có 3 thứ đó mới khoanh đúng bạn đang dính nguyên nhân số mấy ở §2 — thiếu chúng thì
mọi hướng dẫn chỉ là đoán.

## Nguồn tham khảo
- Lenovo Trung Quốc — *Tiểu Tân PAD: các vấn đề cài đặt phần mềm thường gặp* (hướng dẫn bật 安装未知应用 chính thức): https://iknow.lenovo.com.cn/detail/196528
- Android SDK Platform-Tools (ADB chính chủ Google): https://developer.android.com/tools/releases/platform-tools
