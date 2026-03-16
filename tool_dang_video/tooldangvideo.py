# -*- coding: utf-8 -*-
"""
Module đăng video lên YouTube qua YouTube Studio (Selenium).
Cung cấp: init_driver(), upload_video(), generate_excel()
"""
import os
import re
import time
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, WebDriverException

try:
    from openpyxl import Workbook
    from openpyxl import load_workbook
    from openpyxl.styles import Font, Alignment
    from openpyxl.utils import get_column_letter
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False
    get_column_letter = None


import json

# URL YouTube Studio
YOUTUBE_STUDIO_URL = "https://studio.youtube.com/"
YOUTUBE_UPLOAD_URL = "https://studio.youtube.com/?noapp=1"

# Thư mục profile Chrome mặc định để lưu đăng nhập YouTube (cookie, session)
# (app.py có thể truyền profile_dir khác để chọn nhiều tài khoản)
CHROME_PROFILE_DIR = os.path.join(os.getcwd(), "chrome_youtube_profile")


# #region agent log
def _agent_debug_log(hypothesis_id, message, data=None, run_id="init_driver_pre"):
    """
    Ghi log debug dạng NDJSON vào file debug-57c0c7.log (ở thư mục project gốc)
    để phân tích lỗi runtime. Không ghi thông tin nhạy cảm (token, mật khẩu, ...).
    """
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    log_path = os.path.join(project_root, "debug-57c0c7.log")
    payload = {
        "sessionId": "57c0c7",
        "runId": run_id,
        "hypothesisId": hypothesis_id,
        "location": "tooldangvideo.py:init_driver",
        "message": message,
        "data": data or {},
        "timestamp": int(time.time() * 1000),
    }
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        # Tránh làm hỏng luồng chính nếu việc ghi log thất bại
        pass
# #endregion agent log


def _log(log_callback, message):
    if log_callback:
        log_callback(message)


# #region agent log
def _agent_excel_path(excel_filename: str):
    output_dir = os.path.join(os.getcwd(), "output")
    os.makedirs(output_dir, exist_ok=True)
    safe_name = "".join(c for c in str(excel_filename or "") if c.isalnum() or c in "._- ") or "YouTube_Upload_Links.xlsx"
    if not safe_name.endswith(".xlsx"):
        safe_name += ".xlsx"
    return os.path.join(output_dir, safe_name)


def _set_excel_column_widths(ws, num_cols=5):
    """Đặt độ rộng cột để dễ đọc và copy link (STT, Tên file, Link, Thời gian, Trạng thái)."""
    if not OPENPYXL_AVAILABLE or get_column_letter is None:
        return
    widths = [8, 42, 58, 20, 14]  # STT hẹp, Tên file & Link rộng, Thời gian & Trạng thái vừa
    for i, w in enumerate(widths[:num_cols], 1):
        try:
            ws.column_dimensions[get_column_letter(i)].width = w
        except Exception:
            pass


def append_excel_row(file_name: str, url: str, status: str, excel_filename: str = "YouTube_Upload_Links.xlsx", log_callback=None):
    """
    Ghi dần kết quả upload ra Excel ngay khi có kết quả.
    - Nếu file chưa tồn tại: tạo mới + header
    - Nếu đã tồn tại: append thêm 1 dòng
    """
    if not OPENPYXL_AVAILABLE:
        _log(log_callback, "Thiếu thư viện openpyxl, không ghi được Excel theo thời gian thực.")
        return None
    excel_path = _agent_excel_path(excel_filename)
    try:
        # Debug: xác định đang tạo mới hay append
        _agent_debug_log(
            "X1",
            "append_excel_row invoked",
            {"excelPath": excel_path, "exists": os.path.exists(excel_path), "cwd": os.getcwd()},
            run_id="excel_append_pre",
        )
    except Exception:
        pass
    try:
        if os.path.exists(excel_path):
            wb = load_workbook(excel_path)
            ws = wb.active
            # Nếu file cũ chưa có cột Trạng thái thì thêm vào cuối (để tương thích ngược)
            try:
                header = [str(c.value or "").strip() for c in ws[1]]
                if "Trạng thái" not in header:
                    col = len(header) + 1
                    ws.cell(row=1, column=col, value="Trạng thái")
                    ws.cell(row=1, column=col).font = Font(bold=True)
                    ws.cell(row=1, column=col).alignment = Alignment(horizontal="center")
                    # fill rỗng cho các dòng cũ
                    for r in range(2, ws.max_row + 1):
                        ws.cell(row=r, column=col, value=ws.cell(row=r, column=col).value or "")
            except Exception:
                pass
        else:
            wb = Workbook()
            ws = wb.active
            ws.title = "YouTube Links"
            ws.append(["STT", "Tên file", "Link YouTube", "Thời gian", "Trạng thái"])
            for cell in ws[1]:
                cell.font = Font(bold=True)
                cell.alignment = Alignment(horizontal="center")
        next_index = ws.max_row  # header ở row 1 => dòng data đầu = 2 => STT = max_row
        ws.append([next_index, file_name or "N/A", url or "", datetime.now().strftime("%Y-%m-%d %H:%M"), status or ""])
        # Đảm bảo file cũ được "mở rộng" đủ 5 cột (một số trường hợp append không tăng max_column như mong đợi)
        try:
            ws.cell(row=1, column=5, value=ws.cell(row=1, column=5).value or "Trạng thái")
            ws.cell(row=ws.max_row, column=5, value=status or "")
        except Exception:
            pass
        _set_excel_column_widths(ws, 5)
        wb.save(excel_path)
        _log(log_callback, f"📄 Đã cập nhật Excel: {excel_path}")
        try:
            _agent_debug_log(
                "X1",
                "append_excel_row saved",
                {"excelPath": excel_path, "row": ws.max_row, "maxCol": ws.max_column},
                run_id="excel_append_post",
            )
        except Exception:
            pass
        return excel_path
    except Exception as e:
        _log(log_callback, f"⚠️ Lỗi khi cập nhật Excel realtime: {e}")
        try:
            _agent_debug_log(
                "X2",
                "append_excel_row failed",
                {"excelPath": excel_path, "error": str(e)},
                run_id="excel_append_error",
            )
        except Exception:
            pass
        return None
# #endregion agent log


def ensure_excel_initialized(excel_filename: str = "YouTube_Upload_Links.xlsx", log_callback=None):
    """
    Đảm bảo file Excel tồn tại và có đủ header, đặc biệt cột "Trạng thái".
    Dùng ngay khi bắt đầu batch để không phụ thuộc việc upload thành công/thất bại.
    """
    if not OPENPYXL_AVAILABLE:
        _log(log_callback, "Thiếu thư viện openpyxl, không khởi tạo được Excel.")
        return None
    excel_path = _agent_excel_path(excel_filename)
    try:
        _agent_debug_log(
            "X0",
            "ensure_excel_initialized invoked",
            {"excelPath": excel_path, "exists": os.path.exists(excel_path), "cwd": os.getcwd()},
            run_id="excel_init_pre",
        )
    except Exception:
        pass
    try:
        if os.path.exists(excel_path):
            wb = load_workbook(excel_path)
            ws = wb.active
            header = [str(c.value or "").strip() for c in ws[1]]
            if "Trạng thái" not in header:
                col = len(header) + 1
                ws.cell(row=1, column=col, value="Trạng thái")
                ws.cell(row=1, column=col).font = Font(bold=True)
                ws.cell(row=1, column=col).alignment = Alignment(horizontal="center")
                for r in range(2, ws.max_row + 1):
                    ws.cell(row=r, column=col, value=ws.cell(row=r, column=col).value or "")
                _set_excel_column_widths(ws, 5)
                wb.save(excel_path)
        else:
            wb = Workbook()
            ws = wb.active
            ws.title = "YouTube Links"
            ws.append(["STT", "Tên file", "Link YouTube", "Thời gian", "Trạng thái"])
            for cell in ws[1]:
                cell.font = Font(bold=True)
                cell.alignment = Alignment(horizontal="center")
            _set_excel_column_widths(ws, 5)
            wb.save(excel_path)
        try:
            _agent_debug_log(
                "X0",
                "ensure_excel_initialized done",
                {"excelPath": excel_path},
                run_id="excel_init_post",
            )
        except Exception:
            pass
        return excel_path
    except Exception as e:
        _log(log_callback, f"⚠️ Lỗi khi khởi tạo Excel: {e}")
        try:
            _agent_debug_log(
                "X0",
                "ensure_excel_initialized failed",
                {"excelPath": excel_path, "error": str(e)},
                run_id="excel_init_error",
            )
        except Exception:
            pass
        return None


