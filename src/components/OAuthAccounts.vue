<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { apiFetch } from '../api.js'
import { store } from '../store.js'
import MuseUsage from './MuseUsage.vue'

const accounts = ref([])
const error = ref('')
const notice = ref('')
const loading = ref(false)
const busy = ref('')
const models = ref({})
const selections = ref({})
const bindRole = ref('all')
const usageLoading = ref({})
const usageErrors = ref({})
const usageAttempts = new Set()
const loginAttempt = ref(null)
const localBrowser = computed(() => ['127.0.0.1', 'localhost', '[::1]'].includes(window.location.hostname))
let timer
let alive = true
let popup
const statuses = { connected: '已连接', disconnected: '已断开', pending: '等待登录', failed: '登录未完成' }
const post = data => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) })

async function refreshAccounts() {
  const result = await (await apiFetch('/accounts')).json()
  if (!alive) return
  accounts.value = result.accounts
  for (const account of accounts.value) {
    if (account.provider === 'muse' && account.status === 'connected' && !usageAttempts.has(account.id) && (!account.usage?.checkedAt || Date.now() - account.usage.checkedAt * 1000 > 60000)) loadUsage(account)
  }
}
async function loadUsage(account) {
  if (usageLoading.value[account.id]) return
  usageAttempts.add(account.id)
  usageLoading.value[account.id] = true; usageErrors.value[account.id] = ''
  try {
    const result = await (await apiFetch(`/accounts/${account.id}/usage`, {method:'POST'})).json()
    const current = accounts.value.find(item => item.id === account.id && item.status === 'connected')
    if (alive && current) current.usage = result.usage
  } catch (e) { if (alive) usageErrors.value[account.id] = e.message }
  finally { if (alive) usageLoading.value[account.id] = false }
}
async function loadModels(account) {
  try {
    const result = await (await apiFetch(`/accounts/${account.id}/models`)).json()
    models.value[account.id] = result.models
    if (!result.models.some(m => m.id === selections.value[account.id])) selections.value[account.id] = result.models[0]?.id || ''
    if (!result.models.length) notice.value = '该账号暂未返回可用模型，请检查账号权限。'
  } catch (e) { error.value = e.message }
}
async function load() {
  loading.value = true; error.value = ''
  try {
    await refreshAccounts()
    if (accounts.value.some(a => a.provider === 'muse' && a.status === 'pending')) schedulePoll()
  } catch (e) { error.value = e.message }
  finally { loading.value = false }
}
function schedulePoll() {
  clearTimeout(timer)
  timer = setTimeout(poll, 2000)
}
async function poll() {
  if (!alive) return
  try {
    if (loginAttempt.value) {
      const result = await (await apiFetch(`/accounts/oauth/attempts/${loginAttempt.value}`)).json()
      if (result.status === 'pending' && popup?.closed) { loginAttempt.value = null; busy.value = ''; notice.value = '登录窗口已关闭，可重新发起授权。' }
      if (['connected', 'failed', 'expired'].includes(result.status)) {
        loginAttempt.value = null; busy.value = ''
        if (popup && !popup.closed) popup.close()
        if (result.status === 'connected') {
          notice.value = 'ChatGPT 已授权。请选择可用模型并绑定 Agent。'
          if (result.account?.canGenerate) await loadModels(result.account)
        } else error.value = result.message || '授权已过期，请重新登录'
      }
    }
    await refreshAccounts()
    if (accounts.value.some(a => a.provider === 'muse' && a.status === 'pending')) schedulePoll()
    else if (busy.value === 'muse') { busy.value = ''; notice.value = 'Muse 登录窗口已结束，请查看账号状态并绑定 Agent。' }
    if (loginAttempt.value) schedulePoll()
  } catch (e) { error.value = e.message; if (alive && (loginAttempt.value || busy.value === 'muse')) schedulePoll() }
}
async function loginChatGPT(accountId) {
  if (!localBrowser.value) return
  error.value = ''; notice.value = ''; busy.value = 'chatgpt'
  // Open synchronously to avoid popup blockers; the provider cannot reach the opener.
  popup = window.open('about:blank', '_blank', 'popup=yes,width=650,height=780')
  if (popup) popup.opener = null
  try {
    const result = await (await apiFetch('/accounts/chatgpt/login', post({ accountId }))).json()
    loginAttempt.value = result.attemptId
    if (!popup) throw new Error('浏览器拦截了登录窗口，请允许弹出窗口后重试')
    popup.location.href = result.authorizationUrl
    notice.value = '请在官方授权页完成登录和模型使用授权。'
    schedulePoll()
  } catch (e) {
    error.value = e.message; busy.value = ''; loginAttempt.value = null
    if (popup && !popup.closed) popup.close()
  }
}
async function loginMuse(accountId) {
  if (!localBrowser.value) return
  error.value = ''; notice.value = ''; busy.value = 'muse'
  if (accountId) { usageAttempts.delete(accountId); usageErrors.value[accountId] = '' }
  try {
    const result = await (await apiFetch('/accounts/muse/login', post({ accountId }))).json()
    notice.value = result.message
    await refreshAccounts(); schedulePoll()
  } catch (e) { error.value = e.message; busy.value = '' }
}
async function check(account) {
  error.value = ''
  try {
    await apiFetch(`/accounts/${account.id}/check`, { method: 'POST' })
    await refreshAccounts()
    notice.value = '账号连接检查通过。'
    await loadModels(account)
  } catch (e) { error.value = e.message }
}
async function disconnect(account) {
  if (!confirm(`断开 ${account.label}？已绑定的 Agent 将无法继续使用此账号。`)) return
  try {
    const result = await (await apiFetch(`/accounts/${account.id}/disconnect`, { method: 'POST' })).json()
    notice.value = result.message
    await refreshAccounts()
  } catch (e) { error.value = e.message }
}
async function bind(account) {
  if (account.status !== 'connected' || !account.canGenerate) return
  if (account.provider === 'muse') selections.value[account.id] = 'muse'
  if (!selections.value[account.id]) { await loadModels(account); return }
  const model = selections.value[account.id]
  let config = store.llmConfigs.find(c => c.authType === 'account' && c.accountId === account.id && c.modelName === model)
  if (!config) {
    config = { id: 'account-' + crypto.randomUUID(), name: `${account.label} · ${model}`,
      authType: 'account', accountId: account.id, provider: account.provider, apiKey: '', baseUrl: '', modelName: model }
    store.llmConfigs.push(config)
  }
  const roles = bindRole.value === 'all' ? ['EditorAgent', 'PlotAgent', 'LoreAgent'] : [bindRole.value]
  for (const role of roles) store.agentAssignments[role] = config.id
  notice.value = `账号模型已绑定到 ${bindRole.value === 'all' ? '全部 Agent' : bindRole.value}。`
}
onMounted(load)
onUnmounted(() => { alive = false; clearTimeout(timer) })
</script>

