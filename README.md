# Tool Đăng Video YouTube

Ứng dụng **YouTube Upload Tool**: giao diện web Flask + module đăng video lên YouTube Studio bằng Selenium (Chrome).

## Cấu trúc

```
tool_dang_video/
├── app.py                 # Ứng dụng Flask (API + giao diện)
├── tooldangvideo.py       # Module upload video lên YouTube Studio (Selenium)
├── requirements.txt       # Dependencies
├── templates/
│   ├── index.html         # Trang chính (cấu hình + hướng dẫn)
│   └── select_account.html # Trang chọn tài khoản (profile Chrome)
├── static/
│   ├── css/style.css
│   └── js/main.js
├── output/                # Thư mục lưu file Excel kết quả (tự tạo khi chạy)
├── chrome_youtube_profiles/  # Profile Chrome theo tài khoản (tự tạo)
└── README.md
```

## Cài đặt

```bash
cd tool_dang_video
pip install -r requirements.txt
```

**Yêu cầu:** Chrome (64-bit) và ChromeDriver (Selenium 4 có thể tự tải driver).

## Chạy ứng dụng

```bash
python app.py
```

Mở trình duyệt tại: **http://127.0.0.1:5000**

## Đóng gói thành file EXE (chạy không cần cài Python)

File EXE được tạo trên **máy Windows có Python**, bằng script **`tool_dang_video/build_exe.bat`**. Máy người dùng cuối chỉ cần file `.exe` và Chrome, không cần cài Python.

### Điều kiện trước khi build

- **Windows** (script `.bat` chỉ dùng trên Windows).
- **Python 3** đã cài và lệnh `python` / `pip` chạy được trong **Command Prompt** hoặc **PowerShell** (Python được thêm vào PATH khi cài).
- Đã cài dependency của project (một lần):

  ```bash
  cd tool_dang_video
  pip install -r requirements.txt
  ```

### Cách xuất file EXE bằng `build_exe.bat` (khuyên dùng)

1. Mở thư mục **`tool_dang_video`** trong File Explorer (ví dụ: `D:\code\ToolUploadYoutube-main\tool_dang_video`).
2. **Double-click** file **`build_exe.bat`**.  
   - Cửa sổ console (đen) sẽ mở, hiện tiến trình đóng gói.  
   - Script tự `cd` vào đúng thư mục chứa `.bat` (dù bạn mở từ đâu), nên **không cần** tự `cd` trước.
3. Script sẽ:
   - Đặt mã UTF-8 (`chcp 65001`) để tránh lỗi font tiếng Việt trên console.
   - Cài **PyInstaller** nếu máy chưa có (`pip install pyinstaller`).
   - Chạy: `pyinstaller --noconfirm YouTubeUploadTool.spec`
4. Đợi đến khi thấy dòng **Build xong** và đường dẫn file exe.
5. Bấm một phím bất kỳ (nếu có `pause`) để đóng cửa sổ.

**File exe nằm tại:** `tool_dang_video/dist/YouTubeUploadTool.exe` (cùng cấp với thư mục `build/`).

### Build qua Command Prompt (cmd) — hướng dẫn chi tiết

**Đường dẫn thư mục build trên máy bạn (clone repo này):**  
`D:\code\ToolUploadYoutube-main\tool_dang_video`

Dùng **Command Prompt** (cmd), không bắt buộc dùng PowerShell. Các lệnh dưới đây gõ từng dòng rồi Enter.

#### Bước 1: Mở cmd

- Nhấn **Win + R**, gõ `cmd`, Enter; hoặc  
- Gõ **cmd** vào ô tìm kiếm Windows, mở **Command Prompt**; hoặc  
- Trong File Explorer, vào thư mục `tool_dang_video`, click vào thanh địa chỉ, gõ `cmd`, Enter — cửa sổ cmd sẽ mở **sẵn đúng thư mục đó** (khi đó có thể bỏ qua Bước 2 nếu đã đứng trong `tool_dang_video`).

#### Bước 2: Vào thư mục chứa project

Thư mục build **bắt buộc** là `tool_dang_video` (nơi có `app.py`, `YouTubeUploadTool.spec`, `build_exe.bat`).

