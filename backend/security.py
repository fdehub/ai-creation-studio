import hmac
import ipaddress
import os
import secrets
import socket
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException, Request
from settings import ALLOWED_ORIGINS, ALLOWED_HOSTS

EXPLICIT_TOKEN = os.environ.get("NOVEL_ACCESS_TOKEN", "")
ACCESS_TOKEN = EXPLICIT_TOKEN or secrets.token_urlsafe(32)
LOCAL_HOSTS = {"localhost", "127.0.0.1", "[::1]", "::1"}
if not EXPLICIT_TOKEN and (any(host not in LOCAL_HOSTS for host in ALLOWED_HOSTS)
        or any(urlsplit(origin).hostname not in LOCAL_HOSTS for origin in ALLOWED_ORIGINS)):
    raise RuntimeError("远程部署必须配置 NOVEL_ACCESS_TOKEN")


def authenticate(request: Request):
    origin = request.headers.get("origin")
    if origin and origin not in ALLOWED_ORIGINS and origin != str(request.base_url).rstrip("/"):
        raise HTTPException(403, "不允许的页面来源")
    auth = request.headers.get("authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else ""
    if not token or not hmac.compare_digest(token.encode(), ACCESS_TOKEN.encode()):
        raise HTTPException(401, "请输入后端访问令牌", headers={"X-Novel-Session-Expired": "1"})


def local_session(request: Request):
    origin = request.headers.get("origin", "")
    peer = request.client.host if request.client else ""
    if (EXPLICIT_TOKEN or peer not in {"127.0.0.1", "::1"}
            or origin not in ALLOWED_ORIGINS
            or urlsplit(origin).hostname not in {"localhost", "127.0.0.1", "::1"}):
        raise HTTPException(401, "请使用部署时配置的后端访问令牌")
    return {"token": ACCESS_TOKEN}


def provider_target(url: str):
    """Validate an admin allowlist, then pin DNS; preserve Host and TLS SNI."""
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower()
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError:
        raise HTTPException(400, "模型服务地址无效")
    defaults = {"api.openai.com"}
    # Existing administrator-owned base URLs remain compatible; no key values
    # are copied, changed or sent during allowlist construction.
    for key, value in os.environ.items():
        if key.endswith("_BASE_URL"):
            configured = urlsplit(value).hostname
            if configured:
                defaults.add(configured.lower())
    allowed = {v.strip().lower() for v in os.environ.get(
        "NOVEL_PROVIDER_HOSTS", ",".join(defaults)).split(",") if v.strip()}
    local = {v.strip().lower() for v in os.environ.get(
        "NOVEL_LOCAL_PROVIDER_HOSTS", "").split(",") if v.strip()}
    if (host not in allowed | local or parsed.username or parsed.password
            or parsed.query or parsed.fragment or not parsed.path.endswith("/chat/completions")
            or parsed.scheme not in {"https", "http"}):
        raise HTTPException(400, "模型服务地址不在后端允许名单中")
    if host not in local and (parsed.scheme != "https" or port != 443):
        raise HTTPException(400, "公网模型服务必须使用 HTTPS 443")
    try:
        addresses = sorted({r[4][0] for r in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)})
        if not addresses or (host not in local and any(not ipaddress.ip_address(ip).is_global for ip in addresses)):
            raise HTTPException(400, "模型服务不能解析到本机或内网地址")
    except (socket.gaierror, ValueError):
        raise HTTPException(400, "模型服务地址解析失败")
    target = httpx.URL(url).copy_with(host=addresses[0])
    authority = f"[{host}]" if ":" in host else host
    if port != (443 if parsed.scheme == "https" else 80):
        authority += f":{port}"
    return target, authority, host


def provider_headers(headers: dict, authority: str):
    cleaned = {"Host": authority, "Content-Type": "application/json"}
    for key, value in headers.items():
        if key.lower() in {"authorization", "accept"} and isinstance(value, str):
            if "\r" in value or "\n" in value:
                raise HTTPException(400, "请求头包含非法字符")
            cleaned[key.lower()] = value
    return cleaned


def first_party_target(url, hosts):
    """Pin a fixed first-party OAuth/API URL, independent of model allowlists."""
    try:
        parsed = urlsplit(url)
        host = parsed.hostname or ''
        if (host not in hosts or parsed.scheme != 'https' or parsed.port not in (None, 443)
                or parsed.username or parsed.password or parsed.fragment or parsed.query):
            raise HTTPException(400, '授权服务地址无效')
        addresses = sorted({r[4][0] for r in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)})
        if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
            raise HTTPException(400, '授权服务不能解析到内网地址')
    except (ValueError, socket.gaierror):
        raise HTTPException(502, '无法解析授权服务地址')
    return httpx.URL(url).copy_with(host=addresses[0]), host, host


def post_provider(url, headers, payload, timeout=120):
    target, authority, host = provider_target(url)
    with httpx.Client(trust_env=False, follow_redirects=False, timeout=timeout) as client:
        return client.post(target, headers=provider_headers(headers, authority), json=payload,
                           extensions={"sni_hostname": host})