def _handle_prechecks_warning_after_done(driver, log_callback=None):
    """
    Sau khi bấm Lưu/Done, YouTube đôi khi hiện dialog cảnh báo pre-checks:
    - Nút: "Vẫn xuất bản" / "Quay lại"
    Điều kiện nhận biết thường thấy: banner khuyến nghị "Bạn nên giữ video này ở chế độ riêng tư..."
    """
    try:
        # #region agent log
        try:
            _agent_debug_log(
                "P1",
                "Checking prechecks warning banner/dialog after Done",
                {"url": driver.current_url},
                run_id="prechecks_check_pre",
            )
        except Exception:
            pass
        # #endregion agent log

        # 1) Kiểm tra banner khuyến nghị (nếu có)
        banner_present = False
        try:
            banner = driver.find_elements(By.CSS_SELECTOR, "ytcp-banner #message .subheading")
            for b in banner:
                txt = (b.text or "").strip()
                if "Bạn nên giữ video này ở chế độ riêng tư" in txt or "You should keep this video private" in txt:
                    banner_present = True
                    break
        except Exception:
            banner_present = False

        # 2) Nếu có dialog warning: ưu tiên bấm "Vẫn xuất bản"
        # Selector theo DOM bạn gửi: ytcp-prechecks-warning-dialog + secondary-action-button
        try:
            dialog = WebDriverWait(driver, 2).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "ytcp-prechecks-warning-dialog"))
            )
            try:
                _agent_debug_log(
                    "P1",
                    "Prechecks warning dialog detected",
                    {"bannerPresent": banner_present},
                    run_id="prechecks_check_post",
                )
            except Exception:
                pass

            publish_btn = None
            for sel in [
                "ytcp-prechecks-warning-dialog ytcp-button#secondary-action-button button",
                "ytcp-prechecks-warning-dialog button[aria-label*='Vẫn']",
                "ytcp-prechecks-warning-dialog button[aria-label*='xuất bản']",
                "ytcp-prechecks-warning-dialog button:has(.ytcpButtonShapeImpl__button-text-content)",
            ]:
                try:
                    btns = driver.find_elements(By.CSS_SELECTOR, sel)
                    if btns:
                        publish_btn = btns[0]
                        break
                except Exception:
                    continue
            if publish_btn is None:
                # XPath fallback by visible text
                try:
                    publish_btn = driver.find_element(By.XPATH, "//*[contains(text(),'Vẫn xuất bản') or contains(text(),'Vẫn xuất bản') or contains(text(),'Publish anyway')]/ancestor::button")
                except Exception:
                    publish_btn = None
            if publish_btn is not None:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", publish_btn)
                try:
                    publish_btn.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", publish_btn)
                _log(log_callback, "Đã xác nhận cảnh báo: Vẫn xuất bản.")
                try:
                    _agent_debug_log(
                        "P2",
                        "Clicked 'Vẫn xuất bản' on prechecks dialog",
                        {},
                        run_id="prechecks_action_post",
                    )
                except Exception:
                    pass
                return True
            return False
        except Exception:
            # Không có dialog
            try:
                _agent_debug_log(
                    "P1",
                    "No prechecks warning dialog detected",
                    {"bannerPresent": banner_present},
                    run_id="prechecks_check_post",
                )
            except Exception:
                pass
            return False
    except Exception as e:
        try:
            _agent_debug_log(
                "P0",
                "Error while handling prechecks warning",
                {"error": str(e)},
                run_id="prechecks_error",
            )
        except Exception:
            pass
        return False


def _click_next(driver, log_callback, step_name=""):
    """Bấm nút Next nếu có."""
    # Giả thuyết:
    # N1: Sau khi xử lý bản quyền và quay lại, nút Next dùng selector khác (#done-button, label tiếng Việt khác, v.v.)
    # N2: Có overlay/dialog che nút Next nên element_to_be_clickable không thỏa.
    # N3: Đang ở bước Chế độ hiển thị (chỉ có nút Lưu/Done, không còn Next).
    try:
        try:
            _agent_debug_log(
                "N1",
                "Trying to locate Next button",
                {"step": step_name},
                run_id="click_next_pre",
            )
        except Exception:
            pass
        # ytcp-button#next-button (bước Chi tiết, Các thành phần của video, Kiểm tra); aria-label tiếng Việt "Tiếp"
        next_btn = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((
            By.CSS_SELECTOR,
            "ytcp-button#next-button, #next-button, button[aria-label='Tiếp'], button[aria-label='Next']"
        )))
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_btn)
        next_btn.click()
        if step_name and log_callback:
            log_callback(f"Đã bấm Next: {step_name}")
        try:
            _agent_debug_log(
                "N1",
                "Clicked Next button successfully",
                {"step": step_name},
                run_id="click_next_post",
            )
        except Exception:
            pass
        return True
    except TimeoutException:
        # Ghi log chi tiết khi không tìm thấy/click được Next
        try:
            _agent_debug_log(
                "N2",
                "Failed to locate/click Next button (TimeoutException)",
                {"step": step_name, "url": driver.current_url},
                run_id="click_next_error",
            )
        except Exception:
            pass
        return False


