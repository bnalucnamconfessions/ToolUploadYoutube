import os
import sys

# Phải chạy TRƯỚC import tooldangvideo: cwd = thư mục chứa exe → log/debug cùng chỗ với profile Chrome.
if getattr(sys, "frozen", False):
    os.chdir(os.path.dirname(sys.executable))

DEBUG_DIR = os.path.join(os.getcwd(), "debug_logs")
try:
    os.makedirs(DEBUG_DIR, exist_ok=True)
except OSError:
    pass

from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import time
import threading
import queue
import json
import shutil
import urllib.request
import urllib.error
import traceback
from datetime import datetime
from werkzeug.utils import secure_filename
import tooldangvideo
from profile_secrets import decrypt_password, encrypt_password

tooldangvideo.configure_debug_dir(DEBUG_DIR)

# Ghi file hướng dẫn một lần (đặc biệt hữu ích khi user chỉ có file .exe)
try:
    _readme_debug = os.path.join(DEBUG_DIR, "HUONG_DAN_DEBUG.txt")
    if not os.path.isfile(_readme_debug):
        with open(_readme_debug, "w", encoding="utf-8") as _rf:
            _rf.write(
                "Thư mục debug_logs — tự tạo cạnh YouTubeUploadTool.exe (hoặc thư mục chạy python).\n\n"
                "- console.log        : Sao chép cửa sổ console khi chạy bản .exe.\n"
                "- crash.log          : Lỗi không bắt được + lỗi trong luồng upload (traceback).\n"
                "- debug-57c0c7.log   : Sự kiện upload / Studio (mỗi dòng một JSON).\n"
                "- debug-speed.ndjson : Chi tiết bước (chỉ khi YTB_DEBUG_NDJSON=1).\n"
            )
except OSError:
    pass

# URL file thông báo từ xa (GitHub Raw hoặc Gist).
NOTICE_JSON_URL = "https://raw.githubusercontent.com/bnalucnamconfessions/ToolUploadYoutube/main/notice.json"

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
upload_session_log_file = None

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


def _clear_profile_google_cookies(pdir):
    """
    Xóa file cookie của Chrome trong profile (ép đăng nhập lại Google).
    Phải đóng mọi Chrome đang dùng profile này (kể cả do tool mở).
    Trả về (True, None) hoặc (False, thông báo lỗi).
    """
    paths = [
        os.path.join(pdir, "Default", "Cookies"),
        os.path.join(pdir, "Default", "Cookies-journal"),
        os.path.join(pdir, "Default", "Network", "Cookies"),
        os.path.join(pdir, "Default", "Network", "Cookies-journal"),
    ]
    errors = []
    for p in paths:
        try:
            if os.path.isfile(p):
                os.remove(p)
        except OSError as e:
            errors.append(f"{os.path.basename(p)}: {e}")
    if errors:
        return False, "Không xóa được một số file (thường do Chrome còn mở): " + "; ".join(errors)
    return True, None


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

def _append_upload_session_log(timestamp: str, message: str):
    """Ghi log phiên upload ra file text để debug sau khi chạy."""
    global upload_session_log_file
    if not upload_session_log_file:
        return
    try:
        with open(upload_session_log_file, "a", encoding="utf-8", errors="replace") as f:
            f.write(f"{timestamp} | {message}\n")
    except Exception:
        pass

