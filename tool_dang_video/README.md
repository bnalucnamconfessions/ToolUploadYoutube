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

## Quy trình sử dụng

1. **Chọn folder** chứa video (mp4, mov, mkv, …).
2. **Cấu hình:** tiêu đề (tùy chọn), Made for kids (Có/Không), Visibility (Riêng tư / Không công khai / Công khai), tên file Excel.
3. **Bắt đầu Upload** → chuyển sang trang **chọn tài khoản** (profile Chrome). Chọn profile để dùng; lần đầu có thể đăng nhập YouTube trong cửa sổ Chrome do tool mở.
4. **Theo dõi** tiến trình và log. File Excel được cập nhật **realtime** (link + trạng thái) sau mỗi video.
5. **Tải Excel** khi cần (có thể tải bất kỳ lúc nào, không cần đợi hết batch).

## Chức năng chính

- **Nhiều tài khoản:** Mỗi tài khoản = một profile Chrome (`chrome_youtube_profiles/profile_1`, `profile_2`, …). Có thể lưu email/mật khẩu để tự đăng nhập.
- **Upload tự động:** Điền tiêu đề, chọn Made for kids, Visibility; tool tự thao tác trên YouTube Studio (kiểm tra bản quyền, thay thế nhạc nếu có, chế độ hiển thị, nút Lưu/Xuất bản).
- **Excel realtime:** Cột STT, Tên file, Link YouTube, Thời gian, Trạng thái (SUCCESS/FAIL/ERROR); ghi ngay sau mỗi video, không đợi hết batch.
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
