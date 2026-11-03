"""Account-scoped Muse bridge. Browser session bytes travel only through private IPC."""
import atexit
import hashlib
import json
import os
import shutil
import subprocess
import threading
import time
import math
from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException
from account_store import FileLock, public_account, vault

WORKER = Path(__file__).with_name('muse_worker.mjs')
_ACTIVE = set()
_ACTIVE_LOCK = threading.Lock()


def stop_process(process):
    try: process.stdin.close()
    except (OSError, ValueError): pass
    try: process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.terminate()
        try: process.wait(timeout=3)
        except subprocess.TimeoutExpired: process.kill(); process.wait()


def stop_workers():
    with _ACTIVE_LOCK: children = list(_ACTIVE)
    for process in children: stop_process(process)


atexit.register(stop_workers)


def account_lock(account_id):
    return FileLock(vault.directory / 'locks' / (hashlib.sha256(account_id.encode()).hexdigest() + '.lock'), timeout=1)


def verify_worker_account(account, action, session, attempt_id):
    if action == 'login':
        valid = account.get('status') == 'pending' and account.get('pendingAttempt') == attempt_id
    else:
        valid = account.get('status') == 'connected' and account.get('session') == session
    if not valid: raise HTTPException(409, 'Muse 登录状态已改变，请重新操作')


def worker_events(account_id, action, session=None, messages=None, attempt_id=None):
    node = shutil.which('node')
    if not node: raise HTTPException(503, 'Muse 登录需要 Node.js 24 和项目浏览器依赖')
    with account_lock(account_id):
        verify_worker_account(vault.account(account_id), action, session, attempt_id)
        options = {'stdin': subprocess.PIPE, 'stdout': subprocess.PIPE, 'stderr': subprocess.DEVNULL,
                   'text': True, 'encoding': 'utf-8', 'cwd': str(WORKER.parent.parent)}
        if os.name == 'nt': options['creationflags'] = subprocess.CREATE_NO_WINDOW
        process = subprocess.Popen([node, str(WORKER)], **options)
        with _ACTIVE_LOCK: _ACTIVE.add(process)
        watchdog = threading.Timer(660 if action == 'login' else 240, lambda: stop_process(process) if process.poll() is None else None)
        watchdog.daemon = True; watchdog.start()
        complete = False
        pending_session = None
        pending_usage = None
        try:
            process.stdin.write(json.dumps({'action': action, 'session': session, 'messages': messages}, ensure_ascii=False) + '\n')
            process.stdin.flush()
            for line in process.stdout:
                if len(line) > 5000000: raise HTTPException(502, 'Muse 浏览器响应过大')
                try: event = json.loads(line)
                except ValueError: raise HTTPException(502, 'Muse 浏览器返回无效响应')
                if event.get('type') == 'error': raise HTTPException(409, event.get('message') or 'Muse 操作失败')
                if event.get('type') == 'session':
                    state = event.get('session')
                    if not isinstance(state, dict) or not isinstance(state.get('cookies'), list): raise HTTPException(502, 'Muse 会话无效')
                    if any(c.get('domain') != 'muse.ai' and not c.get('domain', '').endswith('.muse.ai') for c in state['cookies']):
                        raise HTTPException(502, 'Muse 会话包含非本站数据，已拒绝保存')
                    pending_session = state
                elif event.get('type') == 'delta':
                    if not isinstance(event.get('text'), str): raise HTTPException(502, 'Muse 文本响应无效')
                    yield event['text']
                elif event.get('type') == 'usage' and action == 'usage':
                    pending_usage = sanitize_usage(event.get('usage'))
                elif event.get('type') == 'complete': complete = True
            process.wait(timeout=5)
            if not complete or process.returncode != 0: raise HTTPException(409, 'Muse 操作未完整结束，请重新登录或重试')
            if pending_session is None: raise HTTPException(502, 'Muse 未返回已验证会话')
            if action == 'usage' and pending_usage is None: raise HTTPException(502, 'Muse 未返回有效用量')
            with vault.transaction() as data:
                account = data['accounts'].get(account_id)
                if not account: raise HTTPException(409, 'Muse 账号已被移除')
                verify_worker_account(account, action, session, attempt_id)
                account.update(session=pending_session, verifiedAt=time.time(), status='connected', canGenerate=True, message='')
                if action == 'login':
                    for field in ('usage', 'pendingAttempt', 'pendingUntil'): account.pop(field, None)
                if pending_usage is not None: account['usage'] = pending_usage
        finally:
            watchdog.cancel()
            if process.poll() is None: stop_process(process)
            else:
                try: process.stdin.close()
                except (OSError, ValueError): pass
            with _ACTIVE_LOCK: _ACTIVE.discard(process)
            process.stdout.close()


