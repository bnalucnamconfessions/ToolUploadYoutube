# -*- coding: utf-8 -*-
"""Mã hóa mật khẩu lưu trong profiles.json (Fernet + PBKDF2, salt riêng trên máy)."""
import base64
import os

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
except ImportError:
    Fernet = None  # type: ignore


_PREFIX = "enc:v1:"


def _fernet():
    if Fernet is None:
        return None
    salt_dir = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    d = os.path.join(salt_dir, "YouTubeUploadTool")
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        d = os.getcwd()
    salt_path = os.path.join(d, ".ytb_pwd_salt")
    if not os.path.isfile(salt_path):
        try:
            with open(salt_path, "wb") as f:
                f.write(os.urandom(16))
        except OSError:
            return None
    try:
        with open(salt_path, "rb") as f:
            salt = f.read()
    except OSError:
        return None
    pwd = (os.path.abspath(os.getcwd()) + "|ToolUploadYoutube|v1").encode("utf-8", errors="replace")
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=120_000)
    key = base64.urlsafe_b64encode(kdf.derive(pwd))
    return Fernet(key)


def encrypt_password(plain: str) -> str:
    if not plain:
        return ""
    f = _fernet()
    if f is None:
        return plain
    try:
        return _PREFIX + f.encrypt(plain.encode("utf-8")).decode("ascii")
    except Exception:
        return plain


def decrypt_password(stored: str) -> str:
    if not stored:
        return ""
    if not stored.startswith(_PREFIX):
        return stored
    f = _fernet()
    if f is None:
        return ""
    try:
        token = stored[len(_PREFIX) :].encode("ascii")
        return f.decrypt(token).decode("utf-8")
    except Exception:
        return ""
