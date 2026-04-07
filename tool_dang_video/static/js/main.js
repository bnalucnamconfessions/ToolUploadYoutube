let statusInterval = null;
let isRunning = false;
let selectedFolderPath = null;

// Bộ nhớ tạm cho Made for kids — tránh nhầm khi gửi request (ưu tiên giá trị user vừa chọn)
const MADE_FOR_KIDS_STORAGE_KEY = 'made_for_kids_choice';

// Favicon blink when error happens
let _favBlinkTimer = null;
let _favBlinkStopTimer = null;
let _favBlinkOn = false;
let _lastFailCount = 0;
let _lastErrorSig = '';
let _lastWasRunning = false;
let _lastProgress = 0;

function _faviconSvgDataUrl(dotColorHex) {
    const dot = dotColorHex
        ? ("<circle cx='52' cy='12' r='8' fill='" + dotColorHex + "' stroke='white' stroke-width='3'/>")
        : "";
    const svg =
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'>" +
        "<rect width='64' height='64' rx='14' fill='%23111827'/>" +
        "<path d='M25 21h16a6 6 0 0 1 6 6v10a6 6 0 0 1-6 6H25a6 6 0 0 1-6-6V27a6 6 0 0 1 6-6z' fill='%23ef4444'/>" +
        "<path d='M29 27l12 6-12 6V27z' fill='white'/>" +
        dot +
        "</svg>";
    return "data:image/svg+xml," + encodeURIComponent(svg);
}

function _setFaviconDotColor(dotColorHexOrEmpty) {
    const el = document.getElementById('appFavicon') || document.querySelector('link[rel~="icon"]');
    if (!el) return;
    el.href = _faviconSvgDataUrl(dotColorHexOrEmpty || "");
}

function _triggerFaviconBlink(dotColorHex, durationMs = 8000) {
    try {
        if (_favBlinkStopTimer) clearTimeout(_favBlinkStopTimer);
        _favBlinkStopTimer = setTimeout(() => {
            if (_favBlinkTimer) clearInterval(_favBlinkTimer);
            _favBlinkTimer = null;
            _favBlinkOn = false;
            _setFaviconDotColor("");
        }, durationMs);

        if (_favBlinkTimer) return; // already blinking
        _favBlinkTimer = setInterval(() => {
            _favBlinkOn = !_favBlinkOn;
            _setFaviconDotColor(_favBlinkOn ? dotColorHex : "");
        }, 500);
    } catch (e) {}
}

function triggerFaviconErrorBlink(durationMs = 8000) {
    _triggerFaviconBlink('%23f59e0b', durationMs); // amber
}

function triggerFaviconSuccessBlink(durationMs = 6000) {
    _triggerFaviconBlink('%2322c55e', durationMs); // green
}

function syncMadeForKidsChoice() {
    const checked = document.querySelector('input[name="made_for_kids"]:checked');
    const value = (checked && checked.value) ? checked.value : 'no';
    try { localStorage.setItem(MADE_FOR_KIDS_STORAGE_KEY, value); } catch (e) {}
}

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    // Form submission
    document.getElementById('uploadForm').addEventListener('submit', function(e) {
        e.preventDefault();
        startUpload();
    });

    // Đồng bộ Made for kids vào bộ nhớ tạm khi load và mỗi khi đổi lựa chọn
    syncMadeForKidsChoice();
    document.querySelectorAll('input[name="made_for_kids"]').forEach(function(radio) {
        radio.addEventListener('change', syncMadeForKidsChoice);
    });
    
    // Download button
    document.getElementById('downloadBtn').addEventListener('click', downloadExcel);
    const downloadLogBtn = document.getElementById('downloadLogBtn');
    if (downloadLogBtn) {
        downloadLogBtn.addEventListener('click', downloadUploadLog);
    }
    
    // Continue login button
    document.getElementById('continueLoginBtn').addEventListener('click', continueLogin);
    
    // Start polling for status
    pollStatus();

    // Thông báo từ xa (GitHub Raw / Gist) — gọi trong pageshow để luôn hiện khi vào/quay lại trang chủ
});

// Hiện thông báo từ xa khi vào trang chủ, nhưng không hiện khi vừa quay lại sau chọn tài khoản
window.addEventListener('pageshow', function() {
    if (!document.getElementById('remote-notice')) return;
    try {
        if (sessionStorage.getItem('skip_notice_return') === '1') {
            sessionStorage.removeItem('skip_notice_return');
            return;
        }
    } catch (e) {}
    loadRemoteNotice();
});