def start_muse_login(account_id=None, label='Muse 账号'):
    identifier, attempt_id = account_id or str(uuid4()), str(uuid4())
    with account_lock(identifier):
        with vault.transaction() as data:
            account = data['accounts'].get(account_id) if account_id else None
            if account_id and (not account or account['provider'] != 'muse'): raise HTTPException(404, 'Muse 账号不存在')
            if account and account.get('status') == 'pending' and account.get('pendingUntil', 0) > time.time(): raise HTTPException(409, '该账号的登录窗口已打开')
            # Keep an existing encrypted session until a successful new login replaces it.
            data['accounts'][identifier] = {**(account or {}), 'id': identifier, 'provider': 'muse',
                'label': (account or {}).get('label') or (label if label != 'Muse 账号' else f'Muse 账号 · {identifier[:6]}'),
                'status': 'pending', 'pendingAttempt': attempt_id, 'pendingUntil': time.time() + 660, 'canGenerate': False}
    def login():
        try:
            for _ in worker_events(identifier, 'login', attempt_id=attempt_id): pass
        except Exception as exc:
            message = str(exc.detail) if isinstance(exc, HTTPException) else 'Muse 登录未完成，请检查浏览器依赖和网络'
            with vault.transaction() as data:
                record = data['accounts'].get(identifier)
                if record and record['status'] == 'pending' and record.get('pendingAttempt') == attempt_id:
                    record.update(status='failed', canGenerate=False, message=message)
    threading.Thread(target=login, name='muse-account-login', daemon=True).start()
    return {'accountId': identifier, 'message': '请在独立打开的浏览器窗口中完成 Muse 登录'}


def muse_text(account_id, messages):
    account = vault.account(account_id)
    if account['provider'] != 'muse' or account.get('status') != 'connected' or not account.get('session'):
        raise HTTPException(409, 'Muse 账号未连接，请先登录')
    yield from worker_events(account_id, 'generate', session=account['session'], messages=messages)


def check_muse(account_id):
    account = vault.account(account_id)
    if account['provider'] != 'muse' or account.get('status') != 'connected' or not account.get('session'): raise HTTPException(409, '请先登录 Muse')
    for _ in worker_events(account_id, 'check', session=account['session']): pass
    return public_account(vault.account(account_id))


def sanitize_usage(value):
    """Only documented display fields cross the credential boundary."""
    if not isinstance(value, dict) or value.get('source') != 'muse-settings' or not isinstance(value.get('rows'), list):
        raise HTTPException(502, 'Muse 用量格式无效')
    rows = []
    for row in value['rows'][:6]:
        if not isinstance(row, dict): continue
        percent = row.get('usedPercent')
        if type(percent) not in (float, int) or not 0 <= percent <= 100 or not math.isfinite(percent): continue
        if not all(isinstance(row.get(key), str) for key in ('label', 'description', 'valueLabel')): continue
        if not row['label'].strip() or not row['valueLabel'].strip(): continue
        rows.append({'kind': row.get('kind') if row.get('kind') in ('weekly', 'additional') else 'other',
                     'label': row['label'].strip()[:100], 'description': row['description'].strip()[:240],
                     'valueLabel': row['valueLabel'].strip()[:240], 'usedPercent': percent})
    if not rows: raise HTTPException(502, 'Muse 未返回可读取用量，不会将未知额度显示为零')
    return {'source': 'muse-settings', 'checkedAt': time.time(), 'rows': rows}


def refresh_muse_usage(account_id):
    account = vault.account(account_id)
    if account['provider'] != 'muse' or account.get('status') != 'connected' or not account.get('session'):
        raise HTTPException(409, '请先登录 Muse 再读取额度')
    for _ in worker_events(account_id, 'usage', session=account['session']): pass
    return {'usage': vault.account(account_id).get('usage')}


def disconnect_muse(account_id):
    with account_lock(account_id):
        with vault.transaction() as data:
            account = data['accounts'].get(account_id)
            if not account: raise HTTPException(404, '账号不存在')
            account.pop('session', None)
            account.pop('usage', None)
            account.pop('pendingAttempt', None)
            account.pop('pendingUntil', None)
            account.update(status='disconnected', canGenerate=False)
    return {'message': 'Muse 本地会话已清除；不会注销你其他浏览器中的账号'}
