# -*- mode: python ; coding: utf-8 -*-
# Build: pyinstaller YouTubeUploadTool.spec
# Hoặc: python build_exe.py

import os

block_cipher = None

# Thư mục gốc của project (nơi có app.py, templates, static)
# Chạy build từ trong thư mục tool_dang_video: pyinstaller YouTubeUploadTool.spec
project_dir = os.path.dirname(os.path.abspath(SPEC)) if 'SPEC' in dir() else os.getcwd()

a = Analysis(
    [os.path.join(project_dir, 'app.py')],
    pathex=[project_dir],
    binaries=[],
    datas=[
        (os.path.join(project_dir, 'templates'), 'templates'),
        (os.path.join(project_dir, 'static'), 'static'),
    ],
    hiddenimports=[
        'flask',
        'flask_cors',
        'werkzeug',
        'jinja2',
        'selenium',
        'selenium.webdriver',
        'selenium.webdriver.chrome',
        'selenium.webdriver.chrome.service',
        'selenium.webdriver.chrome.options',
        'selenium.webdriver.chrome.webdriver',
        'selenium.webdriver.common.by',
        'selenium.webdriver.common.keys',
        'selenium.webdriver.support.ui',
        'selenium.webdriver.support.expected_conditions',
        'selenium.common.exceptions',
        'openpyxl',
        'openpyxl.styles',
        'openpyxl.utils',
        'tooldangvideo',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='YouTubeUploadTool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Hiện cửa sổ console; bản sao log nằm trong debug_logs/ cạnh exe (xem app.py)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Có thể thêm icon: icon='icon.ico'
)
