"""Official Sign in with ChatGPT OSS flow; no borrowed client IDs or web endpoints."""
import base64
import hashlib
import hmac
import math
from datetime import datetime
import secrets
import time
from functools import lru_cache
from urllib.parse import urlencode, urlsplit
from uuid import uuid4

import httpx
from fastapi import HTTPException
from account_store import public_account, vault
from security import first_party_target

ISSUER = 'https://auth.openai.com'
AUTHORIZE = ISSUER + '/api/accounts/authorize'
TOKEN = ISSUER + '/api/accounts/oauth/token'
RESOURCE = 'https://api.openai.com/v1'
SCOPES = 'openid profile email offline_access resource.invoke chatgpt.tokens.use.direct'
APP_NAME = 'AI Creation Studio'


def request_first_party(method, url, **kwargs):
    target, host, sni = first_party_target(url, {'auth.openai.com', 'api.openai.com'})
    headers = {'Host': host, **kwargs.pop('headers', {})}
    try:
        with httpx.Client(timeout=20, follow_redirects=False, trust_env=False) as client:
            return client.request(method, target, headers=headers, extensions={'sni_hostname': sni}, **kwargs)
    except httpx.HTTPError:
        raise HTTPException(502, '无法连接官方授权服务，请稍后重试')


def checked_json(response):
    if not response.is_success:
        raise HTTPException(409 if response.status_code in (400, 401, 403) else 502,
                            '授权服务拒绝了请求，请重新授权或检查账号权限')
    try:
        data = response.json()
        if not isinstance(data, dict): raise ValueError()
        return data
    except ValueError:
        raise HTTPException(502, '授权服务返回了无效响应')


@lru_cache(maxsize=1)
def metadata():
    data = checked_json(request_first_party('GET', ISSUER + '/.well-known/openid-configuration'))
    if (data.get('issuer') != ISSUER or data.get('authorization_endpoint') != AUTHORIZE
            or data.get('token_endpoint') != TOKEN):
        raise HTTPException(502, '授权服务元数据不匹配')
    for key in ('jwks_uri', 'revocation_endpoint'):
        parsed = urlsplit(data.get(key, ''))
        if (parsed.scheme != 'https' or parsed.hostname != 'auth.openai.com'
                or parsed.port not in (None, 443) or parsed.username or parsed.query or parsed.fragment):
            raise HTTPException(502, '授权服务元数据地址不可信')
    return data


def verify_identity(encoded, client_id, nonce=None, access_token=None):
    try:
        import jwt
    except ImportError:
        raise HTTPException(503, '请先更新后端依赖，以启用 OAuth 签名验证')
    try:
        header = jwt.get_unverified_header(encoded)
        algorithm = header.get('alg')
        if algorithm not in ('RS256', 'ES256') or not isinstance(header.get('kid'), str): raise ValueError()
        keys = checked_json(request_first_party('GET', metadata()['jwks_uri'])).get('keys', [])
        key = next(k for k in keys if k.get('kid') == header['kid'] and k.get('use', 'sig') == 'sig')
        identity = jwt.decode(encoded, jwt.PyJWK.from_dict(key).key, algorithms=[algorithm],
                              audience=client_id, issuer=ISSUER, leeway=5,
                              options={'require': ['sub', 'exp', 'iat', 'iss', 'aud']})
        if not isinstance(identity.get('sub'), str) or not identity['sub']: raise ValueError()
        if nonce is not None and not hmac.compare_digest(str(identity.get('nonce', '')), nonce): raise ValueError()
        if identity.get('azp', client_id) != client_id: raise ValueError()
        if isinstance(identity['aud'], list) and len(identity['aud']) > 1 and identity.get('azp') != client_id: raise ValueError()
        if identity.get('at_hash'):
            if not access_token: raise ValueError()
            digest = hashlib.sha256(access_token.encode()).digest()[:16]
            expected = base64.urlsafe_b64encode(digest).decode().rstrip('=')
            if not hmac.compare_digest(expected, identity['at_hash']): raise ValueError()
        return identity
    except (jwt.PyJWTError, ValueError, TypeError, KeyError, StopIteration):
        raise HTTPException(409, 'OAuth 身份签名、账号、回调 nonce 或有效期校验失败，请重新登录')