- Nếu project nằm ở ổ khác ổ hệ thống (ví dụ ổ **D:**), **đổi ổ trước**, rồi `cd`:

  ```bat
  D:
  cd /d D:\code\ToolUploadYoutube-main\tool_dang_video
  ```

- `cd /d` dùng khi cần **đổi cả ổ đĩa và thư mục** trong một lệnh (trên cmd là cần thiết).

- Kiểm tra đã đúng chỗ (phải thấy các file `app.py`, `build_exe.bat`):

  ```bat
  dir app.py
  dir build_exe.bat
  ```

#### Bước 3: Kiểm tra Python và pip

```bat
python --version
pip --version
```

- Nếu báo **không nhận lệnh `python`**, thử **Python Launcher** (thường có khi cài Python từ python.org):

  ```bat
  py --version
  py -m pip --version
  ```

  Khi đó các lệnh `pip ...` bên dưới thay bằng `py -m pip ...` (ví dụ `py -m pip install -r requirements.txt`).

#### Bước 4: Cài dependency của tool (một lần hoặc khi đổi `requirements.txt`)

```bat
pip install -r requirements.txt
```

(Hoặc `py -m pip install -r requirements.txt` nếu bạn dùng `py`.)

#### Bước 5A — Build bằng file `.bat` (giống double-click)

Vẫn đang ở trong `tool_dang_video`:

```bat
build_exe.bat
```

Hoặc gọi đường dẫn đầy đủ nếu cmd đang ở chỗ khác:

```bat
cd /d D:\code\ToolUploadYoutube-main\tool_dang_video
build_exe.bat
```

Script sẽ tự cài PyInstaller nếu thiếu và chạy PyInstaller theo `YouTubeUploadTool.spec`.

#### Bước 5B — Build **thủ công** bằng lệnh (không dùng `.bat`)

Luôn trong thư mục `tool_dang_video`:

```bat
chcp 65001
pip install pyinstaller
pyinstaller --noconfirm YouTubeUploadTool.spec
```

- `chcp 65001`: UTF-8 trên console (tiếng Việt ít bị lỗi font khi build in log).  
- `--noconfirm`: ghi đè bản build cũ trong `build/` và `dist/` không hỏi lại.

Nếu dùng `py`:

```bat
chcp 65001
py -m pip install pyinstaller
py -m PyInstaller --noconfirm YouTubeUploadTool.spec
```

#### Bước 6: Lấy file exe

Sau khi build thành công:

```bat
dir dist\YouTubeUploadTool.exe
```

File nằm tại: **`tool_dang_video\dist\YouTubeUploadTool.exe`**. Có thể mở thư mục `dist` bằng Explorer:

```bat
explorer dist
```

### Nếu build thất bại

- Đọc lỗi in ra ngay trong cửa sổ console (thiếu module, không tìm thấy `pyinstaller`, v.v.).
- Kiểm tra đã chạy `pip install -r requirements.txt` trong **`tool_dang_video`**.
- Thử cài tay PyInstaller: `pip install pyinstaller`, rồi chạy lại `build_exe.bat` hoặc lại lệnh `pyinstaller ...`.
- Nếu **“python không phải lệnh…”**: cài lại Python và tick **Add Python to PATH**, hoặc dùng `py -m pip` / `py -m PyInstaller` như trên.

### Sau khi có file EXE

Copy **`YouTubeUploadTool.exe`** sang máy khác (không cần Python). Trên máy đó chỉ cần **cài Chrome**. Double-click exe: cửa sổ console hiện log, trình duyệt thường tự mở **http://127.0.0.1:5000**. Thư mục **profile Chrome**, **file Excel**, **`temp_uploads`**, và **`debug_logs`** (log lỗi gửi dev) được tạo **cùng thư mục với file exe**.

## Quy trình sử dụng

