"""Encrypted, atomic per-installation account storage; contains no browser secrets."""
import contextlib
import ctypes
import json
import os
import tempfile
import threading
import time
from pathlib import Path
from uuid import uuid4

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
from settings import DATA_DIR

_LOCKS = {}
_LOCKS_GUARD = threading.Lock()


class FileLock:
    def __init__(self, path, timeout=20):
        self.path, self.timeout = Path(path), timeout
        with _LOCKS_GUARD:
            self.thread_lock = _LOCKS.setdefault(str(self.path.resolve()), threading.RLock())

    def __enter__(self):
        if not self.thread_lock.acquire(timeout=self.timeout):
            raise HTTPException(409, '账号正在使用，请稍后重试')
        self.file = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.file = open(self.path, 'a+b')
            self.file.seek(0, 2)
            if not self.file.tell():
                self.file.write(b'0'); self.file.flush()
            deadline = time.monotonic() + self.timeout
            while True:
                try:
                    self.file.seek(0)
                    if os.name == 'nt':
                        import msvcrt
                        msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    return self
                except OSError:
                    if time.monotonic() >= deadline:
                        raise HTTPException(409, '账号正在使用，请稍后重试')
                    time.sleep(.05)
        except BaseException:
            if self.file: self.file.close()
            self.thread_lock.release()
            raise

    def __exit__(self, *args):
        try:
            self.file.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
        finally:
            self.file.close()
            self.thread_lock.release()


def _dpapi(data, encrypt):
    from ctypes import wintypes
    class Blob(ctypes.Structure):
        _fields_ = [('length', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_byte))]
    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
    output = Blob()
    function = ctypes.windll.crypt32.CryptProtectData if encrypt else ctypes.windll.crypt32.CryptUnprotectData
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output)):
        raise OSError('Cannot protect account key with Windows DPAPI')
    try:
        return ctypes.string_at(output.data, output.length)
    finally:
        ctypes.windll.kernel32.LocalFree(output.data)


def atomic_write(path, data):
    path = Path(path)
    fd, temp = tempfile.mkstemp(prefix='.account-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as file:
            if os.name != 'nt': os.fchmod(file.fileno(), 0o600)
            file.write(data); file.flush(); os.fsync(file.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp): os.unlink(temp)


class AccountVault:
    def __init__(self, directory=None):
        self.directory = Path(directory or DATA_DIR / 'credentials')

    def _cipher(self):
        key_path = self.directory / '.key'
        if key_path.exists():
            value = key_path.read_bytes()
            if value.startswith(b'DPAPI:') and os.name == 'nt': key = _dpapi(value[6:], False)
            elif value.startswith(b'LOCAL:') and os.name != 'nt': key = value[6:]
            else: raise HTTPException(503, '账号凭据属于其他系统用户，无法解密，请重新连接账号')
        else:
            if (self.directory / 'accounts.enc').exists():
                raise HTTPException(503, '账号加密密钥缺失，请恢复凭据目录备份')
            key = Fernet.generate_key()
            atomic_write(key_path, b'DPAPI:' + _dpapi(key, True) if os.name == 'nt' else b'LOCAL:' + key)
        return Fernet(key)

    @contextlib.contextmanager
    def transaction(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        if os.name != 'nt': self.directory.chmod(0o700)
        with FileLock(self.directory / '.lock'):
            cipher = self._cipher()
            path = self.directory / 'accounts.enc'
            try:
                data = json.loads(cipher.decrypt(path.read_bytes())) if path.exists() else {
                    'version': 1, 'host_id': 'urn:uuid:' + str(uuid4()), 'accounts': {}, 'attempts': {}}
            except (InvalidToken, ValueError):
                raise HTTPException(503, '账号凭据无法解密，请恢复备份，不会覆盖原文件')
            before = json.dumps(data, ensure_ascii=False, sort_keys=True)
            yield data
            encoded = json.dumps(data, ensure_ascii=False, sort_keys=True)
            if encoded != before or not path.exists():
                atomic_write(path, cipher.encrypt(encoded.encode('utf-8')))

    def accounts(self):
        with self.transaction() as data:
            return [public_account(account) for account in data['accounts'].values()]

    def account(self, account_id):
        with self.transaction() as data:
            account = data['accounts'].get(account_id)
            if not account: raise HTTPException(404, '账号不存在或已断开，请重新登录')
            return dict(account)


def public_account(account):
    result = {key: account.get(key) for key in (
        'id', 'provider', 'label', 'status', 'email', 'expiresAt', 'verifiedAt', 'canGenerate', 'message')}
    if account.get('status') == 'pending' and account.get('pendingUntil', float('inf')) <= time.time():
        result.update(status='failed', canGenerate=False, message='登录等待已过期，请重新登录')
    if result.get('provider') == 'muse' and result.get('status') == 'connected': result['usage'] = account.get('usage')
    return result


vault = AccountVault()
