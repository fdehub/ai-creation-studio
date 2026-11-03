"""Account management routes. OAuth callback has one-use state instead of app auth."""
import asyncio
import logging
from urllib.parse import urlsplit
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from account_store import vault
from chatgpt_oauth import attempt_status, begin_chatgpt, disconnect_chatgpt, finish_chatgpt, list_models
from muse_accounts import start_muse_login, disconnect_muse, check_muse, refresh_muse_usage
from security import authenticate

router = APIRouter(prefix='/api/accounts', dependencies=[Depends(authenticate)])
callback_router = APIRouter()


class CallbackLogFilter(logging.Filter):
    def filter(self, record):
        # Uvicorn's access record is (client, method, path-with-query, version, status).
        if isinstance(record.args, tuple) and len(record.args) == 5:
            values = list(record.args)
            if isinstance(values[2], str) and values[2].startswith('/api/accounts/oauth/chatgpt/callback'):
                values[2] = values[2].split('?', 1)[0]
                record.args = tuple(values)
        return True


logging.getLogger('uvicorn.access').addFilter(CallbackLogFilter())


def require_local_browser(request):
    hostname = urlsplit(request.headers.get('origin', '')).hostname
    if hostname not in {'localhost', '127.0.0.1', '::1'} or not request.client or request.client.host not in {'127.0.0.1', '::1'}:
        raise HTTPException(400, '此登录方式需在运行项目的本机浏览器中使用；远程页面不能操作服务器登录窗口')


class LoginRequest(BaseModel):
    accountId: str | None = Field(default=None, max_length=64)
    label: str = Field(default='Muse 账号', min_length=1, max_length=100)


@router.get('')
def accounts():
    return {'accounts': vault.accounts(), 'chatgptFlow': 'official-oss-oauth', 'museFlow': 'isolated-browser-session'}


@router.post('/chatgpt/login')
def chatgpt_login(req: LoginRequest, request: Request):
    require_local_browser(request)
    # The already-running API listener is the loopback callback listener.
    port = request.url.port or (443 if request.url.scheme == 'https' else 80)
    return begin_chatgpt(f'http://127.0.0.1:{port}/api/accounts/oauth/chatgpt/callback', req.accountId)


@router.get('/oauth/attempts/{attempt_id}')
def oauth_status(attempt_id: str):
    return attempt_status(attempt_id)


@callback_router.get('/api/accounts/oauth/chatgpt/callback')
def callback(request: Request):
    query = request.query_params
    try:
        finish_chatgpt(query.get('state', ''), code=query.get('code'), client_id=query.get('client_id'), error=query.get('error'))
        message, status = 'ChatGPT 授权已完成，请关闭此窗口并返回小说工作台。', 200
    except HTTPException:
        message, status = 'ChatGPT 授权未完成或回调已失效，请返回小说工作台查看状态并重新登录。', 400
    return HTMLResponse('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>账号授权</title><p>' + message + '</p></html>',
        status_code=status, headers={'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer',
                                    'Content-Security-Policy': "default-src 'none'; frame-ancestors 'none'"})


@router.post('/muse/login')
def muse_login(req: LoginRequest, request: Request):
    require_local_browser(request)
    return start_muse_login(req.accountId, req.label)


@router.get('/{account_id}/models')
def models(account_id: str):
    account = vault.account(account_id)
    if account['provider'] == 'chatgpt': return {'models': list_models(account_id)}
    return {'models': [{'id': 'muse', 'name': 'Muse 网页当前模型（由 Muse 决定）'}]}


@router.post('/{account_id}/check')
def check(account_id: str):
    account = vault.account(account_id)
    if account['provider'] == 'muse': return check_muse(account_id)
    list_models(account_id)
    return {'status': 'connected'}


@router.post('/{account_id}/usage')
def usage(account_id: str):
    return refresh_muse_usage(account_id)


@router.post('/{account_id}/disconnect')
def disconnect(account_id: str):
    account = vault.account(account_id)
    return disconnect_chatgpt(account_id) if account['provider'] == 'chatgpt' else disconnect_muse(account_id)