def _handle_checks_and_copyright(driver, wait, log_callback):
    """
    Bước Kiểm tra ban đầu (ytcp-uploads-checks): không báo gì thì Next.
    Nếu có bản quyền: xử lý thay thế bài hát rồi tiếp tục.
    :return: True nếu OK tiếp tục, False nếu không hoàn thành được (upload_video sẽ báo lỗi và chuyển video khác).
    """
    try:
        # Đọc nội dung mô tả kết quả kiểm tra bản quyền
        try:
            status_desc_el = driver.find_element(
                By.CSS_SELECTOR,
                "#copyright-status #results-description"
            )
            status_desc = (status_desc_el.text or "").strip()
        except Exception:
            status_desc_el = None
            status_desc = ""

        # Nếu hệ thống vẫn đang ở trạng thái "Kiểm tra xem video của bạn có chứa nội dung có bản quyền hay không"
        # thì chờ cho đến khi trạng thái đổi sang 1 trong 2:
        # - "Không phát hiện vấn đề nào"  -> tiếp tục luôn
        # - "Phát hiện có nội dung được bảo hộ bản quyền..." -> xử lý thay thế bài hát
        if status_desc and "Kiểm tra xem video của bạn có chứa nội dung có bản quyền hay không" in status_desc:
            _log(log_callback, "Đang chờ YouTube chạy kiểm tra bản quyền (tối đa ~3 phút)...")
            max_wait_secs = 180
            waited = 0
            while waited < max_wait_secs:
                time.sleep(3)
                waited += 3
                try:
                    status_desc_el = driver.find_element(
                        By.CSS_SELECTOR,
                        "#copyright-status #results-description"
                    )
                    status_desc = (status_desc_el.text or "").strip()
                except Exception:
                    status_desc = ""
                    break
                # Khi text không còn là câu "Kiểm tra xem video..." nữa thì thoát vòng lặp để xử lý tiếp
                if "Kiểm tra xem video của bạn có chứa nội dung có bản quyền hay không" not in status_desc:
                    break
            _log(log_callback, f"Trạng thái kiểm tra bản quyền sau khi chờ: {status_desc or 'không xác định'}")

        # Trạng thái đã xong: không phát hiện vấn đề nào -> bỏ qua bước bản quyền, Next luôn
        if status_desc and "Không phát hiện vấn đề nào" in status_desc:
            _log(log_callback, "Kiểm tra bản quyền: Không phát hiện vấn đề nào, bỏ qua bước Xem chi tiết.")
            return True

        # Chỉ khi thực sự hiện câu "Phát hiện có nội dung được bảo hộ bản quyền..."
        # thì mới coi là có cảnh báo bản quyền cần xử lý
        if status_desc and "Phát hiện có nội dung được bảo hộ bản quyền" in status_desc:
            _log(log_callback, "Phát hiện cảnh báo bản quyền, đang chờ nút Xem chi tiết (YouTube kiểm tra có thể vài phút)...")
            # Chờ nút "Xem chi tiết" xuất hiện — tối đa 5 phút, không báo lỗi trong lúc chờ
            clicked = False
            try:
                btn = WebDriverWait(driver, 300).until(EC.element_to_be_clickable((
                    By.CSS_SELECTOR,
                    "#copyright-status #results-action ytcp-button, "
                    "#copyright-status button[aria-label*='Xem chi ti'], "
                    "ytcp-uploads-check-status#copyright-status [id='results-action'] ytcp-button"
                )))
                time.sleep(1)
                btn.click()
                clicked = True
                _log(log_callback, "Đã bấm Xem chi tiết.")
                time.sleep(3)
            except Exception:
                pass
            if not clicked:
                try:
                    btn = WebDriverWait(driver, 120).until(EC.element_to_be_clickable((
                        By.XPATH,
                        "//*[contains(text(),'Xem chi tiết') or contains(text(),'Xem chi tiết') or contains(text(),'View details')]"
                    )))
                    btn.click()
                    clicked = True
                    _log(log_callback, "Đã bấm Xem chi tiết.")
                    time.sleep(3)
                except Exception:
                    pass
            if not clicked:
                _log(log_callback, "❌ Lỗi: Không tìm thấy nút Xem chi tiết (kiểm tra bản quyền chưa xong hoặc giao diện đổi). Chuyển video khác.")
                return False
            time.sleep(2)
            # Chọn cách giải quyết — chờ dialog mở rồi mới bấm (tối đa 15s)
            choose_clicked = False
            try:
                choose_btn = WebDriverWait(driver, 15).until(EC.element_to_be_clickable((
                    By.CSS_SELECTOR,
                    "ytcr-video-actions-button button[aria-label='Chọn cách giải quyết'], "
                    ".resolution-actions-button ytcp-button, "
                    "ytcr-video-actions-button #actions-button, "
                    "button[aria-label='Chọn cách giải quyết']"
                )))
                choose_btn.click()
                choose_clicked = True
                _log(log_callback, "Đã bấm Chọn cách giải quyết.")
                time.sleep(2)
            except Exception:
                pass
            if not choose_clicked:
                for btn_text in ["Chọn cách giải quyết", "Choose resolution", "Choose action"]:
                    try:
                        btn = WebDriverWait(driver, 8).until(EC.element_to_be_clickable((
                            By.XPATH, f"//*[contains(text(),'{btn_text}')]"
                        )))
                        btn.click()
                        time.sleep(2)
                        choose_clicked = True
                        break
                    except Exception:
                        continue
            if not choose_clicked:
                _log(log_callback, "❌ Lỗi: Không tìm thấy Chọn cách giải quyết. Chuyển video khác.")
                return False
            time.sleep(2)
            # Thay thế bài hát — trong ytcr-video-actions-dialog: action-card-container action="NON_TAKEDOWN_CLAIM_OPTION_REPLACE_SONG"
            replace_clicked = False
            try:
                replace_btn = driver.find_element(
                    By.CSS_SELECTOR,
                    "ytcr-video-actions-dialog button.action-card-container[action='NON_TAKEDOWN_CLAIM_OPTION_REPLACE_SONG'], "
                    "ytcr-video-actions-dialog .action-card-container[action='NON_TAKEDOWN_CLAIM_OPTION_REPLACE_SONG'], "
                    "[action='NON_TAKEDOWN_CLAIM_OPTION_REPLACE_SONG']"
                )
                replace_btn.click()
                replace_clicked = True
                _log(log_callback, "Đã chọn Thay thế bài hát.")
                time.sleep(2)
            except Exception:
                pass
            if not replace_clicked:
                for opt in ["Thay thế bài hát", "Replace the song", "Replace song"]:
                    try:
                        el = driver.find_element(By.XPATH, f"//*[contains(text(),'{opt}')]")
                        el.click()
                        time.sleep(2)
                        break
                    except Exception:
                        continue
            time.sleep(1)
            # Trong dialog sau "Thay thế bài hát" có nút "Tiếp tục" (confirm-button) — bấm để mở panel chọn bài hát
            confirm_clicked = False
            try:
                confirm_btn = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((
                    By.CSS_SELECTOR,
                    "ytcr-video-actions-dialog ytcp-button#confirm-button, "
                    "ytcr-video-actions-dialog button[aria-label*='Tiếp tục'], "
                    "ytcr-video-actions-dialog button[aria-label*='Tiếp tục'], "
                    "button[aria-label='Tiếp tục']"
                )))
                try:
                    inner = confirm_btn.find_element(By.CSS_SELECTOR, "button")
                    inner.click()
                except Exception:
                    confirm_btn.click()
                confirm_clicked = True
                _log(log_callback, "Đã bấm Tiếp tục trong dialog thay thế bài hát.")
                time.sleep(2)
            except Exception:
                pass
            if not confirm_clicked:
                try:
                    btn = driver.find_element(By.XPATH, "//*[contains(text(),'Tiếp tục') or contains(text(),'Continue')]/ancestor::button | //ytcp-button[.//*[contains(text(),'Tiếp tục')]]")
                    btn.click()
                    confirm_clicked = True
                    _log(log_callback, "Đã bấm Tiếp tục.")
                    time.sleep(2)
                except Exception:
                    pass
            # Chờ panel thay thế bài hát tải xong
            time.sleep(3)
            _log(log_callback, "Tiếp tục: chọn bài hát đầu tiên (bấm Thêm)...")
            # Nút Thêm: ytcp-icon-button#add-track-button (aria-label="Thêm") trong ytve-audioswap-track-row — bấm cái đầu tiên
            add_clicked = False
            try:
                first_add = WebDriverWait(driver, 15).until(EC.presence_of_all_elements_located((
                    By.CSS_SELECTOR,
                    "ytve-audioswap-track-row ytcp-icon-button#add-track-button, "
                    "ytcp-icon-button#add-track-button, "
                    "ytcp-icon-button[aria-label='Thêm']"
                )))
                if first_add:
                    add_el = first_add[0]
                    time.sleep(0.5)
                    add_el.click()
                    add_clicked = True
                    _log(log_callback, "Đã chọn bài hát đầu tiên (Thêm).")
                    time.sleep(2)
            except Exception:
                pass
            if not add_clicked:
                try:
                    plus_btn = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((
                        By.CSS_SELECTOR,
                        "ytcp-icon-button#add-track-button, ytcp-icon-button[aria-label='Thêm']"
                    )))
                    plus_btn.click()
                    add_clicked = True
                    _log(log_callback, "Đã chọn bài hát đầu tiên (Thêm).")
                    time.sleep(2)
                except Exception:
                    plus_btns = driver.find_elements(By.CSS_SELECTOR, "ytcp-icon-button#add-track-button, ytcp-icon-button[aria-label='Thêm']")
                    if plus_btns:
                        plus_btns[0].click()
                        add_clicked = True
                        _log(log_callback, "Đã chọn bài hát đầu tiên (Thêm).")
                        time.sleep(2)
            time.sleep(2)
            # Lưu / Xong — chờ nút sẵn sàng (tối đa 15s), thử click nút thật bên trong ytcp-button nếu cần
            _log(log_callback, "Đang bấm Lưu / Xong...")
            save_clicked = False
            # Ưu tiên nút Lưu trên góc phải trong modal "Thay thế bài hát"
            try:
                # Tìm đúng button bên trong ytcp-button#save-button như DOM bạn gửi
                save_btn_outer = WebDriverWait(driver, 15).until(EC.presence_of_element_located((
                    By.CSS_SELECTOR,
                    "ytve-modal-host ytcp-button#save-button"
                )))
                inner_button = save_btn_outer.find_element(By.CSS_SELECTOR, "button[aria-label='Lưu'], button.ytcpButtonShapeImplHost")
                # Đảm bảo nút ở trong vùng hiển thị và không bị lớp khác che
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", inner_button)
                WebDriverWait(driver, 10).until(EC.element_to_be_clickable(inner_button))
                try:
                    inner_button.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", inner_button)
                save_clicked = True
                _log(log_callback, "Đã bấm nút Lưu trong modal Thay thế bài hát.")
                time.sleep(2)
            except Exception:
                pass
            # Nếu chưa bấm được Lưu, fallback sang Xong/Done trong editor
            if not save_clicked:
                try:
                    done_btn = WebDriverWait(driver, 15).until(EC.element_to_be_clickable((
                        By.CSS_SELECTOR,
                        "ytmus-license-dialog ytcp-button#done-button, "
                        "ytve-editor ytcp-button#done-button, "
                        "button[aria-label='Xong'], button[aria-label='Done']"
                    )))
                    try:
                        inner = done_btn.find_element(By.CSS_SELECTOR, "button")
                        inner.click()
                    except Exception:
                        done_btn.click()
                    save_clicked = True
                    _log(log_callback, "Đã bấm Xong.")
                    time.sleep(2)
                except Exception:
                    pass
            if not save_clicked:
                for save_text in ["Lưu", "Xong", "Save", "Lưu thay đổi", "Done"]:
                    try:
                        save_btn = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((
                            By.XPATH, f"//*[contains(text(),'{save_text}')]/ancestor::button | //button[contains(.,'{save_text}')]"
                        )))
                        save_btn.click()
                        save_clicked = True
                        _log(log_callback, f"Đã bấm {save_text}.")
                        time.sleep(2)
                        break
                    except Exception:
                        continue
            if not save_clicked:
                _log(log_callback, "❌ Lỗi: Không tìm thấy nút Lưu/Xong sau thay thế bài hát. Chuyển video khác.")
                return False

            # Hộp thoại "Xác nhận thay đổi": tích checkbox trước, chờ nút Xác nhận bật rồi bấm
            time.sleep(2)
            try:
                # Tìm đúng checkbox theo DOM bạn gửi
                checkbox = WebDriverWait(driver, 12).until(
                    EC.presence_of_element_located((
                        By.CSS_SELECTOR,
                        "ytve-save-dialog ytcp-checkbox-lit #checkbox, "
                        "ytcp-checkbox-lit #checkbox[role='checkbox'][aria-label*='xác nhận'], "
                        "div#checkbox[role='checkbox'][aria-label*='xác nhận']"
                    ))
                )
                # Đưa checkbox vào giữa màn hình và bấm bằng JS để tránh lớp che
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", checkbox)
                WebDriverWait(driver, 8).until(EC.element_to_be_clickable(checkbox))
                try:
                    checkbox.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", checkbox)
                # Nếu vẫn chưa được tick thì gửi phím Space
                time.sleep(0.8)
                aria_checked = checkbox.get_attribute("aria-checked")
                if aria_checked not in ("true", "True"):
                    from selenium.webdriver.common.keys import Keys as _Keys
                    checkbox.send_keys(_Keys.SPACE)
                    time.sleep(0.8)
                aria_checked = checkbox.get_attribute("aria-checked")
                _log(log_callback, f"Trạng thái checkbox sau khi click: aria-checked={aria_checked}")
                if aria_checked not in ("true", "True"):
                    _log(log_callback, "⚠️ Không tick được checkbox xác nhận thay đổi vĩnh viễn, vẫn thử bấm nút 'Xác nhận thay đổi'.")
                else:
                    _log(log_callback, "Đã tích xác nhận thay đổi vĩnh viễn.")
            except Exception as e:
                _log(log_callback, f"⚠️ Không tìm được checkbox 'Tôi xác nhận rằng những thay đổi này là vĩnh viễn': {e}")

            try:
                # Tìm đúng nút 'Xác nhận thay đổi' theo DOM bạn gửi
                apply_btn_outer = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((
                        By.CSS_SELECTOR,
                        "ytve-save-dialog ytcp-button#apply-button"
                    ))
                )
                apply_inner = apply_btn_outer.find_element(
                    By.CSS_SELECTOR,
                    "button[aria-label='Xác nhận thay đổi'], button.ytcpButtonShapeImplHost"
                )
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", apply_inner)
                WebDriverWait(driver, 8).until(EC.element_to_be_clickable(apply_inner))
                try:
                    apply_inner.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", apply_inner)
                _log(log_callback, "Đã bấm Xác nhận thay đổi.")
                time.sleep(3)
            except Exception:
                try:
                    apply_btn = driver.find_element(By.CSS_SELECTOR, "ytcp-button#apply-button")
                    inner = apply_btn.find_element(By.CSS_SELECTOR, "button")
                    if inner.get_attribute("disabled") != "true":
                        inner.click()
                        _log(log_callback, "Đã bấm Xác nhận thay đổi (fallback).")
                        time.sleep(3)
                except Exception:
                    for txt in ["Xác nhận thay đổi", "Apply changes", "Xác nhận"]:
                        try:
                            btn = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((
                                By.XPATH, f"//button[contains(.,'{txt}')] | //ytcp-button[.//*[contains(text(),'{txt}')]]"
                            )))
                            btn.click()
                            _log(log_callback, f"Đã bấm '{txt}'.")
                            time.sleep(3)
                            break
                        except Exception:
                            continue

            # Sau khi áp dụng thay đổi, quay lại editor / quy trình tải lên
            try:
                for back_txt in ["Quay lại quy trình tải lên", "Quay lại trình chỉnh sửa", "Quay lại"]:
                    try:
                        back_btn = driver.find_element(
                            By.XPATH,
                            f"//ytcp-button[.//*[contains(text(),'{back_txt}')]] | //button[contains(text(),'{back_txt}')]"
                        )
                        back_btn.click()
                        _log(log_callback, f"Đã bấm nút '{back_txt}' để quay lại quy trình tải lên.")
                        time.sleep(2)
                        break
                    except Exception:
                        continue
            except Exception:
                pass

            # Sau khi quay lại quy trình tải lên, bấm "Tiếp" để sang bước "Chế độ hiển thị"
            try:
                if _click_next(driver, log_callback, "Sau thay thế bài hát → Chế độ hiển thị"):
                    time.sleep(2)
            except Exception:
                pass

            _log(log_callback, "Đã xử lý thay thế bài hát và xác nhận thay đổi, quay lại quy trình tải lên.")
            return True
        else:
            _log(log_callback, "Không có cảnh báo kiểm tra, tiếp tục.")
            return True
    except Exception as e:
        _log(log_callback, f"❌ Lỗi bước kiểm tra/bản quyền: {e}. Chuyển video khác.")
        return False