function loadRemoteNotice() {
    // Cache-busting: mỗi lần mở trang gọi URL khác nhau để không dùng bản cache
    fetch('/api/notice?_=' + Date.now())
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (!data || !data.success || !data.notice) return;
            var n = data.notice;
            var title = (n.title || '').trim();
            var rawMessage = n.message;
            var message = '';
            if (Array.isArray(rawMessage)) {
                message = rawMessage.join('\n\n');
            } else {
                message = (rawMessage || '').trim();
            }
            if (!title && !message) return;
            var el = document.getElementById('remote-notice');
            if (!el) return;
            var titleEl = document.getElementById('remote-notice-title');
            var msgEl = document.getElementById('remote-notice-message');
            var linkEl = document.getElementById('remote-notice-link');
            if (titleEl) titleEl.textContent = title;
            if (msgEl) msgEl.textContent = message;
            if (linkEl && n.link) {
                linkEl.href = n.link;
                linkEl.textContent = (n.linkText || 'Xem thêm');
                linkEl.style.display = '';
            } else if (linkEl) linkEl.style.display = 'none';
            el.style.display = '';
            var closeBtn = el.querySelector('.remote-notice-close');
            if (closeBtn) {
                // Khóa nút X trong 10s đầu để user có thời gian đọc
                closeBtn.disabled = true;
                setTimeout(function() {
                    closeBtn.disabled = false;
                }, 10000);
                closeBtn.onclick = function() {
                    if (closeBtn.disabled) return;
                    el.style.display = 'none';
                };
            }
        })
        .catch(function() {});
}

function selectFolder() {
    // Trigger file picker để chọn folder
    document.getElementById('folderPicker').click();
}

async function handleFolderSelect(event) {
    const files = event.target.files;
    if (files.length === 0) {
        addLog('warning', '⚠️ Không có file nào được chọn');
        return;
    }
    
    // Lọc video files
    const videoExtensions = ['.mp4', '.mov', '.mkv', '.avi', '.wmv', '.flv', '.webm'];
    const videoFiles = Array.from(files).filter(f => {
        const ext = f.name.toLowerCase().substring(f.name.lastIndexOf('.'));
        return videoExtensions.includes(ext);
    });
    
    if (videoFiles.length === 0) {
        addLog('error', '❌ Không tìm thấy file video nào trong folder đã chọn');
        addLog('info', '💡 Chỉ hỗ trợ các định dạng: .mp4, .mov, .mkv, .avi, .wmv, .flv, .webm');
        return;
    }
    
    addLog('info', `📁 Đang upload ${videoFiles.length} video file(s) từ folder đã chọn...`);
    
    // Disable button trong khi upload
    const selectBtn = document.querySelector('button[onclick="selectFolder()"]');
    const originalText = selectBtn.innerHTML;
    selectBtn.disabled = true;
    selectBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Đang upload...';
    
    // Tạo FormData để upload files
    const formData = new FormData();
    for (let i = 0; i < videoFiles.length; i++) {
        formData.append('files[]', videoFiles[i]);
    }
    
    try {
        const response = await fetch('/api/upload-files', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok) {
            selectedFolderPath = data.folder;
            document.getElementById('folder').value = data.folder;
            addLog('success', `✅ Đã upload ${data.files.length} video file(s) thành công`);
            addLog('info', `📂 Folder: ${data.folder}`);
            addLog('info', `📋 Files: ${data.files.join(', ')}`);
        } else {
            addLog('error', `❌ Lỗi upload files: ${data.error}`);
        }
    } catch (error) {
        addLog('error', `❌ Lỗi kết nối: ${error.message}`);
    } finally {
        // Re-enable button
        selectBtn.disabled = false;
        selectBtn.innerHTML = originalText;
    }
}

async function startUpload() {
    const folder = document.getElementById('folder').value;
    
    if (!folder) {
        addLog('error', '❌ Vui lòng chọn folder chứa video trước!');
        return;
    }
    
    // Ưu tiên giá trị từ bộ nhớ tạm (đã sync khi user chọn radio) để tránh nhầm
    const madeForKids = (function() {
        try {
            const stored = localStorage.getItem(MADE_FOR_KIDS_STORAGE_KEY);
            if (stored === 'yes' || stored === 'no') return stored;
        } catch (e) {}
        const checked = document.querySelector('input[name="made_for_kids"]:checked');
        return (checked && checked.value) ? checked.value : 'no';
    })();

    const formData = {
        folder: folder,
        made_for_kids: madeForKids,
        visibility: document.querySelector('input[name="visibility"]:checked').value,
        excel_filename: document.getElementById('excel_filename').value
    };
    
    try {
        // Lưu cấu hình tạm, chuyển sang trang chọn tài khoản (profile Chrome)
        localStorage.setItem('pendingUploadConfig', JSON.stringify(formData));
        window.location.href = '/select-account';
    } catch (error) {
        addLog('error', `❌ Lỗi kết nối: ${error.message}`);
    }
}

