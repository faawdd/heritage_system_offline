from __future__ import annotations

import base64
import getpass
import hashlib
import json
import os
from pathlib import Path
import platform
import secrets
import uuid

from .paths import get_config_dir


SERVICE_NAME = 'heritage_system.sqlcipher'
KEYRING_ACCOUNT = 'database-key'
KEY_FILE_NAME = 'key.bin'


class SqlCipherKeyError(RuntimeError):
    pass


def generate_database_key() -> str:
    return secrets.token_hex(32)


def _key_file_path(config_dir: Path | None = None) -> Path:
    base_dir = Path(config_dir) if config_dir is not None else get_config_dir()
    return base_dir / KEY_FILE_NAME


def _windows_dpapi_available() -> bool:
    return platform.system().lower() == 'windows'


def _load_keyring_password() -> str | None:
    try:
        import keyring
    except Exception:
        return None

    try:
        password = keyring.get_password(SERVICE_NAME, KEYRING_ACCOUNT)
    except Exception:
        return None
    return password or None


def _store_keyring_password(key_text: str) -> bool:
    try:
        import keyring
    except Exception:
        return False

    try:
        keyring.set_password(SERVICE_NAME, KEYRING_ACCOUNT, key_text)
        return True
    except Exception:
        return False


def _machine_fingerprint() -> bytes:
    material = '|'.join([
        platform.system(),
        platform.node(),
        getpass.getuser(),
        str(Path.home()),
        str(uuid.getnode()),
        SERVICE_NAME,
    ])
    return hashlib.sha256(material.encode('utf-8')).digest()


def _fallback_encrypt(key_text: str) -> bytes:
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except Exception as exc:
        raise SqlCipherKeyError('cryptography is required for encrypted key file fallback') from exc

    aesgcm = AESGCM(_machine_fingerprint())
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, key_text.encode('utf-8'), SERVICE_NAME.encode('utf-8'))
    payload = {
        'version': 1,
        'nonce': base64.b64encode(nonce).decode('ascii'),
        'ciphertext': base64.b64encode(ciphertext).decode('ascii'),
    }
    return json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def _fallback_decrypt(payload_bytes: bytes) -> str:
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except Exception as exc:
        raise SqlCipherKeyError('cryptography is required for encrypted key file fallback') from exc

    try:
        payload = json.loads(payload_bytes.decode('utf-8'))
        nonce = base64.b64decode(payload['nonce'])
        ciphertext = base64.b64decode(payload['ciphertext'])
    except Exception as exc:
        raise SqlCipherKeyError('Invalid SQLCipher key file') from exc

    aesgcm = AESGCM(_machine_fingerprint())
    try:
        key_text = aesgcm.decrypt(nonce, ciphertext, SERVICE_NAME.encode('utf-8')).decode('utf-8')
    except Exception as exc:
        raise SqlCipherKeyError('Unable to decrypt SQLCipher key file') from exc
    return key_text


def _load_windows_key_file(key_file: Path) -> str:
    try:
        import ctypes
        from ctypes import wintypes
    except Exception as exc:
        raise SqlCipherKeyError('Windows DPAPI is not available') from exc

    data = key_file.read_bytes()

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_byte))]

    blob_in = DATA_BLOB(len(data), ctypes.cast(ctypes.create_string_buffer(data, len(data)), ctypes.POINTER(ctypes.c_byte)))
    blob_out = DATA_BLOB()

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    if not crypt32.CryptUnprotectData(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
        raise SqlCipherKeyError('Unable to decrypt SQLCipher key file')

    try:
        key_bytes = ctypes.string_at(blob_out.pbData, blob_out.cbData)
        return key_bytes.decode('utf-8')
    finally:
        kernel32.LocalFree(blob_out.pbData)


def _store_windows_key_file(key_file: Path, key_text: str) -> None:
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_byte))]

    data = key_text.encode('utf-8')
    blob_in = DATA_BLOB(len(data), ctypes.cast(ctypes.create_string_buffer(data, len(data)), ctypes.POINTER(ctypes.c_byte)))
    blob_out = DATA_BLOB()

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    if not crypt32.CryptProtectData(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
        raise SqlCipherKeyError('Unable to encrypt SQLCipher key file with DPAPI')

    try:
        encrypted_bytes = ctypes.string_at(blob_out.pbData, blob_out.cbData)
        key_file.write_bytes(encrypted_bytes)
    finally:
        kernel32.LocalFree(blob_out.pbData)


def load_database_key(config_dir: Path | None = None, create_if_missing: bool = False) -> str:
    key_file = _key_file_path(config_dir)

    if _windows_dpapi_available():
        if key_file.exists():
            return _load_windows_key_file(key_file)
        if create_if_missing:
            key_text = generate_database_key()
            key_file.parent.mkdir(parents=True, exist_ok=True)
            _store_windows_key_file(key_file, key_text)
            return key_text
        raise SqlCipherKeyError('SQLCipher key file not found')

    if key_file.exists():
        return _fallback_decrypt(key_file.read_bytes())

    keyring_password = _load_keyring_password()
    if keyring_password:
        return keyring_password

    if create_if_missing:
        key_text = generate_database_key()
        store_database_key(key_text, config_dir=config_dir)
        return key_text

    raise SqlCipherKeyError('SQLCipher key not found')


def store_database_key(key_text: str, config_dir: Path | None = None) -> Path:
    key_file = _key_file_path(config_dir)
    key_file.parent.mkdir(parents=True, exist_ok=True)

    if _windows_dpapi_available():
        _store_windows_key_file(key_file, key_text)
        return key_file

    if _store_keyring_password(key_text):
        if key_file.exists():
            key_file.unlink()
        return key_file

    key_file.write_bytes(_fallback_encrypt(key_text))
    return key_file


def has_database_key(config_dir: Path | None = None) -> bool:
    key_file = _key_file_path(config_dir)
    if key_file.exists():
        return True
    if _windows_dpapi_available():
        return False
    return _load_keyring_password() is not None