def log_callback(message):
    """Callback function for logging"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    upload_status['logs'].append({
        'timestamp': timestamp,
        'message': message
    })
    _append_upload_session_log(timestamp, str(message or ""))
    # Keep only last 1000 logs
    if len(upload_status['logs']) > 1000:
        upload_status['logs'] = upload_status['logs'][-1000:]

def run_upload():
    """Main upload function running in separate thread"""
    global upload_driver, upload_status
    
    last_excel_filename = 'YouTube_Upload_Links.xlsx'
    try:
        while not upload_queue.empty():
            job = upload_queue.get()
            batch_paths = job.get('batch_paths') or []
            if not batch_paths and job.get('path'):
                batch_paths = [job['path']]
            if not batch_paths:
                upload_queue.task_done()
                continue

            last_excel_filename = job.get('excel_filename', last_excel_filename)
            _raw_kids = (job.get('made_for_kids') or 'no').strip().lower()
            made_for_kids = 'yes' if _raw_kids in ('yes', 'true', '1') else 'no'
            visibility = job.get('visibility', 'unlisted')
            excel_filename = last_excel_filename

            try:
                tooldangvideo._agent_debug_log(
                    "K0",
                    "run_upload made_for_kids before batch",
                    {
                        "batch_n": len(batch_paths),
                        "file_info_raw": job.get("made_for_kids"),
                        "normalized": made_for_kids,
                        "pass_bool": (made_for_kids == "yes"),
                    },
                    run_id="run_upload_kids",
                )
            except Exception:
                pass

            n_batch = len(batch_paths)
            upload_status['current_file'] = (
                os.path.basename(batch_paths[0])
                if n_batch == 1
                else f"Lô {n_batch} video ({os.path.basename(batch_paths[0])} …)"
            )
            preview = "; ".join(os.path.basename(p) for p in batch_paths[:3])
            if n_batch > 3:
                preview += " …"
            log_callback(f"Đang xử lý lô {n_batch} video: {preview}")

            try:
                if upload_status['waiting_for_login']:
                    try:
                        tooldangvideo._dbg(
                            "WL1",
                            "run_upload waiting_for_login true",
                            {"batch_first": os.path.basename(batch_paths[0])},
                            run_id="login_wait",
                        )
                    except Exception:
                        pass
                    log_callback('Đang chờ đăng nhập...')
                    login_event.wait()
                    login_event.clear()
                    upload_status['waiting_for_login'] = False

                def _ensure_driver_ready():
                    global upload_driver
                    account_id = upload_status.get('account_id')
                    profile_dir = upload_status.get('profile_dir')

                    if upload_driver is not None:
                        try:
                            _ = upload_driver.current_url
                            return
                        except Exception:
                            log_callback('⚠️ Phiên trình duyệt cũ không còn hợp lệ, đang khởi tạo lại...')
                            try:
                                upload_driver.quit()
                            except Exception:
                                pass
                            upload_driver = None

                    log_callback('Đang khởi tạo trình duyệt...')
                    upload_driver = tooldangvideo.init_driver(profile_dir=profile_dir)
                    log_callback('Đã khởi tạo trình duyệt thành công')

                    if account_id is not None:
                        meta = _load_profiles_meta()
                        info = meta.get(str(account_id), {})
                        email = (info.get("email") or "").strip()
                        password = decrypt_password(info.get("password") or "")
                        if email and password:
                            tooldangvideo.ensure_youtube_login(upload_driver, email, password, log_callback)
                            time.sleep(2)

                _ensure_driver_ready()

                def on_link_per_file(fp, url):
                    if not url or url == "N/A":
                        return
                    log_callback(f'Link: {url}')
                    p = tooldangvideo.append_excel_row(
                        file_name=os.path.basename(fp),
                        url=url,
                        status="SUCCESS",
                        excel_filename=excel_filename,
                        log_callback=log_callback,
                    )
                    if p and os.path.exists(p):
                        upload_status['excel_file'] = p
                        log_callback(f'📄 Đã cập nhật Excel: {p}')

                try:
                    results = tooldangvideo.upload_videos_batch(
                        upload_driver,
                        batch_paths,
                        video_title="",
                        made_for_kids=(made_for_kids == 'yes'),
                        visibility=visibility,
                        log_callback=log_callback,
                        on_link_per_file=on_link_per_file,
                    )
                except Exception as e:
                    import traceback
                    log_callback(f'❌ Lỗi khi upload lô: {str(e)}')
                    log_callback(traceback.format_exc())
                    err = str(e)
                    results = [
                        {"success": False, "url": None, "error": err, "excel_done": False}
                        for _ in batch_paths
                    ]

                while len(results) < len(batch_paths):
                    results.append(
                        {
                            "success": False,
                            "url": None,
                            "error": "Thiếu kết quả lô",
                            "excel_done": False,
                        }
                    )

                for file_path, result in zip(batch_paths, results):
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
                                        log_callback=log_callback,
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
                        try:
                            excel_path = tooldangvideo.append_excel_row(
                                file_name=os.path.basename(file_path),
                                url="",
                                status="FAIL",
                                excel_filename=excel_filename,
                                log_callback=log_callback,
                            )
                            if excel_path and os.path.exists(excel_path):
                                upload_status['excel_file'] = excel_path
                        except Exception as e:
                            log_callback(f'⚠️ Lỗi khi cập nhật Excel realtime (FAIL): {str(e)}')

            except Exception as e:
                import traceback
                log_callback(f'❌ Lỗi không mong đợi trong lô: {str(e)}')
                log_callback(traceback.format_exc())
                for fp in batch_paths:
                    upload_status['fail_count'] += 1
                    try:
                        excel_path = tooldangvideo.append_excel_row(
                            file_name=os.path.basename(fp),
                            url="",
                            status="ERROR",
                            excel_filename=excel_filename,
                            log_callback=log_callback,
                        )
                        if excel_path and os.path.exists(excel_path):
                            upload_status['excel_file'] = excel_path
                    except Exception as e2:
                        log_callback(f'⚠️ Lỗi khi cập nhật Excel realtime (ERROR): {str(e2)}')

            processed = upload_status['success_count'] + upload_status['fail_count']
            if upload_status['total_files'] > 0:
                upload_status['progress'] = int((processed / upload_status['total_files']) * 100)

            upload_queue.task_done()

        # Generate Excel file after all uploads
        if upload_status['success_count'] > 0 or upload_status['fail_count'] > 0:
            try:
                excel_filename = last_excel_filename
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
        if upload_driver:
            try:
                upload_driver.quit()
            except Exception:
                pass
            upload_driver = None

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
            meta[str(account_id)]["password"] = encrypt_password(password)
        _save_profiles_meta(meta)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/accounts/clear-google-session', methods=['POST'])
def api_clear_google_session():
    """Xóa cookie trong profile Chrome — dùng khi đổi sang tài khoản Google khác trên cùng profile."""
    try:
        if upload_status.get("is_running"):
            return jsonify({"success": False, "error": "Đang chạy upload. Hãy dừng hẳn, đóng Chrome do tool mở, rồi thử lại."}), 400
        data = request.json or {}
        if data.get("account_id") is None:
            return jsonify({"success": False, "error": "Thiếu account_id"}), 400
        account_id = int(data.get("account_id"))
        pdir = _profile_dir_for_account(account_id)
        if not os.path.isdir(pdir):
            return jsonify({"success": False, "error": "Tài khoản không tồn tại"}), 404
        ok, err = _clear_profile_google_cookies(pdir)
        if not ok:
            return jsonify({"success": False, "error": err}), 500
        return jsonify({
            "success": True,
            "message": "Đã xóa cookie Google trong profile. Lần sau chạy tool, hãy Lưu đăng nhập với email/mật khẩu mới và đăng nhập lại.",
        })
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
    global upload_thread, upload_status, upload_queue, upload_session_log_file
    
    try:
        data = request.json
        account_id = data.get('account_id')
        folder = data.get('folder')
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
            'total_files': 0,
            'current_file': '',
            'success_count': 0,
            'fail_count': 0,
            'progress': 0,
            'logs': [],
            'excel_file': None,
            'waiting_for_login': False,
            'account_id': account_id,
            'profile_dir': profile_dir,
            'session_log_file': None,
        }
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        upload_session_log_file = os.path.join(DEBUG_DIR, f"upload-session-{ts}.log")
        upload_status['session_log_file'] = upload_session_log_file
        _append_upload_session_log(datetime.now().strftime('%H:%M:%S'), "=== Bắt đầu phiên upload mới ===")
        
        # Get video files
        video_extensions = ['.mp4', '.mov', '.mkv', '.avi', '.wmv', '.flv', '.webm']
        video_files = []
        for file in os.listdir(folder):
            if any(file.lower().endswith(ext) for ext in video_extensions):
                video_files.append(os.path.join(folder, file))
        
        if not video_files:
            return jsonify({'error': 'Không tìm thấy file video nào'}), 400
        
        video_files.sort()
        batch_size = getattr(tooldangvideo, "UPLOAD_BATCH_SIZE", 15)
        upload_queue = queue.Queue()
        for i in range(0, len(video_files), batch_size):
            batch = video_files[i : i + batch_size]
            upload_queue.put({
                'batch_paths': batch,
                'made_for_kids': made_for_kids,
                'visibility': visibility,
                'excel_filename': excel_filename,
            })
        
        upload_status['total_files'] = len(video_files)
        log_callback(
            f'Bắt đầu upload {len(video_files)} video — mỗi lô tối đa {batch_size} file (Studio chọn nhiều file một lần)'
        )

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
    """Stop upload is disabled (kept for backward compatibility)."""
    return jsonify({'success': False, 'error': 'Chức năng dừng đã bị tắt'}), 400

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

@app.route('/api/download-upload-log', methods=['GET'])
def download_upload_log():
    """Download file log phiên upload gần nhất."""
    p = upload_status.get('session_log_file') or upload_session_log_file
    if not p or not os.path.exists(p):
        return jsonify({'error': 'File log phiên upload không tồn tại'}), 404
    return send_file(
        p,
        as_attachment=True,
        download_name=os.path.basename(p)
    )

def open_browser():
    """Open browser automatically"""
    import webbrowser
    import time
    time.sleep(1.5)
    webbrowser.open('http://127.0.0.1:5000')

if __name__ == '__main__':
    def _excepthook(exc_type, exc, tb):
        try:
            with open(os.path.join(DEBUG_DIR, "crash.log"), "a", encoding="utf-8", errors="replace") as f:
                f.write(f"\n=== {datetime.now().isoformat()} ===\n")
                traceback.print_exception(exc_type, exc, tb, file=f)
        except Exception:
            pass
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = _excepthook

    if hasattr(threading, "excepthook"):
        _orig_thread_excepthook = threading.excepthook

        def _thread_excepthook(args):
            try:
                with open(os.path.join(DEBUG_DIR, "crash.log"), "a", encoding="utf-8", errors="replace") as f:
                    nm = getattr(args.thread, "name", "?")
                    f.write(f"\n=== Luồng {nm} {datetime.now().isoformat()} ===\n")
                    traceback.print_exception(args.exc_type, args.exc_value, args.exc_traceback, file=f)
            except Exception:
                pass
            _orig_thread_excepthook(args)

        threading.excepthook = _thread_excepthook

    # Bản .exe: ghi thêm mọi thứ in ra console vào debug_logs/console.log để gửi cho dev khi lỗi
    if getattr(sys, "frozen", False):
        class _Tee:
            __slots__ = ("_streams",)

            def __init__(self, *streams):
                self._streams = streams

            def write(self, data):
                for s in self._streams:
                    try:
                        s.write(data)
                        s.flush()
                    except Exception:
                        pass

            def flush(self):
                for s in self._streams:
                    try:
                        s.flush()
                    except Exception:
                        pass

        try:
            _cf = open(os.path.join(DEBUG_DIR, "console.log"), "a", encoding="utf-8", errors="replace")
            _cf.write(f"\n--- Khởi động {datetime.now().isoformat()} ---\n")
            _cf.flush()
            sys.stdout = _Tee(sys.__stdout__, _cf)
            sys.stderr = _Tee(sys.__stderr__, _cf)
        except OSError:
            pass

    try:
        # Open browser in separate thread
        browser_thread = threading.Thread(target=open_browser, daemon=True)
        browser_thread.start()

        # Run Flask app
        app.run(host='127.0.0.1', port=5000, debug=False)
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
        try:
            with open(os.path.join(DEBUG_DIR, "crash.log"), "a", encoding="utf-8", errors="replace") as f:
                f.write(f"\n=== Flask start {datetime.now().isoformat()} ===\n")
                traceback.print_exc(file=f)
        except OSError:
            pass
        input("Press Enter to exit...")