async function pollStatus() {
    try {
        const response = await fetch('/api/status');
        const status = await response.json();
        
        updateStatus(status);
        
        if (status.is_running !== isRunning) {
            isRunning = status.is_running;
            updateButtons();
        }
    } catch (error) {
        console.error('Error polling status:', error);
    }
    
    // Poll every 1 second
    setTimeout(pollStatus, 1000);
}

function updateStatus(status) {
    // Update status text
    const statusText = status.is_running ? 'Đang chạy...' : 'Chưa bắt đầu';
    document.getElementById('statusText').textContent = statusText;
    document.getElementById('statusText').className = status.is_running ? 'status-value running' : 'status-value';
    
    // Update total files
    document.getElementById('totalFiles').textContent = status.total_files || 0;
    
    // Update current file
    document.getElementById('currentFile').textContent = status.current_file || '-';
    
    // Update counts
    document.getElementById('successCount').textContent = status.success_count || 0;
    document.getElementById('failCount').textContent = status.fail_count || 0;

    // Blink favicon when completed / new error appears
    try {
        const isNowRunning = !!status.is_running;

        const failCount = Number(status.fail_count || 0);
        let hasNewError = failCount > _lastFailCount;
        _lastFailCount = failCount;

        // Also detect new ❌ log line (works even if fail_count doesn't change)
        const logs = Array.isArray(status.logs) ? status.logs : [];
        const lastMsg = logs.length ? String(logs[logs.length - 1].message || '') : '';
        const errSig = (lastMsg.includes('❌') || lastMsg.includes('Lỗi')) ? (String(logs[logs.length - 1].timestamp || '') + '|' + lastMsg.slice(0, 120)) : '';
        if (errSig && errSig !== _lastErrorSig) {
            _lastErrorSig = errSig;
            hasNewError = true;
        }

        if (hasNewError) triggerFaviconErrorBlink(8000);

        // Completed: running -> not running AND progress >= 100 (or last log says done)
        try {
            const progressNow = Number(status.progress || 0);
            const doneByProgress = (_lastWasRunning && !isNowRunning && progressNow >= 100);
            const doneByLog = (_lastWasRunning && !isNowRunning && (lastMsg.includes('Hoàn thành upload') || lastMsg.includes('Hoàn thành Upload')));
            if (doneByProgress || doneByLog) triggerFaviconSuccessBlink(6000);
            _lastProgress = progressNow;
        } catch (e2) {}

        _lastWasRunning = isNowRunning;
    } catch (e) {}
    
    // Update progress
    const progress = status.progress || 0;
    document.getElementById('progressFill').style.width = progress + '%';
    document.getElementById('progressText').textContent = progress + '%';
    
    // Update logs
    updateLogs(status.logs);
    
    // Show download button if excel file exists
    const downloadBtn = document.getElementById('downloadBtn');
    if (status.excel_file) {
        downloadBtn.classList.remove('hidden');
        downloadBtn.classList.add('visible');
    } else {
        downloadBtn.classList.add('hidden');
        downloadBtn.classList.remove('visible');
    }
    const downloadLogBtn = document.getElementById('downloadLogBtn');
    if (downloadLogBtn) {
        if (status.session_log_file) {
            downloadLogBtn.classList.remove('hidden');
            downloadLogBtn.classList.add('visible');
        } else {
            downloadLogBtn.classList.add('hidden');
            downloadLogBtn.classList.remove('visible');
        }
    }
    
    // Show continue login button if waiting for login
    const continueLoginBtn = document.getElementById('continueLoginBtn');
    if (status.waiting_for_login) {
        continueLoginBtn.classList.remove('hidden');
        continueLoginBtn.classList.add('visible');
    } else {
        continueLoginBtn.classList.add('hidden');
        continueLoginBtn.classList.remove('visible');
    }
    
    // Update button states based on actual status
    if (status.is_running !== isRunning) {
        isRunning = status.is_running;
        updateButtons();
    }
}

