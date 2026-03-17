from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import os
import sys
import time
import threading
import queue
import json
import shutil
import urllib.request
import urllib.error
from datetime import datetime
from werkzeug.utils import secure_filename
import tooldangvideo

# URL file thông báo từ xa (GitHub Raw hoặc Gist).
NOTICE_JSON_URL = "https://raw.githubusercontent.com/bnalucnamconfessions/ToolUploadYoutube/main/notice.json"

# Khi chạy từ file .exe (PyInstaller), đặt thư mục làm việc = thư mục chứa exe
# để chrome_youtube_profiles, file Excel, temp nằm cạnh exe.
if getattr(sys, "frozen", False):
    os.chdir(os.path.dirname(sys.executable))

def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)

# Setup Flask app
template_folder = resource_path('templates')
static_folder = resource_path('static')

app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
CORS(app)

# Global variables for upload management
upload_queue = queue.Queue()
upload_status = {
    'is_running': False,
    'should_stop': False,
    'total_files': 0,
    'current_file': '',
    'success_count': 0,
    'fail_count': 0,
    'progress': 0,
    'logs': [],
    'excel_file': None,
    'waiting_for_login': False
}
login_event = threading.Event()
upload_thread = None
upload_driver = None

PROFILES_BASE_DIR = os.path.join(os.getcwd(), "chrome_youtube_profiles")
PROFILES_META_PATH = os.path.join(PROFILES_BASE_DIR, "profiles.json")

def _load_profiles_meta():
    try:
        if os.path.exists(PROFILES_META_PATH):
            with open(PROFILES_META_PATH, "r", encoding="utf-8") as f:
                return json.load(f) or {}
    except Exception:
        pass
    return {}

