import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import http from 'node:http'
import { spawn } from 'node:child_process'
import { chromium } from 'playwright'

const root = path.resolve(import.meta.dirname, '..')
const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'novel-browser-'))
const children = []
let browser
let provider
let lastProviderPayload
let failureLogs = ''
const uiPort = Number(process.env.NOVEL_TEST_UI_PORT || 15273)
const apiPort = Number(process.env.NOVEL_TEST_API_PORT || 18100)
function start(command, args, extraEnv) {
  const child = spawn(command, args, { cwd: root, windowsHide: true, env: { ...process.env, ...extraEnv }, stdio: ['ignore', 'pipe', 'pipe'] })
  child.stdout.on('data', data => { failureLogs += data })
  child.stderr.on('data', data => { failureLogs += data })
  children.push(child)
  return child
}
async function waitFor(url) {
  for (let i = 0; i < 100; i++) {
    if (children.some(c => c.exitCode !== null)) throw new Error('Test server exited before becoming ready')
    try { if ((await fetch(url)).ok) return } catch {}
    await new Promise(resolve => setTimeout(resolve, 100))
  }
  throw new Error('Timed out starting test servers')
}
async function until(check) {
  for (let i = 0; i < 80; i++) {
    if (await check()) return
    await new Promise(resolve => setTimeout(resolve, 100))
  }
  throw new Error('Browser assertion did not become true')
}
try {
  provider = http.createServer((req, res) => {
    let text = ''
    req.on('data', chunk => { text += chunk })
    req.on('end', () => {
      const body = JSON.parse(text)
      lastProviderPayload = body
      if (body.stream) {
        res.writeHead(200, { 'Content-Type': 'text/event-stream' })
        res.end('data: ' + JSON.stringify({ choices: [{ delta: { content: ' AI追加' } }] }) + '\n\ndata: [DONE]\n\n')
      } else {
        res.writeHead(200, { 'Content-Type': 'application/json' })
        res.end(JSON.stringify({ choices: [{ message: { content: '[]' } }] }))
      }
    })
  })
  await new Promise(resolve => provider.listen(0, '127.0.0.1', resolve))
  const modelPort = provider.address().port
  const origin = `http://127.0.0.1:${uiPort}`
  start(process.env.PYTHON || 'python', ['-m', 'uvicorn', 'main:app', '--app-dir', 'backend', '--host', '127.0.0.1', '--port', String(apiPort)], {
    NOVEL_DATA_DIR: directory, NOVEL_ACCESS_TOKEN: '', NOVEL_ALLOWED_ORIGINS: origin,
    NOVEL_PROVIDER_HOSTS: 'api.openai.com', NOVEL_LOCAL_PROVIDER_HOSTS: '127.0.0.1'
  })
  start(process.execPath, ['node_modules/vite/bin/vite.js'], { NOVEL_FRONTEND_PORT: String(uiPort), NOVEL_API_PROXY: `http://127.0.0.1:${apiPort}` })
  await waitFor(`http://127.0.0.1:${apiPort}/`)
  await waitFor(origin)
  for (const blocked of ['/backend/settings.py','/backend/settings.py?raw','/backend/ai_novel.db','/backend/.env','/src/recoveredData.js','/README.md', '/@fs/'+root.replaceAll('\\','/')+'/backend/settings.py']) {
    if ((await fetch(origin+blocked)).status !== 403) throw new Error('Vite exposed a non-frontend file: '+blocked)
  }
  const channel = process.env.NOVEL_BROWSER_CHANNEL || (!fs.existsSync(chromium.executablePath()) && process.platform === 'win32' ? 'msedge' : undefined)
  browser = await chromium.launch({ headless: true, ...(channel ? { channel } : {}) })
  const page = await browser.newPage()
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  page.on('dialog', dialog => dialog.type() === 'beforeunload' ? dialog.accept() : dialog.dismiss())
  await page.goto(origin)
  await until(() => page.evaluate(() => Boolean(sessionStorage.getItem('novel-backend-token'))))
  await page.evaluate(async modelPort => {
    const token = sessionStorage.getItem('novel-backend-token')
    const headers = { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }
    for (const title of ['Browser A', 'Browser B']) {
      const result = await fetch('/api/works', { method: 'POST', headers, body: JSON.stringify({ title, chapters: [{ id: `${title}-v`, chapters: [{ id: `${title}-c`, title: 'first', content: 'original' }] }] }) })
      if (!result.ok) throw new Error('Could not create fixture')
    }
    localStorage.setItem('ai-novel-platform-data-v6', JSON.stringify({
      llmConfigs: [{ id: 'default', name: 'Mock', apiKey: 'regression-placeholder', baseUrl: `http://127.0.0.1:${modelPort}/v1`, modelName: 'mock' }],
      agentAssignments: { EditorAgent: 'default', PlotAgent: 'default', LoreAgent: 'default' }
    }))
  }, modelPort)
  await page.reload()
  const particlesActive = () => page.locator('.particle-backdrop').evaluate(canvas => {
    if (canvas.dataset.animation !== 'running') return false
    const pixels = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data
    return pixels.some((value, index) => index % 4 === 3 && value > 0)
  })
  await until(particlesActive)
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await until(() => page.locator('.particle-backdrop').evaluate(canvas => canvas.dataset.animation === 'paused' && getComputedStyle(canvas).display === 'none'))
  await page.emulateMedia({ reducedMotion: 'no-preference' })
  await until(particlesActive)
  await page.locator('#novel-starter').scrollIntoViewIfNeeded()
  await until(() => page.locator('.particle-backdrop').getAttribute('data-animation').then(value => value === 'paused'))
  await page.locator('.menu-item').filter({ hasText: '策略与设置' }).click()
  await page.getByRole('checkbox', { name: '首页粒子特效', exact: true }).uncheck()
  await page.reload()
  if (await page.locator('.particle-backdrop').count()) throw new Error('Disabled particle setting did not survive reload')
  await page.locator('.menu-item').filter({ hasText: '策略与设置' }).click()
  await page.getByRole('checkbox', { name: '首页粒子特效', exact: true }).check()
  await page.locator('.menu-item').filter({ hasText: /^首页$/ }).click()
  await until(particlesActive)
  await page.locator('.menu-item').filter({ hasText: '写作编辑器' }).click()
  await page.locator('.content-editor').waitFor()
  const current = (await page.locator('.book-title').textContent()).trim()
  if (current !== 'Browser A') {
    await page.locator('.book-selector').click()
    await page.locator('.dropdown-item').filter({ hasText: 'Browser A' }).click()
  }
  await page.locator('.content-editor').fill('browser preserved manuscript')
  await page.locator('.book-selector').click()
  await page.locator('.dropdown-item').filter({ hasText: 'Browser B' }).click()
  const savedA = () => page.evaluate(async () => {
    const result = await fetch('/api/works/1', { headers: { Authorization: `Bearer ${sessionStorage.getItem('novel-backend-token')}` } })
    return (await result.json()).chapters[0].chapters[0].content
  })
  await until(async () => (await savedA()) === 'browser preserved manuscript')
  await page.route('**/api/works/*', route => route.request().method() === 'PUT' ? route.fulfill({ status: 503, contentType: 'application/json', body: '{"detail":"simulated disk error"}' }) : route.continue())
  await page.locator('.content-editor').fill('recoverable browser draft')
  await page.getByRole('button', { name: '保存作品', exact: true }).click()
  await page.getByRole('alert').filter({ hasText: '保存失败' }).waitFor()
  await page.reload()
  await page.getByText('发现未提交的本地草稿：').waitFor()
  await page.unroute('**/api/works/*')
  await page.getByRole('button', { name: '恢复草稿', exact: true }).click()
  await page.locator('.menu-item').filter({ hasText: '写作编辑器' }).click()
  await page.getByRole('button', { name: '保存作品', exact: true }).click()
  await until(() => page.evaluate(async () => {
    const result = await fetch('/api/works/2', { headers: { Authorization: `Bearer ${sessionStorage.getItem('novel-backend-token')}` } })
    return (await result.json()).chapters[0].chapters[0].content === 'recoverable browser draft'
  }))
  await page.locator('.menu-item').filter({ hasText: '写作编辑器' }).click()
  await page.locator('.book-selector').click()
  await page.locator('.dropdown-item').filter({ hasText: 'Browser B' }).click()
  await page.getByRole('button', { name: 'AI续写', exact: false }).click()
  await until(async () => (await page.locator('.content-editor').inputValue()).includes('AI追加'))
  // Export remains functional after moving it to the shared secondary action style.
  await page.locator('.menu-item').filter({ hasText: '章节管理' }).click()
  const downloadEvent = page.waitForEvent('download')
  await page.getByRole('button', { name: '导出TXT', exact: true }).click()
  const download = await downloadEvent
  const exported = fs.readFileSync(await download.path(), 'utf8')
  if (!exported.includes('recoverable browser draft') || !exported.includes('AI追加')) throw new Error('TXT export lost the current manuscript')
  // Real browser conversation storage, source citations and work isolation (mock model only).
  await page.locator('.menu-item').filter({ hasText: 'AI对话助手' }).click()
  await page.getByRole('textbox', { name: '创作问题', exact: true }).waitFor()
  if (await page.locator('.conversation-row').count()) throw new Error('New work showed fabricated conversation history')
  const question = page.getByRole('textbox', { name: '创作问题', exact: true })
  await question.fill('test line')
  await question.press('Shift+Enter')
  if (!(await question.inputValue()).includes('\n')) throw new Error('Shift+Enter must insert a line break')
  await question.fill('Inspect the cited fixture chapter')
  await page.getByRole('button', { name: '发送消息', exact: true }).click()
  await page.locator('.chat-message.ai').waitFor()
  if (!lastProviderPayload.messages[0].content.includes('recoverable browser draft')) throw new Error('Chat did not include the selected chapter source')
  if (!(await page.locator('.chat-message-actions button').filter({ hasText: '替换选中' }).isDisabled())) throw new Error('Replacement must be disabled without a valid editor selection')
  const chatWork = (await page.locator('.book-title').textContent()).trim()
  await page.reload()
  await page.locator('.menu-item').filter({ hasText: 'AI对话助手' }).click()
  if ((await page.locator('.book-title').textContent()).trim() !== chatWork) {
    await page.locator('.book-selector').click()
    await page.locator('.dropdown-item').filter({ hasText: chatWork }).click()
  }
  await page.locator('.chat-message.ai').waitFor()
  await page.getByRole('button', { name: '新对话', exact: true }).click()
  if (await page.locator('.chat-message.ai').count()) throw new Error('New conversation did not clear the active thread')
  await page.locator('.conversation-row').first().click()
  await page.locator('.chat-message.ai').waitFor()
  await page.locator('.book-selector').click()
  await page.locator('.dropdown-item').filter({ hasText: 'Browser A' }).click()
  await until(async () => !(await page.locator('.chat-message.ai').count()))
  await page.locator('.book-selector').click()
  await page.locator('.dropdown-item').filter({ hasText: chatWork }).click()
  await page.locator('.chat-message.ai').waitFor()
  // Modal focus and dismissal are tested without submitting or deleting anything.
  await page.locator('.menu-item').filter({ hasText: '我的作品' }).click()
  await page.getByRole('button', { name: '创建新作品', exact: true }).click()
  await page.getByRole('dialog').waitFor()
  await page.keyboard.press('Shift+Tab')
  if (!await page.evaluate(() => document.querySelector('[role=dialog]').contains(document.activeElement))) throw new Error('Modal focus escaped')
  await page.keyboard.press('Escape')
  await page.getByRole('dialog').waitFor({ state: 'hidden' })
  const screenshotDirectory = path.join(root, 'logs', 'release-review')
  fs.mkdirSync(screenshotDirectory, { recursive: true })
  await page.screenshot({ path: path.join(screenshotDirectory, 'desktop-works.png'), fullPage: true })
  const desktopViewport = page.viewportSize()
  await page.setViewportSize({ width: 375, height: 850 })
  await page.getByRole('button', { name: '展开导航', exact: true }).click()
  await page.getByRole('dialog', { name: '创作导航', exact: true }).waitFor()
  await page.keyboard.press('Escape')
  await page.getByRole('dialog', { name: '创作导航', exact: true }).waitFor({ state: 'hidden' })
  await page.locator('.menu-item').filter({ hasText: '提示词工程' }).click()
  const promptWidth = await page.locator('.prompt-main textarea').first().evaluate(el => el.getBoundingClientRect().width)
  if (promptWidth < 180) throw new Error('Mobile prompt editor is clipped')
  await page.locator('.menu-item').filter({ hasText: 'AI对话助手' }).click()
  const chatFits = await page.getByRole('textbox', { name: '创作问题', exact: true }).evaluate(el => {
    const r = el.getBoundingClientRect()
    return r.width > 180 && r.right <= innerWidth && r.bottom <= innerHeight
  })
  if (!chatFits) throw new Error('Mobile chat composer is clipped')
  await page.screenshot({ path: path.join(screenshotDirectory, 'mobile-chat.png'), fullPage: true })
  await page.setViewportSize(desktopViewport)
  // Exercise account settings with a simulated authorization server, never a real login.
  const linkedAccount = { id: 'ui-account-fixture', provider: 'chatgpt', label: 'OAuth fixture', status: 'connected', canGenerate: true }
  const museAccount = { id:'muse-usage-fixture', provider:'muse', label:'Muse fixture', status:'connected', canGenerate:true }
  let showMuse = false
  let authorized = false
  await page.route('**/api/accounts', route => route.fulfill({ contentType: 'application/json', body: JSON.stringify({ accounts: authorized ? [linkedAccount,...(showMuse?[museAccount]:[])] : [] }) }))
  await page.route('**/api/accounts/chatgpt/login', route => route.fulfill({ contentType: 'application/json', body: JSON.stringify({ attemptId: 'browser-fixture', authorizationUrl: origin + '/oauth-fixture' }) }))
  await page.route('**/oauth-fixture', route => route.fulfill({ contentType: 'text/html', body: '<p>Simulated authorization complete</p>' }))
  await page.route('**/api/accounts/oauth/attempts/browser-fixture', route => {
    authorized = true
    return route.fulfill({ contentType: 'application/json', body: JSON.stringify({ status: 'connected', account: linkedAccount }) })
  })
  await page.route('**/api/accounts/ui-account-fixture/models', route => route.fulfill({ contentType: 'application/json', body: JSON.stringify({ models: [{ id: 'oauth-model-fixture', name: 'OAuth fixture model' }] }) }))
  await page.locator('.menu-item').filter({ hasText: '策略与设置' }).click()
  await page.locator('.settings-nav .nav-item').filter({ hasText: 'AI 引擎策略' }).click()
  await page.getByRole('button', { name: 'Continue with ChatGPT', exact: true }).click()
  await page.getByText('ChatGPT 已授权。请选择可用模型并绑定 Agent。', { exact: true }).waitFor()
  await page.getByRole('button', { name: '绑定到所选 Agent', exact: true }).click()
  let accountRequest
  await page.route('**/api/proxy/chat', async route => {
    accountRequest = route.request().postDataJSON()
    return route.fulfill({ contentType: 'text/event-stream', body: 'data: ' + JSON.stringify({ choices: [{ delta: { content: ' 授权续写' } }] }) + '\n\ndata: [DONE]\n\n' })
  })
  await page.locator('.menu-item').filter({ hasText: '写作编辑器' }).click()
  await page.getByRole('button', { name: 'AI续写', exact: false }).click()
  await until(async () => (await page.locator('.content-editor').inputValue()).includes('授权续写'))
  if (accountRequest.headers['X-Novel-Account'] !== linkedAccount.id || accountRequest.headers.Authorization) throw new Error('Account request exposed credentials or lost its account reference')
  const persisted = await page.evaluate(() => JSON.parse(localStorage.getItem('ai-novel-platform-data-v6')))
  const config = persisted.llmConfigs.find(config => config.accountId === linkedAccount.id)
  if (!config || config.apiKey || config.access_token || config.refresh_token) throw new Error('OAuth credentials must never be saved in browser settings')
  showMuse = true
  let usageReads = 0
  await page.route('**/api/accounts/muse-usage-fixture/usage', route => {
    usageReads++
    if (usageReads === 2) return route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'fixture usage unavailable'})})
    const exhausted=usageReads>=3
    return route.fulfill({contentType:'application/json',body:JSON.stringify({usage:{source:'muse-settings',checkedAt:Date.now()/1000,rows:[
      {kind:'weekly',label:'免费版',description:'每周限额将在 11月6日重置',usedPercent:exhausted?100:0,valueLabel:exhausted?'已使用 100%':'已使用 0%'},
      {kind:'additional',label:'额外的使用额度',description:'从不过期',usedPercent:exhausted?100:0,valueLabel:exhausted?'剩余 0 个词元':'剩余 10 亿个词元'}
    ]}})})
  })
  await page.locator('.menu-item').filter({hasText:'策略与设置'}).click()
  await page.locator('.settings-nav .nav-item').filter({hasText:'AI 引擎策略'}).click()
  const usagePanel=page.getByRole('region',{name:'Muse 账户用量',exact:true})
  await usagePanel.getByText('剩余 10 亿个词元',{exact:true}).waitFor()
  await usagePanel.getByRole('button',{name:'刷新额度',exact:true}).click()
  await usagePanel.getByRole('alert').filter({hasText:'fixture usage unavailable'}).waitFor()
  if (!(await usagePanel.getByText('剩余 10 亿个词元',{exact:true}).isVisible())) throw new Error('Usage failure discarded the last known balance')
  await usagePanel.getByRole('button',{name:'刷新额度',exact:true}).click()
  await usagePanel.getByText('剩余 0 个词元',{exact:true}).waitFor()
  if (await usagePanel.getByRole('progressbar',{name:'免费版',exact:true}).getAttribute('aria-valuenow') !== '100') throw new Error('Exhausted quota was not updated')
  if (errors.length) throw new Error('Browser runtime errors: ' + errors.join('; '))
  console.log('Browser smoke passed: particles, settings persistence, editor/cross-work save/draft recovery, cited and persisted conversations/work isolation, modal focus, mobile navigation/prompt/chat layouts, mock streamed model output and OAuth model binding; zero page errors.')
} catch (error) {
  console.error(error)
  console.error(failureLogs)
  process.exitCode = 1
} finally {
  if (browser) await browser.close()
  for (const child of children) {
    if (child.exitCode === null) {
      child.kill()
      await new Promise(resolve => { child.once('exit', resolve); setTimeout(resolve, 5000).unref() })
    }
  }
  if (provider) await new Promise(resolve => provider.close(resolve))
  // Keep teardown non-destructive: only files created in this unique temp dir.
  const cleanupPath = fs.realpathSync(directory)
  const tempPath = fs.realpathSync(os.tmpdir())
  if (path.dirname(cleanupPath) !== tempPath || !path.basename(cleanupPath).startsWith('novel-browser-')) throw new Error('Unsafe test cleanup target')
  fs.rmSync(cleanupPath, { recursive: true, force: true })
}