<template>
  <section class="accounts-panel" aria-label="平台账号授权">
    <h4>平台账号登录</h4>
    <p>ChatGPT 使用官方 OAuth；Muse 参考 muse2api 的网页会话方式，登录后可直接用于写作。账号令牌和会话加密保存在本机后端。此工作台仍为单用户模式，持有工作台访问令牌的人可使用已连接账号。</p>
    <p v-if="!localBrowser" class="account-error">账号登录需要在运行本项目的电脑上打开工作台。远程页面不能打开服务器登录窗口。</p>
    <div class="account-toolbar">
      <button :disabled="Boolean(busy) || !localBrowser" @click="loginChatGPT()">Continue with ChatGPT</button>
      <button :disabled="Boolean(busy) || !localBrowser" @click="loginMuse()">登录 Muse（网页会话）</button>
      <button :disabled="loading" @click="load">刷新账号</button>
    </div>
    <p v-if="error" class="account-error" role="alert">{{ error }}</p>
    <p v-if="notice" class="account-notice" role="status">{{ notice }}</p>
    <p v-if="loading">正在读取账号…</p>
    <p v-else-if="!accounts.length">尚未连接账号，现有 API Key 配置可继续使用。</p>
    <div class="account-toolbar" v-if="accounts.length">
      <label>绑定范围
        <select v-model="bindRole"><option value="all">全部 Agent</option><option value="EditorAgent">写作编辑</option><option value="PlotAgent">人物与情节</option><option value="LoreAgent">世界观</option></select>
      </label>
    </div>
    <article v-for="account in accounts" :key="account.id" class="account-card">
      <div><strong>{{ account.label }}</strong> <span>{{ account.provider === 'chatgpt' ? '官方 OAuth' : 'Muse 网页会话' }} · {{ statuses[account.status] || account.status }}</span></div>
      <p v-if="account.status === 'connected' && !account.canGenerate" class="account-error">账号已登录，但未授予模型使用权限，请重新授权。</p>
      <p v-if="account.message" class="account-error">{{ account.message }}</p>
      <p v-if="account.provider === 'muse'">调用 Muse 网站当前提供的模型，不使用其他平台的模型别名。</p>
      <MuseUsage v-if="account.provider === 'muse' && account.status === 'connected'" :usage="account.usage" :loading="usageLoading[account.id]" :error="usageErrors[account.id]" @refresh="loadUsage(account)" />
      <div class="account-toolbar">
        <template v-if="account.status === 'connected' && account.canGenerate">
          <button @click="check(account)">检查连接</button>
          <button @click="loadModels(account)">读取可用模型</button>
          <select v-if="models[account.id]?.length" v-model="selections[account.id]" :aria-label="account.label + '模型'"><option v-for="model in models[account.id]" :key="model.id" :value="model.id">{{ model.name }}</option></select>
          <button @click="bind(account)">绑定到所选 Agent</button>
        </template>
        <button :disabled="Boolean(busy) || !localBrowser || account.status === 'pending' || usageLoading[account.id]" @click="account.provider === 'chatgpt' ? loginChatGPT(account.id) : loginMuse(account.id)">重新登录</button>
        <button v-if="account.status !== 'pending' && account.status !== 'disconnected'" @click="disconnect(account)">断开账号</button>
      </div>
    </article>
    <p class="account-footnote">ChatGPT 的可用模型与额度由账号授权和套餐决定；Muse 需要本机浏览器，网页结构变化时可能需要更新适配器。首次授权请由你本人完成。</p>
  </section>
</template>

<style scoped>
.accounts-panel { padding: 20px; margin: 20px 0; border: 1px solid var(--border-color); border-radius: 12px; background: var(--panel-bg); color: var(--text-primary); }
h4 { margin: 0 0 12px; }
p { font-size: 13px; line-height: 1.7; color: var(--text-secondary); }
.account-toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin: 12px 0; }
button, select { padding: 8px 12px; border: 1px solid var(--border-color); border-radius: 7px; background: var(--panel-bg); color: var(--text-primary); cursor: pointer; }
button:disabled { opacity: .5; cursor: default; }
.account-card { padding: 16px 0; border-top: 1px solid var(--border-color); }
.account-card span { margin-left: 8px; font-size: 12px; color: var(--text-secondary); }
.account-error { color: var(--danger-color); }
.account-notice { color: var(--success-color); }
.account-footnote { margin-bottom: 0; }
</style>