function updateLogs(logs) {
    const container = document.getElementById('logsContainer');
    
    if (!logs || logs.length === 0) {
        container.innerHTML = '<div class="log-empty">Chưa có logs...</div>';
        return;
    }
    
    // Chuẩn hóa + lọc nhiễu + gộp log trùng liên tiếp
    const normalized = [];
    logs.slice(-300).forEach(log => {
        const ts = (log && log.timestamp) ? String(log.timestamp) : '';
        const rawMsg = (log && log.message) ? String(log.message) : '';
        const msg = sanitizeLogMessage(rawMsg);
        if (!msg || isNoisyLogMessage(msg)) return;
        const prev = normalized.length ? normalized[normalized.length - 1] : null;
        if (prev && prev.message === msg) {
            prev.count += 1;
            prev.lastTimestamp = ts || prev.lastTimestamp;
        } else {
            normalized.push({
                timestamp: ts,
                lastTimestamp: ts,
                message: msg,
                count: 1
            });
        }
    });

    if (!normalized.length) {
        container.innerHTML = '<div class="log-empty">Chưa có logs...</div>';
        return;
    }

    // Clear and render
    container.innerHTML = '';
    normalized.slice(-120).forEach(log => {
        const entry = document.createElement('div');
        entry.className = 'log-entry';
        
        // Determine log type
        const m = log.message.toLowerCase();
        if (log.message.includes('✅') || m.includes('thành công')) {
            entry.classList.add('success');
        } else if (log.message.includes('❌') || m.includes('lỗi')) {
            entry.classList.add('error');
        } else if (log.message.includes('⚠') || m.includes('cảnh báo')) {
            entry.classList.add('warning');
        }
        const repeatHtml = log.count > 1 ? `<span class="log-repeat">x${log.count}</span>` : '';
        
        entry.innerHTML = `
            <span class="log-timestamp">${log.lastTimestamp || log.timestamp || ''}</span>
            <span class="log-message">${escapeHtml(log.message)}</span>
            ${repeatHtml}
        `;
        
        container.appendChild(entry);
    });
    
    // Scroll to bottom
    container.scrollTop = container.scrollHeight;
}

function addLog(type, message) {
    const timestamp = new Date().toLocaleTimeString('vi-VN');
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    entry.innerHTML = `
        <span class="log-timestamp">${timestamp}</span>
        <span class="log-message">${escapeHtml(message)}</span>
    `;
    
    const container = document.getElementById('logsContainer');
    if (container.querySelector('.log-empty')) {
        container.innerHTML = '';
    }
    container.appendChild(entry);
    container.scrollTop = container.scrollHeight;
}

function clearLogs() {
    document.getElementById('logsContainer').innerHTML = '<div class="log-empty">Chưa có logs...</div>';
}

function updateButtons() {
    document.getElementById('startBtn').disabled = isRunning;
}

function sanitizeLogMessage(message) {
    let s = String(message || '').replace(/\s+/g, ' ').trim();
    if (s.length > 260) s = s.slice(0, 257) + '...';
    return s;
}

function isNoisyLogMessage(message) {
    const m = String(message || '').toLowerCase();
    // Nhiễu hệ thống/browser, ít giá trị khi theo dõi luồng upload
    if (m.includes('deprecated_endpoint') || m.includes('gcm\\engine\\registration_request')) return true;
    if (m.includes('devtools://devtools') || m.includes('storage.getstoragekeyforframe')) return true;
    if (m.includes('tensorflow lite') || m.includes('xnnpack delegate')) return true;
    if (m.includes('gpu state invalid') || m.includes('usb_service_win')) return true;
    return false;
}

function downloadExcel() {
    window.location.href = '/api/download-excel';
}

function downloadUploadLog() {
    window.location.href = '/api/download-upload-log';
}

async function continueLogin() {
    try {
        const response = await fetch('/api/continue-login', {
            method: 'POST'
        });
        
        const data = await response.json();
        if (response.ok) {
            addLog('success', '✅ Đã tiếp tục sau khi đăng nhập');
            const continueLoginBtn = document.getElementById('continueLoginBtn');
            continueLoginBtn.classList.add('hidden');
            continueLoginBtn.classList.remove('visible');
        } else {
            addLog('error', `❌ Lỗi: ${data.error}`);
        }
    } catch (error) {
        addLog('error', `❌ Lỗi: ${error.message}`);
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