def ensure_youtube_login(driver, email, password, log_callback=None):
    """
    Nếu Chrome đang ở trang đăng nhập Google/YouTube thì tự động điền email + mật khẩu và đăng nhập.
    Gọi sau init_driver khi profile đã lưu email/password. Nếu có 2FA/captcha thì chỉ ghi log, user đăng nhập tay.
    """
    if not email or not str(email).strip() or not password:
        return
    email = str(email).strip()
    try:
        driver.get(YOUTUBE_STUDIO_URL)
        time.sleep(3)
        url = driver.current_url
        if "accounts.google.com" in url or "signin" in url.lower() or "login" in url.lower():
            _log(log_callback, "Đang tự động đăng nhập bằng email/mật khẩu đã lưu...")
        else:
            body_text = driver.find_element(By.TAG_NAME, "body").text
            if "Đăng nhập" in body_text or "Sign in" in body_text or "Sign in to YouTube" in body_text:
                _log(log_callback, "Phát hiện trang đăng nhập, đang điền email/mật khẩu...")
            else:
                _log(log_callback, "Đã đăng nhập sẵn (cookie profile).")
                return
        if "accounts.google.com" not in driver.current_url:
            try:
                signin = driver.find_element(By.XPATH, "//a[contains(@href,'accounts.google.com') or contains(text(),'Đăng nhập') or contains(text(),'Sign in')]")
                signin.click()
                time.sleep(3)
            except Exception:
                driver.get("https://accounts.google.com/ServiceLogin?service=youtube&continue=https://studio.youtube.com/")
                time.sleep(3)
        try:
            email_input = WebDriverWait(driver, 10).until(EC.presence_of_element_located((
                By.CSS_SELECTOR,
                "input[type='email'], input[name='identifier'], #identifierId"
            )))
            email_input.clear()
            email_input.send_keys(email)
            _log(log_callback, "Đã nhập email.")
            time.sleep(0.5)
        except Exception as e:
            _log(log_callback, f"Không tìm thấy ô email: {e}")
            return
        try:
            next_btn = WebDriverWait(driver, 8).until(EC.element_to_be_clickable((
                By.XPATH,
                "//span[text()='Next']/.. | //span[text()='Tiếp']/.. | //button[.//span[text()='Next']] | //div[@role='button']//span[text()='Tiếp']/.. | //*[text()='Next']/ancestor::button | //*[text()='Tiếp']/ancestor::div[@role='button']"
            )))
            next_btn.click()
            time.sleep(3)
        except Exception:
            try:
                next_btn = driver.find_element(By.CSS_SELECTOR, "#identifierNext button, [data-idom-class*='Next'] button")
                next_btn.click()
                time.sleep(3)
            except Exception as e:
                _log(log_callback, f"Không bấm được Next: {e}")
                return
        try:
            pw_input = WebDriverWait(driver, 10).until(EC.presence_of_element_located((
                By.CSS_SELECTOR,
                "input[type='password'], input[name='password'], input[name='Passwd']"
            )))
            pw_input.clear()
            pw_input.send_keys(password)
            _log(log_callback, "Đã nhập mật khẩu.")
            time.sleep(0.5)
        except Exception as e:
            _log(log_callback, f"Không tìm thấy ô mật khẩu (có thể cần 2FA): {e}")
            return
        try:
            next_btn = WebDriverWait(driver, 8).until(EC.element_to_be_clickable((
                By.XPATH,
                "//span[text()='Next']/.. | //span[text()='Tiếp']/.. | //button[.//span[text()='Next']] | //*[text()='Tiếp']/ancestor::div[@role='button']"
            )))
            next_btn.click()
            time.sleep(5)
        except Exception:
            try:
                next_btn = driver.find_element(By.CSS_SELECTOR, "#passwordNext button, button[type='submit']")
                next_btn.click()
                time.sleep(5)
            except Exception:
                pass
        time.sleep(3)
        if "accounts.google.com" in driver.current_url:
            _log(log_callback, "Có thể cần xác minh 2 bước hoặc captcha — vui lòng đăng nhập tay trên Chrome.")
        else:
            _log(log_callback, "Đã đăng nhập xong (tự động).")
    except Exception as e:
        _log(log_callback, f"Tự động đăng nhập lỗi: {e}")