def token_fields(data, previous=None):
    previous = previous or {}
    access = data.get('access_token')
    refresh = data.get('refresh_token')
    if (not isinstance(access, str) or not access or not isinstance(refresh, str) or not refresh
            or data.get('token_type', '').lower() != 'bearer'):
        raise HTTPException(502, '授权响应缺少有效令牌，原凭据未被替换')
    try:
        lifetime = int(data['expires_in'])
        if not 0 < lifetime <= 86400: raise ValueError()
        raw_earliest = data.get('earliest_refresh_at') or 0
        try: earliest = float(raw_earliest)
        except ValueError: earliest = datetime.fromisoformat(str(raw_earliest).replace('Z', '+00:00')).timestamp()
        if not math.isfinite(earliest): raise ValueError()
    except (ValueError, TypeError, KeyError):
        raise HTTPException(502, '授权令牌有效期无效')
    granted = data.get('scope', ' '.join(previous.get('scopes', [])))
    if not isinstance(granted, str): raise HTTPException(502, '授权范围无效')
    scopes = granted.split()
    return {'access_token': access, 'refresh_token': refresh,
            'id_token': data.get('id_token') or previous.get('id_token'), 'scopes': scopes,
            'expiresAt': time.time() + lifetime, 'earliestRefreshAt': earliest,
            'canGenerate': {'resource.invoke', 'chatgpt.tokens.use.direct'}.issubset(scopes)}


