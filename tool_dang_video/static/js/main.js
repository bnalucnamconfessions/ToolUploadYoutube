let statusInterval = null;
let isRunning = false;
let selectedFolderPath = null;

// Bộ nhớ tạm cho Made for kids — tránh nhầm khi gửi request (ưu tiên giá trị user vừa chọn)
const MADE_FOR_KIDS_STORAGE_KEY = 'made_for_kids_choice';

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
    
    // Stop button
    document.getElementById('stopBtn').addEventListener('click', stopUpload);
    
    // Download button
    document.getElementById('downloadBtn').addEventListener('click', downloadExcel);
    
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
        video_title: (document.getElementById('video_title') && document.getElementById('video_title').value) ? document.getElementById('video_title').value.trim() : '',
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

async function stopUpload() {
    if (!confirm('Bạn có chắc muốn dừng upload?')) {
        return;
    }
    
    try {
        const response = await fetch('/api/stop-upload', {
            method: 'POST'
        });
        
        const data = await response.json();
        addLog('warning', '⏹ Đã yêu cầu dừng upload...');
        
        // Đợi một chút để server xử lý
        setTimeout(() => {
            isRunning = false;
            updateButtons();
        }, 1000);
    } catch (error) {
        addLog('error', `❌ Lỗi: ${error.message}`);
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
    const statusText = status.is_running ? 'Đang chạy...' : (status.should_stop ? 'Đã dừng' : 'Chưa bắt đầu');
    document.getElementById('statusText').textContent = statusText;
    document.getElementById('statusText').className = status.is_running ? 'status-value running' : 'status-value';
    
    // Update total files
    document.getElementById('totalFiles').textContent = status.total_files || 0;
    
    // Update current file
    document.getElementById('currentFile').textContent = status.current_file || '-';
    
    // Update counts
    document.getElementById('successCount').textContent = status.success_count || 0;
    document.getElementById('failCount').textContent = status.fail_count || 0;
    
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
    
    // Clear and add new logs
    container.innerHTML = '';
    logs.slice(-100).forEach(log => {
        const entry = document.createElement('div');
        entry.className = 'log-entry';
        
        // Determine log type
        if (log.message.includes('✅') || log.message.includes('thành công')) {
            entry.classList.add('success');
        } else if (log.message.includes('❌') || log.message.includes('Lỗi')) {
            entry.classList.add('error');
        } else if (log.message.includes('⚠') || log.message.includes('Cảnh báo')) {
            entry.classList.add('warning');
        }
        
        entry.innerHTML = `
            <span class="log-timestamp">${log.timestamp || ''}</span>
            <span class="log-message">${escapeHtml(log.message)}</span>
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
    document.getElementById('stopBtn').disabled = !isRunning;
}

function downloadExcel() {
    window.location.href = '/api/download-excel';
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