def init_driver(headless=False, use_saved_profile=True, profile_dir=None):
    """
    Khởi tạo Chrome WebDriver để dùng cho upload.
    :param headless: Chạy ẩn browser (không nên dùng vì cần đăng nhập thủ công).
    :return: WebDriver instance hoặc None nếu lỗi.
    """
    # Giả thuyết:
    # H1: Không tìm thấy Chrome hoặc ChromeDriver -> WebDriverException ở webdriver.Chrome
    # H2: Lỗi khi tạo/thao tác thư mục profile (quyền, đường dẫn sai)
    # H3: Fallback Edge cũng lỗi do không có Edge hoặc driver tương ứng
    try:
        options = Options()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        # Giữ trình duyệt mở để user có thể đăng nhập
        options.add_experimental_option("detach", False)

        chosen_profile_dir = None
        if use_saved_profile:
            chosen_profile_dir = profile_dir or CHROME_PROFILE_DIR
            _agent_debug_log(
                "H2",
                "About to create/use Chrome profile directory",
                {"profileDir": chosen_profile_dir},
            )
            os.makedirs(chosen_profile_dir, exist_ok=True)
            options.add_argument(f"--user-data-dir={chosen_profile_dir}")
            options.add_argument("--profile-directory=Default")

        _agent_debug_log(
            "H1",
            "Attempting to start Chrome WebDriver",
            {"useSavedProfile": use_saved_profile, "profileDir": chosen_profile_dir},
        )
        # Thử dùng Chrome mặc định (chromedriver trong PATH hoặc Selenium Manager)
        driver = webdriver.Chrome(options=options)
        driver.maximize_window()
        driver.implicitly_wait(10)
        _agent_debug_log(
            "H1",
            "Chrome WebDriver started successfully",
            {"useSavedProfile": use_saved_profile},
            run_id="init_driver_post",
        )
        return driver
    except WebDriverException as e:
        # Chỉ dùng Chrome, không fallback Edge
        _agent_debug_log(
            "H1",
            "Chrome WebDriver failed with WebDriverException (no Edge fallback)",
            {"error": str(e)},
            run_id="init_driver_error",
        )
        # Ném lại lỗi để phía trên ghi log rõ ràng, tránh tự động chuyển sang Edge
        raise e