def _save_profiles_meta(meta):
    os.makedirs(PROFILES_BASE_DIR, exist_ok=True)
    with open(PROFILES_META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

def _profile_dir_for_account(account_id: int):
    return os.path.join(PROFILES_BASE_DIR, f"profile_{account_id}")


def _mask_email(email):
    """Che giấu email để hiển thị (vd: ab***@gmail.com)."""
    if not email or "@" not in str(email):
        return ""
    s = str(email).strip()
    at = s.index("@")
    if at <= 2:
        return "***" + s[at:]
    return s[:2] + "***" + s[at:]


def _list_accounts():
    os.makedirs(PROFILES_BASE_DIR, exist_ok=True)
    meta = _load_profiles_meta()
    accounts = []
    for name in sorted(os.listdir(PROFILES_BASE_DIR)):
        if not name.startswith("profile_"):
            continue
        try:
            account_id = int(name.split("_", 1)[1])
        except Exception:
            continue
        pdir = os.path.join(PROFILES_BASE_DIR, name)
        if os.path.isdir(pdir):
            info = meta.get(str(account_id), {})
            label = info.get("label") or f"Tài khoản {account_id}"
            email = info.get("email") or ""
            password = info.get("password") or ""
            has_credentials = bool(email and password)
            accounts.append({
                "id": account_id,
                "label": label,
                "has_credentials": has_credentials,
                "email": email,
                "email_masked": _mask_email(email) if email else ""
            })
    return accounts

def log_callback(message):
    """Callback function for logging"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    upload_status['logs'].append({
        'timestamp': timestamp,
        'message': message
    })
    # Keep only last 1000 logs
    if len(upload_status['logs']) > 1000:
        upload_status['logs'] = upload_status['logs'][-1000:]

def run_upload():
    """Main upload function running in separate thread"""
    global upload_driver, upload_status
    
    try:
        while not upload_queue.empty() and not upload_status['should_stop']:
            file_info = upload_queue.get()
            file_path = file_info['path']
            video_title = file_info.get('title', 'tool')
            # Chuẩn hóa theo form: input name="made_for_kids" value="yes"|"no" (chỉ dùng đúng giá trị đã pick)
            _raw_kids = (file_info.get('made_for_kids') or 'no').strip().lower()
            made_for_kids = 'yes' if _raw_kids in ('yes', 'true', '1') else 'no'
            visibility = file_info.get('visibility', 'unlisted')

            # #region agent log — truy vết Made for kids khi chọn Có (yes)
            try:
                tooldangvideo._agent_debug_log(
                    "K0",
                    "run_upload made_for_kids before upload_video",
                    {"file_info_raw": file_info.get("made_for_kids"), "normalized": made_for_kids, "pass_bool": (made_for_kids == "yes")},
                    run_id="run_upload_kids",
                )
            except Exception:
                pass
            # #endregion agent log

            upload_status['current_file'] = os.path.basename(file_path)
            log_callback(f'Đang upload: {os.path.basename(file_path)}')
            
            try:
                # Wait for login if needed
                if upload_status['waiting_for_login']:
                    try:
                        tooldangvideo._dbg("WL1", "run_upload waiting_for_login true", {"current_file": os.path.basename(file_path)}, run_id="login_wait")
                    except Exception:
                        pass
                    log_callback('Đang chờ đăng nhập...')
                    login_event.wait()
                    login_event.clear()
                    upload_status['waiting_for_login'] = False
                
                # Initialize driver if not exists
                if upload_driver is None:
                    log_callback('Đang khởi tạo trình duyệt...')
                    profile_dir = upload_status.get('profile_dir')
                    upload_driver = tooldangvideo.init_driver(profile_dir=profile_dir)
                    log_callback('Đã khởi tạo trình duyệt thành công')
                    account_id = upload_status.get('account_id')
                    if account_id is not None:
                        meta = _load_profiles_meta()
                        info = meta.get(str(account_id), {})
                        email = (info.get("email") or "").strip()
                        password = info.get("password") or ""
                        if email and password:
                            tooldangvideo.ensure_youtube_login(upload_driver, email, password, log_callback)
                            time.sleep(2)
                
                # Callback: khi có link (trước hoặc sau bấm Lưu) — log Link + cập nhật Excel ngay
                excel_filename = file_info.get('excel_filename', 'YouTube_Upload_Links.xlsx')
                def on_link_available(url):
                    if not url or url == "N/A":
                        return
                    log_callback(f'Link: {url}')
                    p = tooldangvideo.append_excel_row(
                        file_name=os.path.basename(file_path),
                        url=(url if (url and url != "N/A") else ""),
                        status="SUCCESS",
                        excel_filename=excel_filename,
                        log_callback=log_callback
                    )
                    if p and os.path.exists(p):
                        upload_status['excel_file'] = p
                        log_callback(f'📄 Đã cập nhật Excel: {p}')

                # Upload video
                result = tooldangvideo.upload_video(
                    driver=upload_driver,
                    file_path=file_path,
                    video_title=video_title,
                    made_for_kids=(made_for_kids == 'yes'),
                    visibility=visibility,
                    log_callback=log_callback,
                    on_link_available=on_link_available
                )
                
                if result and result.get('success'):
                    upload_status['success_count'] += 1
                    log_callback(f'✅ Upload thành công: {os.path.basename(file_path)}')
                    if not result.get('excel_done'):
                        if result.get("url"):
                            log_callback(f'Link: {result.get("url")}')
                        try:
                            url = result.get("url")
                            if url and url != "N/A":
                                excel_path = tooldangvideo.append_excel_row(
                                    file_name=os.path.basename(file_path),
                                    url=url,
                                    status="SUCCESS",
                                    excel_filename=excel_filename,
                                    log_callback=log_callback
                                )
                                if excel_path and os.path.exists(excel_path):
                                    upload_status['excel_file'] = excel_path
                                    log_callback(f'📄 Đã cập nhật Excel: {excel_path}')
                        except Exception as e:
                            log_callback(f'⚠️ Lỗi khi cập nhật Excel realtime: {str(e)}')
                    else:
                        if result.get("url"):
                            log_callback(f'Link: {result.get("url")}')
                        if upload_status.get('excel_file') and os.path.exists(upload_status['excel_file']):
                            log_callback(f'📄 Excel đã được cập nhật realtime: {upload_status["excel_file"]}')
                else:
                    upload_status['fail_count'] += 1
                    log_callback(f'❌ Upload thất bại: {os.path.basename(file_path)}')
                    if result and result.get('error'):
                        log_callback(f'Lỗi: {result["error"]}')
                    # Ghi dần trạng thái thất bại ra Excel (không cần đợi hết batch)
                    try:
                        excel_filename = file_info.get('excel_filename', 'YouTube_Upload_Links.xlsx')
                        excel_path = tooldangvideo.append_excel_row(
                            file_name=os.path.basename(file_path),
                            url="",
                            status="FAIL",
                            excel_filename=excel_filename,
                            log_callback=log_callback
                        )
                        if excel_path and os.path.exists(excel_path):
                            upload_status['excel_file'] = excel_path
                    except Exception as e:
                        log_callback(f'⚠️ Lỗi khi cập nhật Excel realtime (FAIL): {str(e)}')
                
            except Exception as e:
                upload_status['fail_count'] += 1
                log_callback(f'❌ Lỗi khi upload {os.path.basename(file_path)}: {str(e)}')
                import traceback
                log_callback(traceback.format_exc())
                # Ghi dần trạng thái lỗi ra Excel để không mất tiến độ
                try:
                    excel_filename = file_info.get('excel_filename', 'YouTube_Upload_Links.xlsx')
                    excel_path = tooldangvideo.append_excel_row(
                        file_name=os.path.basename(file_path),
                        url="",
                        status="ERROR",
                        excel_filename=excel_filename,
                        log_callback=log_callback
                    )
                    if excel_path and os.path.exists(excel_path):
                        upload_status['excel_file'] = excel_path
                except Exception as e2:
                    log_callback(f'⚠️ Lỗi khi cập nhật Excel realtime (ERROR): {str(e2)}')
            
            # Update progress
            processed = upload_status['success_count'] + upload_status['fail_count']
            if upload_status['total_files'] > 0:
                upload_status['progress'] = int((processed / upload_status['total_files']) * 100)
            
            upload_queue.task_done()
        
        # Generate Excel file after all uploads
        if upload_status['success_count'] > 0 or upload_status['fail_count'] > 0:
            try:
                excel_filename = file_info.get('excel_filename', 'YouTube_Upload_Links.xlsx')
                # Nếu đã ghi Excel realtime trong quá trình chạy thì không ghi đè lại bằng generate_excel()
                if upload_status.get('excel_file') and os.path.exists(upload_status['excel_file']):
                    log_callback(f'📄 Excel đã được cập nhật realtime: {upload_status["excel_file"]}')
                else:
                    excel_path = tooldangvideo.generate_excel(
                        upload_status['logs'],
                        excel_filename,
                        log_callback=log_callback
                    )
                    if excel_path and os.path.exists(excel_path):
                        upload_status['excel_file'] = excel_path
                        log_callback(f'✅ Đã tạo file Excel: {excel_path}')
            except Exception as e:
                log_callback(f'⚠️ Lỗi khi tạo file Excel: {str(e)}')
        
        # Cleanup
        if upload_driver:
            try:
                upload_driver.quit()
            except:
                pass
            upload_driver = None
        
        upload_status['is_running'] = False
        log_callback('Hoàn thành upload!')
        
    except Exception as e:
        log_callback(f'❌ Lỗi trong quá trình upload: {str(e)}')
        import traceback
        log_callback(traceback.format_exc())
        upload_status['is_running'] = False

def _fetch_notice_json(url):
    """Tải và parse JSON từ url. Trả về (data, None) nếu OK, (None, error_string) nếu lỗi."""
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "YouTubeUploadTool/1.0", "Cache-Control": "no-cache"},
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return (data, None)
    except urllib.error.HTTPError as e:
        return (None, str(e))
    except Exception as e:
        return (None, str(e))


@app.route('/api/notice', methods=['GET'])
def api_notice():
    """Lấy thông báo từ xa (GitHub Raw / Gist). Trả về JSON { success, notice }."""
    if not (NOTICE_JSON_URL and NOTICE_JSON_URL.strip()):
        return jsonify({"success": False, "notice": None})
    base_url = NOTICE_JSON_URL.strip()
    bust = str(int(time.time() * 1000))
    url = (base_url + ("&" if "?" in base_url else "?") + "_=" + bust)

    data, err = _fetch_notice_json(url)
    # Nếu 404, thử đường dẫn trong thư mục tool_dang_video (repo có thể để notice.json trong subfolder)
    if data is None and err and "404" in err:
        if "/notice.json" in base_url and "tool_dang_video" not in base_url:
            alt_base = base_url.replace("/notice.json", "/tool_dang_video/notice.json")
            alt_url = (alt_base + ("&" if "?" in alt_base else "?") + "_=" + bust)
            data, err = _fetch_notice_json(alt_url)
    if data is None:
        print("[api/notice] Lỗi:", err, file=sys.stderr)
        return jsonify({"success": False, "notice": None, "error": err or "Unknown"})

    response = jsonify({"success": True, "notice": data})
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/select-account')
def select_account():
    """Account selection page (Chrome profiles)"""
    return render_template('select_account.html')

@app.route('/api/accounts', methods=['GET'])
def api_list_accounts():
    try:
        return jsonify({"success": True, "accounts": _list_accounts()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/accounts/create', methods=['POST'])
def api_create_account():
    try:
        accounts = _list_accounts()
        next_id = (max([a["id"] for a in accounts]) + 1) if accounts else 1
        pdir = _profile_dir_for_account(next_id)
        os.makedirs(pdir, exist_ok=True)

        meta = _load_profiles_meta()
        meta[str(next_id)] = meta.get(str(next_id), {})
        meta[str(next_id)]["label"] = meta[str(next_id)].get("label") or f"Tài khoản {next_id}"
        _save_profiles_meta(meta)
        return jsonify({"success": True, "account": {"id": next_id, "label": meta[str(next_id)]["label"]}})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/accounts/rename', methods=['POST'])
def api_rename_account():
    try:
        data = request.json or {}
        account_id = int(data.get("account_id"))
        label = (data.get("label") or "").strip()
        if not label:
            return jsonify({"success": False, "error": "Label không hợp lệ"}), 400
        pdir = _profile_dir_for_account(account_id)
        if not os.path.isdir(pdir):
            return jsonify({"success": False, "error": "Tài khoản không tồn tại"}), 404
        meta = _load_profiles_meta()
        meta[str(account_id)] = meta.get(str(account_id), {})
        meta[str(account_id)]["label"] = label
        _save_profiles_meta(meta)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/accounts/delete', methods=['POST'])
def api_delete_account():
    """Xóa tài khoản (profile Chrome): xóa thư mục profile và mục trong meta."""
    try:
        data = request.json or {}
        account_id = data.get("account_id")
        if account_id is None:
            return jsonify({"success": False, "error": "Thiếu account_id"}), 400
        account_id = int(account_id)
        pdir = _profile_dir_for_account(account_id)
        if not os.path.isdir(pdir):
            return jsonify({"success": False, "error": "Tài khoản không tồn tại"}), 404
        meta = _load_profiles_meta()
        meta.pop(str(account_id), None)
        _save_profiles_meta(meta)
        shutil.rmtree(pdir, ignore_errors=True)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/accounts/set-credentials', methods=['POST'])
def api_set_credentials():
    """Lưu email và mật khẩu cho profile (để tự động đăng nhập YouTube khi mở Chrome)."""
    try:
        data = request.json or {}
        account_id = data.get("account_id")
        if account_id is None:
            return jsonify({"success": False, "error": "Thiếu account_id"}), 400
        account_id = int(account_id)
        email = (data.get("email") or "").strip()
        password = data.get("password") or ""
        pdir = _profile_dir_for_account(account_id)
        if not os.path.isdir(pdir):
            return jsonify({"success": False, "error": "Tài khoản không tồn tại"}), 404
        meta = _load_profiles_meta()
        meta[str(account_id)] = meta.get(str(account_id), {})
        if email:
            meta[str(account_id)]["email"] = email
        if password:
            meta[str(account_id)]["password"] = password
        _save_profiles_meta(meta)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/upload-files', methods=['POST'])
def upload_files():
    """Handle file uploads"""
    try:
        if 'files[]' not in request.files:
            return jsonify({'error': 'No files provided'}), 400
        
        files = request.files.getlist('files[]')
        if not files or files[0].filename == '':
            return jsonify({'error': 'No files selected'}), 400
        
        # Create temp directory và xoá video cũ trong đó, chỉ giữ batch mới vừa chọn
        temp_dir = os.path.join(os.getcwd(), 'temp_uploads')
        os.makedirs(temp_dir, exist_ok=True)
        for name in os.listdir(temp_dir):
            path = os.path.join(temp_dir, name)
            try:
                if os.path.isfile(path):
                    os.remove(path)
            except Exception:
                pass
        
        uploaded_files = []
        for file in files:
            if file.filename:
                filename = secure_filename(file.filename)
                file_path = os.path.join(temp_dir, filename)
                file.save(file_path)
                uploaded_files.append(filename)
        
        return jsonify({
            'success': True,
            'folder': temp_dir,
            'files': uploaded_files
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/start-upload', methods=['POST'])
def start_upload():
    """Start upload process"""
    global upload_thread, upload_status, upload_queue
    
    try:
        data = request.json
        account_id = data.get('account_id')
        folder = data.get('folder')
        video_title = (data.get('video_title') or '').strip()
        _raw_kids = data.get('made_for_kids', 'no')
        made_for_kids = 'yes' if str(_raw_kids).strip().lower() in ('yes', 'true', '1') else 'no'
        visibility = data.get('visibility', 'unlisted')
        excel_filename = data.get('excel_filename', 'YouTube_Upload_Links.xlsx')

        # #region agent log — kiểm tra giá trị Made for kids nhận từ client
        try:
            tooldangvideo._agent_debug_log(
                "A1",
                "start_upload received made_for_kids",
                {"raw": _raw_kids, "normalized": made_for_kids},
                run_id="start_upload",
            )
        except Exception:
            pass
        # #endregion agent log

        if not account_id:
            return jsonify({'error': 'Vui lòng chọn tài khoản (profile Chrome) trước khi upload'}), 400
        try:
            account_id = int(account_id)
        except Exception:
            return jsonify({'error': 'account_id không hợp lệ'}), 400
        profile_dir = _profile_dir_for_account(account_id)
        os.makedirs(profile_dir, exist_ok=True)
        
        if not folder or not os.path.exists(folder):
            return jsonify({'error': 'Folder không tồn tại'}), 400
        
        # Reset status
        upload_status = {
            'is_running': True,
            'should_stop': False,
            'total_files': 0,
            'current_file': '',
            'success_count': 0,
            'fail_count': 0,
            'progress': 0,
            'logs': [],
            'excel_file': None,
            'waiting_for_login': False,
            'account_id': account_id,
            'profile_dir': profile_dir
        }
        
        # Get video files
        video_extensions = ['.mp4', '.mov', '.mkv', '.avi', '.wmv', '.flv', '.webm']
        video_files = []
        for file in os.listdir(folder):
            if any(file.lower().endswith(ext) for ext in video_extensions):
                video_files.append(os.path.join(folder, file))
        
        if not video_files:
            return jsonify({'error': 'Không tìm thấy file video nào'}), 400
        
        # Clear queue then add files to queue
        upload_queue = queue.Queue()
        for file_path in video_files:
            upload_queue.put({
                'path': file_path,
                'title': video_title,
                'made_for_kids': made_for_kids,
                'visibility': visibility,
                'excel_filename': excel_filename
            })
        
        upload_status['total_files'] = len(video_files)
        log_callback(f'Bắt đầu upload {len(video_files)} video(s)')

        # Khởi tạo file Excel ngay khi bắt đầu batch (đảm bảo có cột Trạng thái)
        try:
            excel_path = tooldangvideo.ensure_excel_initialized(excel_filename, log_callback=log_callback)
            if excel_path and os.path.exists(excel_path):
                upload_status['excel_file'] = excel_path
        except Exception as e:
            log_callback(f'⚠️ Lỗi khi khởi tạo Excel: {str(e)}')
        
        # Start upload thread
        upload_thread = threading.Thread(target=run_upload, daemon=True)
        upload_thread.start()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/status', methods=['GET'])
def get_status():
    """Get upload status"""
    return jsonify(upload_status)

@app.route('/api/continue-login', methods=['POST'])
def continue_login():
    """Continue after login"""
    global login_event
    login_event.set()
    upload_status['waiting_for_login'] = False
    return jsonify({'success': True})

@app.route('/api/stop-upload', methods=['POST'])
def stop_upload():
    """Stop upload process"""
    global upload_status
    upload_status['should_stop'] = True
    upload_status['is_running'] = False
    return jsonify({'success': True})

@app.route('/api/download-excel', methods=['GET'])
def download_excel():
    """Download Excel file"""
    if not upload_status.get('excel_file') or not os.path.exists(upload_status['excel_file']):
        return jsonify({'error': 'File Excel không tồn tại'}), 404
    
    return send_file(
        upload_status['excel_file'],
        as_attachment=True,
        download_name=os.path.basename(upload_status['excel_file'])
    )

def open_browser():
    """Open browser automatically"""
    import webbrowser
    import time
    time.sleep(1.5)
    webbrowser.open('http://127.0.0.1:5000')

if __name__ == '__main__':
    try:
        # Open browser in separate thread
        browser_thread = threading.Thread(target=open_browser, daemon=True)
        browser_thread.start()
        
        # Run Flask app
        app.run(host='127.0.0.1', port=5000, debug=False)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        input("Press Enter to exit...")