1. **Chọn folder** chứa video (mp4, mov, mkv, …).
2. **Cấu hình:** Made for kids (Có/Không), Visibility (Riêng tư / Không công khai / Công khai), tên file Excel.
3. **Bắt đầu Upload** → chuyển sang trang **chọn tài khoản** (profile Chrome). Chọn profile để dùng; lần đầu có thể đăng nhập YouTube trong cửa sổ Chrome do tool mở.
4. **Theo dõi** tiến trình và log. Tool upload theo lô tối đa **15 video/lần** rồi xử lý từng video trong Studio.
5. **Tải kết quả:** dùng **Tải Excel** (link + trạng thái) và **Tải Log** (log phiên upload) khi cần debug.

## Chức năng chính

- **Nhiều tài khoản:** Mỗi tài khoản = một profile Chrome (`chrome_youtube_profiles/profile_1`, `profile_2`, …). Có thể lưu email/mật khẩu để tự đăng nhập.
- **Upload tự động:** Chọn Made for kids, Visibility; tool tự thao tác trên YouTube Studio (kiểm tra bản quyền, thay thế nhạc nếu có, chế độ hiển thị, nút Lưu/Xuất bản).
- **Excel realtime:** Cột STT, Tên file, Link YouTube, Thời gian, Trạng thái (SUCCESS/FAIL/ERROR); ghi ngay sau mỗi video, không đợi hết batch.
- **Log phiên upload:** Mỗi phiên tạo file `debug_logs/upload-session-YYYYMMDD-HHMMSS.log`; có API tải log `GET /api/download-upload-log` và nút **Tải Log** trên giao diện.
- **Thông báo từ xa:** Có thể đẩy thông báo (update, vá lỗi, donate, Telegram…) tới tất cả máy đang dùng tool qua file JSON trên GitHub Raw / Gist (xem mục dưới).

## Thông báo từ xa (GitHub Raw / Gist)

Để hiển thị thông báo cho mọi người dùng tool (update, vá lỗi, link donate/Telegram…):

1. Tạo file `notice.json` trên GitHub (repo public) hoặc [Gist](https://gist.github.com). Định dạng mẫu (xem `notice.example.json`):

   ```json
   {
     "version": 1,
     "title": "Thông báo từ nhà phát triển",
     "message": "Nội dung thông báo...",
     "link": "https://t.me/Sieucapdeptrai03",
     "linkText": "Liên hệ Telegram"
   }
   ```

2. Lấy **Raw URL** (GitHub: nút Raw → copy URL; Gist: Raw → copy URL).

3. Trong `app.py` đặt biến `NOTICE_JSON_URL` bằng URL đó, hoặc set biến môi trường khi chạy:
   ```bash
   set NOTICE_JSON_URL=https://raw.githubusercontent.com/user/repo/main/notice.json
   python app.py
   ```
   (Trên Linux/macOS dùng `export NOTICE_JSON_URL=...`.)

4. Mỗi lần mở trang chủ, tool sẽ gọi URL và hiển thị banner nếu có thông báo mới (so với `version` đã xem). Chỉ cần sửa file trên GitHub là tất cả máy dùng exe sẽ nhận thông báo mới.

## Lưu thông tin đăng nhập

- **Profile Chrome** nằm tại: `chrome_youtube_profiles/profile_<id>/` (cùng thư mục với `app.py`). Không xóa nếu muốn giữ phiên đăng nhập.
- **Lần đầu:** Cửa sổ Chrome do tool mở → đăng nhập YouTube (mail của bạn) → trên giao diện tool bấm "Tiếp tục (Sau khi đăng nhập)".
- **Lần sau:** Chọn tài khoản (profile) → Chrome mở với profile đã lưu, đã đăng nhập sẵn; có thể lưu email/mật khẩu trong trang chọn tài khoản để tool tự điền khi cần.

## Lưu ý

- Lần đầu cần đăng nhập YouTube trong cửa sổ Chrome do tool mở; sau đó bấm "Tiếp tục (Sau khi đăng nhập)" trên giao diện.
- Khi chạy tool, không mở thêm Chrome khác dùng cùng profile (một lúc chỉ một Chrome với profile đó).
- YouTube có thể đổi giao diện Studio; nếu upload lỗi, có thể cần cập nhật selector trong `tooldangvideo.py`.
- Chức năng **Dừng** đã tắt khỏi giao diện; nếu cần dừng, đóng app/terminal chạy `python app.py`.