def _try_get_video_link_from_page(driver):
    """Thử lấy link video từ trang hiện tại (trước hoặc sau khi bấm Done). Trả về url hoặc None."""
    try:
        link_el = driver.find_elements(By.CSS_SELECTOR, "ytcp-video-info a[href*='youtu.be'], ytcp-video-info a[href*='youtube.com/watch']")
        if not link_el:
            link_el = driver.find_elements(By.CSS_SELECTOR, "a[href*='youtu.be'], a[href*='youtube.com/watch']")
        if link_el:
            url = link_el[0].get_attribute("href")
            if url:
                return url.split("&")[0].strip()
        page_source = driver.page_source
        for pattern in (r"https?://(?:www\.)?youtu\.be/[\w-]+", r"https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+"):
            match = re.search(pattern, page_source)
            if match:
                return match.group(0).split("&")[0]
    except Exception:
        pass
    return None


def upload_video(driver, file_path, video_title="tool", made_for_kids=False, visibility="unlisted", log_callback=None, on_link_available=None):
    """
    Upload một video lên YouTube qua YouTube Studio.
    :param driver: WebDriver từ init_driver()
    :param file_path: Đường dẫn file video (mp4, mov, ...)
    :param video_title: Tiêu đề video
    :param made_for_kids: True = Made for kids
    :param visibility: 'public' | 'unlisted' | 'private'
    :param log_callback: Hàm callback(str) để ghi log
    :param on_link_available: Hàm callback(url) gọi khi có link (trước hoặc sau Done) để log + cập nhật Excel
    :return: dict {'success': bool, 'url': str|None, 'error': str|None, 'excel_done': bool}
    """
    if not driver or not os.path.isfile(file_path):
        return {"success": False, "url": None, "error": "Driver hoặc file không hợp lệ"}

    result = {"success": False, "url": None, "error": None, "excel_done": False}
    wait = WebDriverWait(driver, 60)
    file_path_abs = os.path.abspath(file_path)

    try:
        # Mở YouTube Studio
        _log(log_callback, "Đang mở YouTube Studio...")
        driver.get(YOUTUBE_STUDIO_URL)
        time.sleep(3)

        # Chờ có thể đã đăng nhập (hoặc đang ở trang login)
        # Tìm nút "Create" / "Upload" để mở form upload
        try:
            # Cách 1: Link/button "Upload videos" hoặc "Create"
            upload_btn = wait.until(EC.element_to_be_clickable((
                By.CSS_SELECTOR,
                "ytcp-button#upload-icon, [aria-label*='Upload'], [aria-label*='upload'], "
                "tp-yt-paper-button#upload-icon, #upload-icon"
            )))
            upload_btn.click()
            _log(log_callback, "Đã mở form upload.")
        except TimeoutException:
            # Cách 2: Thử đi thẳng tới upload (một số phiên bản dùng path)
            driver.get("https://studio.youtube.com/channel/upload")
            _log(log_callback, "Đang chuyển tới trang upload...")
        time.sleep(2)

        # Chọn file: input[type="file"]
        file_input = wait.until(EC.presence_of_element_located((
            By.CSS_SELECTOR, "input[type='file']"
        )))
        file_input.send_keys(file_path_abs)
        _log(log_callback, "Đã chọn file video, đang chờ xử lý...")
        time.sleep(3)

        # Tiêu đề: có nhập trong cấu hình thì điền; không nhập thì bỏ qua, chạy luôn bước Có/Không trẻ em (radio đã có sẵn)
        # YouTube Studio dùng div contenteditable cho ô tiêu đề, không phải input
        if video_title and str(video_title).strip():
            try:
                title_selector = (
                    "#title-textarea div#textbox[contenteditable='true'], "
                    "ytcp-social-suggestions-textbox#title-textarea div#textbox, "
                    "div#textbox[role='textbox'][aria-label*='tiêu đề'], "
                    "[aria-label*='Thêm tiêu đề']"
                )
                title_el = WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, title_selector))
                )
                title_el.click()
                time.sleep(0.3)
                # Clear contenteditable: Ctrl+A rồi gõ mới
                title_el.send_keys(Keys.CONTROL + "a")
                title_el.send_keys(Keys.BACKSPACE)
                time.sleep(0.2)
                title_el.send_keys(str(video_title).strip())
                _log(log_callback, "Đã điền tiêu đề.")
            except TimeoutException:
                _log(log_callback, "Không tìm thấy ô tiêu đề, bỏ qua (có thể dùng tên file).")
        else:
            _log(log_callback, "Không điền tiêu đề (để trống), chạy luôn phần Có/Không trẻ em.")

        # Bước 2: Có / Không - Nội dung dành cho trẻ em (chờ chậm, xác định rõ đã pick Yes/No rồi mới chọn)
        time.sleep(3)
        want_yes = bool(made_for_kids)
        try:
            # #region agent log
            try:
                _agent_debug_log(
                    "K1",
                    "Selecting made_for_kids radio",
                    {"madeForKids": want_yes, "url": driver.current_url},
                    run_id="kids_select_pre",
                )
            except Exception:
                pass
            # #endregion agent log
            # Chờ cả hai radio có trên trang rồi mới chọn (tránh click nhầm)
            WebDriverWait(driver, 15).until(EC.presence_of_element_located((
                By.CSS_SELECTOR, "tp-yt-paper-radio-button[name='VIDEO_MADE_FOR_KIDS_MFK']"
            )))
            WebDriverWait(driver, 5).until(EC.presence_of_element_located((
                By.CSS_SELECTOR, "tp-yt-paper-radio-button[name='VIDEO_MADE_FOR_KIDS_NOT_MFK']"
            )))
            time.sleep(0.5)
            yes_el = driver.find_element(By.CSS_SELECTOR, "tp-yt-paper-radio-button[name='VIDEO_MADE_FOR_KIDS_MFK']")
            no_el = driver.find_element(By.CSS_SELECTOR, "tp-yt-paper-radio-button[name='VIDEO_MADE_FOR_KIDS_NOT_MFK']")
            target = yes_el if want_yes else no_el
            # #region agent log
            try:
                _agent_debug_log(
                    "K1b",
                    "Kids radio about to click",
                    {"target": "MFK" if want_yes else "NOT_MFK", "want_yes": want_yes},
                    run_id="kids_click_pre",
                )
            except Exception:
                pass
            # #endregion agent log
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target)
            time.sleep(0.3)
            WebDriverWait(driver, 8).until(EC.element_to_be_clickable(target))
            try:
                target.click()
            except Exception:
                driver.execute_script("arguments[0].click();", target)
            time.sleep(0.8)
            yes_checked = (yes_el.get_attribute("aria-checked") or "").strip().lower()
            no_checked = (no_el.get_attribute("aria-checked") or "").strip().lower()
            try:
                _agent_debug_log(
                    "K2",
                    "Kids radio aria-checked after click",
                    {"yes": yes_checked, "no": no_checked, "expected": "yes" if want_yes else "no"},
                    run_id="kids_select_post",
                )
            except Exception:
                pass
            if want_yes and yes_checked != "true":
                try:
                    driver.execute_script("arguments[0].click();", yes_el)
                    time.sleep(0.5)
                except Exception:
                    pass
            if (not want_yes) and no_checked != "true":
                try:
                    driver.execute_script("arguments[0].click();", no_el)
                    time.sleep(0.5)
                except Exception:
                    pass
            # #region agent log — trạng thái cuối sau retry
            try:
                yes_checked_final = (yes_el.get_attribute("aria-checked") or "").strip().lower()
                no_checked_final = (no_el.get_attribute("aria-checked") or "").strip().lower()
                _agent_debug_log(
                    "K3",
                    "Kids radio final state after retry",
                    {"yes": yes_checked_final, "no": no_checked_final, "want_yes": want_yes},
                    run_id="kids_select_final",
                )
            except Exception:
                pass
            # #endregion agent log
            if want_yes:
                _log(log_callback, "Đã chọn: Có, nội dung dành cho trẻ em.")
            else:
                _log(log_callback, "Đã chọn: Không, nội dung không dành cho trẻ em.")
        except Exception:
            try:
                if want_yes:
                    kids_yes = driver.find_elements(By.CSS_SELECTOR, "tp-yt-paper-radio-button[name='VIDEO_MADE_FOR_KIDS_MFK']")
                    if not kids_yes:
                        kids_yes = driver.find_elements(By.XPATH, "//*[contains(@aria-label,'trẻ em') or contains(@aria-label,'kids') or contains(text(),'Có') or contains(text(),'Yes')]")
                    for el in kids_yes:
                        try:
                            if "MFK" in (el.get_attribute("name") or "") or "kids" in (el.get_attribute("aria-label") or "").lower():
                                el.click()
                                _log(log_callback, "Đã chọn: Có, nội dung dành cho trẻ em.")
                                break
                        except Exception:
                            pass
                else:
                    kids_no = driver.find_elements(By.CSS_SELECTOR, "tp-yt-paper-radio-button[name='VIDEO_MADE_FOR_KIDS_NOT_MFK']")
                    if not kids_no:
                        kids_no = driver.find_elements(By.XPATH, "//*[contains(@aria-label,'Không') or contains(@aria-label,'No') or contains(text(),'Không') or contains(text(),'No')]")
                    for el in kids_no:
                        try:
                            if "NOT_MFK" in (el.get_attribute("name") or "") or "không" in (el.get_attribute("aria-label") or "").lower() or "no" in (el.get_attribute("aria-label") or "").lower():
                                el.click()
                                _log(log_callback, "Đã chọn: Không, nội dung không dành cho trẻ em.")
                                break
                        except Exception:
                            pass
            except Exception:
                pass
        time.sleep(1)

        # Bước 3–4: Next hai lần — lần 1: Chi tiết → Các thành phần của video; lần 2: sang Kiểm tra ban đầu
        if not _click_next(driver, log_callback, "Chi tiết → Các thành phần của video"):
            result["error"] = "Không chuyển được sang bước Các thành phần của video"
            _log(log_callback, f"❌ {result['error']}. Chuyển video khác.")
            return result
        time.sleep(2)
        if not _click_next(driver, log_callback, "Các thành phần của video → Kiểm tra ban đầu"):
            result["error"] = "Không chuyển được sang bước Kiểm tra ban đầu"
            _log(log_callback, f"❌ {result['error']}. Chuyển video khác.")
            return result
        time.sleep(2)

        # Bước 5: Kiểm tra ban đầu — không báo gì thì Next; có bản quyền thì xử lý thay thế bài hát
        if not _handle_checks_and_copyright(driver, wait, log_callback):
            result["error"] = "Không hoàn thành bước kiểm tra/bản quyền"
            return result
        time.sleep(1)

        # Một số luồng (đặc biệt khi xử lý bản quyền / thay thế bài hát) có thể đã đưa thẳng tới bước
        # Chế độ hiển thị, nên không còn nút Next nữa. Nếu đã thấy #privacy-radios thì bỏ qua click Next.
        already_on_visibility = False
        try:
            try:
                _agent_debug_log(
                    "V1",
                    "Checking if already on visibility step (#privacy-radios)",
                    {"url": driver.current_url},
                    run_id="visibility_check_pre",
                )
            except Exception:
                pass
            WebDriverWait(driver, 3).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#privacy-radios"))
            )
            # #region agent log
            try:
                el = driver.find_element(By.CSS_SELECTOR, "#privacy-radios")
                uploads_dialog_present = bool(driver.find_elements(By.CSS_SELECTOR, "ytcp-uploads-dialog"))
                _agent_debug_log(
                    "V1",
                    "Found #privacy-radios during visibility check",
                    {
                        "url": driver.current_url,
                        "privacyRadiosDisplayed": bool(getattr(el, "is_displayed", lambda: None)()),
                        "uploadsDialogPresent": uploads_dialog_present,
                    },
                    run_id="visibility_check_detail",
                )
            except Exception:
                pass
            # #endregion agent log
            already_on_visibility = True
            try:
                _agent_debug_log(
                    "V1",
                    "Detected visibility step already present; skipping Next",
                    {"url": driver.current_url},
                    run_id="visibility_check_post",
                )
            except Exception:
                pass
        except Exception:
            already_on_visibility = False

        if not already_on_visibility:
            if not _click_next(driver, log_callback, "Sau kiểm tra ban đầu"):
                result["error"] = "Không chuyển được sang Chế độ hiển thị"
                _log(log_callback, f"❌ {result['error']}. Chuyển video khác.")
                return result
            time.sleep(2)

        # Bước 6: Chế độ hiển thị (ytcp-uploads-review) — chọn Riêng tư / Không công khai / Công khai, rồi Lưu và lấy link
        # Radio: tp-yt-paper-radio-button name="PRIVATE"|"UNLISTED"|"PUBLIC" trong #privacy-radios
        visibility_name_map = {
            "public": "PUBLIC",
            "unlisted": "UNLISTED",
            "private": "PRIVATE",
        }
        visibility_label_map = {
            "public": ["Công khai", "Public"],
            "unlisted": ["Không công khai", "Unlisted"],
            "private": ["Riêng tư", "Private"],
        }
        visibility_key = visibility.lower()
        visibility_name = visibility_name_map.get(visibility_key, "UNLISTED")
        visibility_labels = visibility_label_map.get(visibility_key, visibility_label_map["unlisted"])

        chosen = False
        # Ưu tiên chọn trực tiếp radio trong nhóm #privacy-radios theo name
        try:
            # #region agent log
            try:
                _agent_debug_log(
                    "V2",
                    "Attempting visibility select by name",
                    {"visibilityKey": visibility_key, "visibilityName": visibility_name, "url": driver.current_url},
                    run_id="visibility_select_pre",
                )
            except Exception:
                pass
            # #endregion agent log
            radio = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((
                    By.CSS_SELECTOR,
                    f"#privacy-radios tp-yt-paper-radio-button[name='{visibility_name}']"
                ))
            )
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", radio)
            WebDriverWait(driver, 10).until(EC.element_to_be_clickable((
                By.CSS_SELECTOR,
                f"#privacy-radios tp-yt-paper-radio-button[name='{visibility_name}']"
            )))
            try:
                radio.click()
            except Exception:
                driver.execute_script("arguments[0].click();", radio)
            # #region agent log
            try:
                _agent_debug_log(
                    "V2",
                    "Visibility select by name clicked",
                    {
                        "visibilityName": visibility_name,
                        "ariaChecked": radio.get_attribute("aria-checked"),
                        "url": driver.current_url,
                    },
                    run_id="visibility_select_post",
                )
            except Exception:
                pass
            # #endregion agent log
            _log(log_callback, f"Đã chọn visibility (theo name): {visibility_key}")
            chosen = True
        except Exception:
            chosen = False

        # Fallback 1: tìm theo #radioLabel text (tiếng Việt + tiếng Anh)
        if not chosen:
            try:
                radios = driver.find_elements(
                    By.CSS_SELECTOR,
                    "#privacy-radios tp-yt-paper-radio-button"
                )
                for r in radios:
                    try:
                        label_el = r.find_element(By.CSS_SELECTOR, "#radioLabel")
                        label_text = (label_el.text or "").strip()
                        if any(label_text == l for l in visibility_labels):
                            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", r)
                            WebDriverWait(driver, 5).until(EC.element_to_be_clickable(r))
                            try:
                                r.click()
                            except Exception:
                                driver.execute_script("arguments[0].click();", r)
                            # #region agent log
                            try:
                                _agent_debug_log(
                                    "V3",
                                    "Visibility select by #radioLabel clicked",
                                    {
                                        "labelText": label_text,
                                        "ariaChecked": r.get_attribute("aria-checked"),
                                        "url": driver.current_url,
                                    },
                                    run_id="visibility_select_post",
                                )
                            except Exception:
                                pass
                            # #endregion agent log
                            _log(log_callback, f"Đã chọn visibility (theo #radioLabel): {label_text}")
                            chosen = True
                            break
                    except Exception:
                        continue
            except Exception:
                pass

        # Fallback 2: match theo aria-label/text tổng nếu vẫn chưa chọn được
        if not chosen:
            visibility_map = {
                "public": ["Public", "Công khai", "PUBLIC"],
                "unlisted": ["Unlisted", "Không công khai", "UNLISTED"],
                "private": ["Private", "Riêng tư", "PRIVATE"],
            }
            target_visibility = visibility_map.get(visibility_key, visibility_map["unlisted"])
            for r in driver.find_elements(By.CSS_SELECTOR, "#privacy-radios tp-yt-paper-radio-button, tp-yt-paper-radio-button, [role='radio']"):
                try:
                    label = (r.get_attribute("aria-label") or r.text or "").strip()
                    if any(v in label for v in target_visibility):
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", r)
                        try:
                            r.click()
                        except Exception:
                            driver.execute_script("arguments[0].click();", r)
                        _log(log_callback, f"Đã chọn visibility (theo label fallback): {visibility_key}")
                        chosen = True
                        break
                except Exception:
                    continue

        if not chosen:
            _log(log_callback, "⚠️ Không chọn được radio chế độ hiển thị, YouTube có thể đã đổi giao diện.")
        time.sleep(1)

        # Thử lấy link ngay sau khi chọn visibility (trước khi bấm Lưu) — để log + Excel trước, rồi mới bấm Lưu/Xuất bản
        early_url = _try_get_video_link_from_page(driver)
        if early_url:
            result["url"] = early_url
            result["success"] = True
            _log(log_callback, f"Link video: {result['url']}")
            if on_link_available:
                try:
                    on_link_available(early_url)
                except Exception:
                    pass
                result["excel_done"] = True

        # Bấm "Lưu" / Done (bước Chế độ hiển thị: #done-button hiện, #next-button ẩn)
        try:
            # Tìm đúng ytcp-button#done-button trong footer như DOM bạn gửi
            done_outer = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((
                    By.CSS_SELECTOR,
                    "ytcp-uploads-dialog ytcp-button#done-button, ytcp-button#done-button"
                ))
            )
            done_inner = done_outer.find_element(
                By.CSS_SELECTOR,
                "button[aria-label='Lưu'], button.ytcpButtonShapeImplHost"
            )
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", done_inner)
            WebDriverWait(driver, 10).until(EC.element_to_be_clickable(done_inner))
            try:
                done_inner.click()
            except Exception:
                driver.execute_script("arguments[0].click();", done_inner)
            _log(log_callback, "Đã bấm Lưu / Xuất bản ở bước Chế độ hiển thị.")
        except TimeoutException:
            result["error"] = "Không tìm thấy nút Lưu/Done"
            _log(log_callback, f"❌ {result['error']}")
            return result

        # Sau khi bấm Done, đôi khi YouTube hiện cảnh báo pre-checks -> cần xác nhận "Vẫn xuất bản"
        try:
            _handle_prechecks_warning_after_done(driver, log_callback=log_callback)
        except Exception:
            pass

        time.sleep(5)

        # Lấy link video nếu chưa có (sau khi bấm Done)
        if not result.get("url"):
            try:
                url = _try_get_video_link_from_page(driver)
                if url:
                    result["url"] = url
                    result["success"] = True
                    _log(log_callback, f"Link video: {result['url']}")
                    if on_link_available and not result.get("excel_done"):
                        try:
                            on_link_available(url)
                        except Exception:
                            pass
                        result["excel_done"] = True
                else:
                    result["success"] = True
                    result["url"] = None
                    _log(log_callback, "Upload có thể đã xong nhưng chưa lấy được link (kiểm tra Studio).")
            except Exception as e:
                result["success"] = True
                result["url"] = None
                result["error"] = str(e)

    except Exception as e:
        result["success"] = False
        result["error"] = str(e)
        _log(log_callback, f"Lỗi upload: {e}")

    return result


