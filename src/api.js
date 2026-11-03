const API_ROOT = (import.meta.env?.VITE_API_BASE_URL || '/api').replace(/\/+$/, '')
let accessToken = globalThis.sessionStorage?.getItem('novel-backend-token') || ''
let sessionPromise = null

export function setBackendToken(token) {
  accessToken = token.trim()
  globalThis.sessionStorage?.setItem('novel-backend-token', accessToken)
}

export function apiUrl(path) {
  return API_ROOT + '/' + path.replace(/^\/api\/?|^\//, '')
}

async function responseError(response) {
  let detail = `请求失败：HTTP ${response.status}`
  try {
    const data = await response.json()
    if (typeof data.detail === 'string') detail = data.detail
  } catch { /* A reverse proxy may return a non-JSON error page. */ }
  const error = new Error(detail)
  error.status = response.status
  return error
}

async function ensureSession() {
  if (accessToken) return
  if (!sessionPromise) {
    sessionPromise = (async () => {
      const res = await fetch(apiUrl('/session'), { method: 'POST' })
      if (!res.ok) throw await responseError(res)
      setBackendToken((await res.json()).token)
    })().finally(() => { sessionPromise = null })
  }
  await sessionPromise
}

export async function apiFetch(path, options = {}) {
  await ensureSession()
  const headers = new Headers(options.headers)
  headers.set('Authorization', `Bearer ${accessToken}`)
  let response = await fetch(apiUrl(path), { ...options, headers })
  if (response.status === 401 && response.headers.get('X-Novel-Session-Expired') === '1') {
    setBackendToken('')
    await ensureSession()
    headers.set('Authorization', `Bearer ${accessToken}`)
    response = await fetch(apiUrl(path), { ...options, headers })
  }
  if (!response.ok) throw await responseError(response)
  return response
}

// Provider API keys remain in the existing user configuration. All network
// calls use the same authenticated proxy, including providers without CORS.
export function llmFetch(url, options) {
  return apiFetch('/proxy/chat', {
    method: 'POST', signal: options.signal,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url, headers: options.headers, body: JSON.parse(options.body) })
  })
}

export function hasModelCredentials(config) {
  return Boolean(config && (config.authType === 'account' ? config.accountId : config.apiKey))
}
export function modelAuthHeaders(config) {
  return config?.authType === 'account' ? { 'X-Novel-Account': config.accountId || '' } : { Authorization: `Bearer ${config?.apiKey || ''}` }
}