def begin_chatgpt(redirect_uri, account_id=None):
    state, nonce, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(32), secrets.token_urlsafe(64)
    with vault.transaction() as data:
        for key in list(data['attempts']):
            if data['attempts'][key]['expiresAt'] < time.time(): del data['attempts'][key]
        if len(data['attempts']) >= 8: raise HTTPException(429, '授权窗口过多，请稍后重试')
        account = data['accounts'].get(account_id) if account_id else None
        if account_id and (not account or account['provider'] != 'chatgpt'):
            raise HTTPException(404, 'ChatGPT 账号不存在')
        client_id = account['client_id'] if account else 'dynamic_agent_client'
        data['attempts'][state] = {'status': 'pending', 'expiresAt': time.time() + 600,
            'nonce': nonce, 'verifier': verifier, 'redirectUri': redirect_uri,
            'clientId': client_id, 'accountId': account_id}
        params = {'client_id': client_id, 'response_type': 'code', 'redirect_uri': redirect_uri,
            'scope': SCOPES, 'resource': RESOURCE, 'state': state, 'nonce': nonce,
            'ext_agent_host_id': data['host_id'], 'code_challenge_method': 'S256',
            'code_challenge': base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')}
        if account:
            # Keep ID tokens behind the backend boundary; an email hint is optional.
            if account.get('email'): params['login_hint'] = account['email']
        else: params['agent_name_hint'] = APP_NAME
    return {'attemptId': state, 'authorizationUrl': AUTHORIZE + '?' + urlencode(params), 'expiresIn': 600}


def attempt_status(state):
    with vault.transaction() as data:
        attempt = data['attempts'].get(state)
        if not attempt or attempt['expiresAt'] < time.time(): return {'status': 'expired'}
        result = {'status': attempt['status'], 'message': attempt.get('message', '')}
        if attempt.get('resultAccountId'):
            account = data['accounts'].get(attempt['resultAccountId'])
            if account: result['account'] = public_account(account)
        return result


def finish_chatgpt(state, code=None, client_id=None, error=None):
    with vault.transaction() as data:
        attempt = data['attempts'].get(state)
        if not attempt or attempt['expiresAt'] < time.time() or attempt['status'] != 'pending':
            raise HTTPException(400, '授权回调已过期、已使用或 state 无效')
        attempt['status'] = 'exchanging'
        pending = dict(attempt)
    try:
        if error: raise HTTPException(409, '授权已取消或被平台拒绝')
        selected = pending['clientId']
        if selected == 'dynamic_agent_client':
            if not client_id or client_id == selected or len(client_id) > 256 or any(c.isspace() for c in client_id):
                raise HTTPException(400, '回调缺少平台颁发的客户端 ID')
            selected = client_id
        elif client_id and client_id != selected:
            raise HTTPException(400, '回调客户端 ID 与选中账号不匹配')
        if not code or len(code) > 8192: raise HTTPException(400, '回调授权码无效')
        tokens = checked_json(request_first_party('POST', TOKEN, data={
            'grant_type': 'authorization_code', 'client_id': selected, 'code': code,
            'code_verifier': pending['verifier'], 'redirect_uri': pending['redirectUri'], 'resource': RESOURCE}))
        fields = token_fields(tokens)
        identity = verify_identity(tokens.get('id_token', ''), selected, pending['nonce'], fields['access_token'])
        with vault.transaction() as data:
            if data['attempts'].get(state, {}).get('status') != 'exchanging':
                raise HTTPException(409, '授权等待已取消，请重新登录')
            previous = data['accounts'].get(pending['accountId']) if pending.get('accountId') else None
            if previous and (previous['subject'] != identity['sub'] or previous['client_id'] != selected):
                raise HTTPException(409, '登录账号与选中账号不同，原账号未被覆盖')
            identifier = previous['id'] if previous else str(uuid4())
            account = {**(previous or {}), **fields, 'id': identifier, 'provider': 'chatgpt',
                'label': identity.get('email') or identity.get('name') or 'ChatGPT 账号',
                'email': identity.get('email'), 'subject': identity['sub'], 'client_id': selected,
                'status': 'connected', 'verifiedAt': time.time()}
            data['accounts'][identifier] = account
            data['attempts'][state] = {'status': 'connected', 'expiresAt': time.time() + 600, 'resultAccountId': identifier}
        return public_account(account)
    except HTTPException as exc:
        with vault.transaction() as data:
            data['attempts'][state] = {'status': 'failed', 'message': exc.detail, 'expiresAt': time.time() + 600}
        raise
    except Exception:
        with vault.transaction() as data:
            data['attempts'][state] = {'status': 'failed', 'message': '授权未完成，请重新尝试', 'expiresAt': time.time() + 600}
        raise HTTPException(502, '授权未完成，请重新尝试')


def access_credentials(account_id, force=False):
    # The cross-process vault lock serializes refresh-token rotation and atomic writes.
    with vault.transaction() as data:
        account = data['accounts'].get(account_id)
        if not account or account.get('status') != 'connected' or account.get('provider') != 'chatgpt':
            raise HTTPException(409, 'ChatGPT 账号未连接，请重新授权')
        if not account.get('canGenerate'): raise HTTPException(403, '该账号未授权 ChatGPT 模型使用权限，请重新授权')
        if force or account['expiresAt'] <= time.time() + 60:
            if time.time() < account.get('earliestRefreshAt', 0):
                if force or account['expiresAt'] <= time.time(): raise HTTPException(409, '令牌已过期且尚不可刷新，请重新授权')
            else:
                tokens = checked_json(request_first_party('POST', TOKEN, data={
                    'grant_type': 'refresh_token', 'client_id': account['client_id'],
                    'refresh_token': account['refresh_token'], 'resource': RESOURCE}))
                fields = token_fields(tokens, account)
                if tokens.get('id_token'):
                    identity = verify_identity(tokens['id_token'], account['client_id'], access_token=fields['access_token'])
                    if identity['sub'] != account['subject']: raise HTTPException(409, '刷新返回了不同身份，已拒绝替换')
                account.update(fields)
        result = dict(account)
    if not result.get('canGenerate'): raise HTTPException(403, '该账号不再具备模型使用权限，请重新授权')
    return result


def list_models(account_id):
    account = access_credentials(account_id)
    data = checked_json(request_first_party('GET', RESOURCE + '/models', headers={'Authorization': 'Bearer ' + account['access_token']}))
    return [{'id': row['slug'], 'name': row.get('display_name') or row['slug']}
            for row in data.get('models', []) if row.get('visibility') == 'list' and isinstance(row.get('slug'), str)]


def disconnect_chatgpt(account_id):
    with vault.transaction() as data:
        account = data['accounts'].get(account_id)
        if not account: raise HTTPException(404, '账号不存在')
        confirmed = False
        try:
            if account.get('refresh_token'):
                confirmed = request_first_party('POST', metadata()['revocation_endpoint'], data={
                    'token': account['refresh_token'], 'token_type_hint': 'refresh_token', 'client_id': account['client_id']}).status_code == 200
        except HTTPException:
            pass
        # Keep registration/identity for reauthorization; remove every token together.
        for key in ('access_token', 'refresh_token', 'id_token'): account.pop(key, None)
        for attempt in data['attempts'].values():
            if attempt.get('accountId') == account_id and attempt.get('status') in ('pending', 'exchanging'):
                attempt.update(status='failed', message='账号已断开，原授权等待已取消')
        account.update(status='disconnected', canGenerate=False)
    return {'revocationConfirmed': confirmed, 'message': '账号已断开' if confirmed else '本地凭据已清除；未确认远端撤销，可在 ChatGPT 设置中断开应用'}