def generate_excel(logs, excel_filename="YouTube_Upload_Links.xlsx", log_callback=None):
    """
    Tạo file Excel chứa danh sách link YouTube từ logs.
    Logs: list of dict {'timestamp': str, 'message': str}
    Tìm các dòng message chứa "Link: https://..."
    :return: Đường dẫn file Excel đã lưu, hoặc None.
    """
    if not OPENPYXL_AVAILABLE:
        _log(log_callback, "Thiếu thư viện openpyxl, không tạo được Excel.")
        return None

    # Parse links và tên file từ logs
    link_re = re.compile(r"Link:\s*(https?://[^\s]+)")
    upload_re = re.compile(r"Đang upload:\s*(.+)")
    success_re = re.compile(r"✅\s*Upload thành công:\s*(.+)")

    rows = []
    current_file = None
    for entry in logs:
        msg = entry.get("message", "")
        link_m = link_re.search(msg)
        upload_m = upload_re.search(msg)
        success_m = success_re.search(msg)
        if upload_m:
            current_file = upload_m.group(1).strip()
        if success_m:
            current_file = success_m.group(1).strip()
        if link_m:
            url = link_m.group(1).strip()
            if "youtube.com/watch" in url:
                url = url.split("&")[0]
            rows.append({"file": current_file or "N/A", "url": url})

    if not rows:
        _log(log_callback, "Không tìm thấy link nào trong logs để ghi Excel.")
        return None

    wb = Workbook()
    ws = wb.active
    ws.title = "YouTube Links"
    ws.append(["STT", "Tên file", "Link YouTube", "Thời gian"])
    for i, r in enumerate(rows, 1):
        ws.append([i, r["file"], r["url"], datetime.now().strftime("%Y-%m-%d %H:%M")])
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for col in ws.columns:
        max_len = max(len(str(c.value) or "") for c in col)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 80)

    output_dir = os.path.join(os.getcwd(), "output")
    os.makedirs(output_dir, exist_ok=True)
    safe_name = "".join(c for c in excel_filename if c.isalnum() or c in "._- ") or "YouTube_Upload_Links.xlsx"
    if not safe_name.endswith(".xlsx"):
        safe_name += ".xlsx"
    file_path = os.path.join(output_dir, safe_name)
    wb.save(file_path)
    return file_path
