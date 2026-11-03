// Muse selectors and fresh-thread approach informed by www222fff/muse2api (MIT).
// See third-party/muse2api-LICENSE.txt. Only app-owned isolated contexts are used.
import { chromium } from 'playwright'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createInterface } from 'node:readline'
import { readMuseUsage } from './muse_usage.mjs'

export const SITE = 'https://muse.ai'
export const BUBBLE = 'div[class*="hatch-agent-bubble-bg"]'
const STOP = 'button[aria-label*="Stop" i]'
const APPROVAL = '[data-testid="hatch-inline-approval-card"]'
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms))
const emit = value => process.stdout.write(JSON.stringify(value) + '\n')
let ownedBrowser
let parentDisconnected = false

export async function pageState(page) {
  return page.evaluate(({ bubble, stop, approval }) => {
    const nodes = [...document.querySelectorAll(bubble)]
    return { count: nodes.length, text: nodes.at(-1)?.innerText?.trim() || '',
      generating: !!document.querySelector(stop), approval: !!document.querySelector(approval),
      inputReady: !!document.querySelector('textarea:not([disabled])'),
      quotaAlert: [...document.querySelectorAll('[role=alert]')].some(node => !node.closest(bubble) && /out of credits|usage limit|limit reached|额度不足|用量上限/i.test(node.textContent || '')) }
  }, { bubble: BUBBLE, stop: STOP, approval: APPROVAL })
}

export async function collectReply(page, onDelta, { timeout = 180000, stableMs = 2500, pollMs = 250 } = {}) {
  const started = Date.now()
  let emitted = '', changed = Date.now()
  while (Date.now() - started < timeout) {
    if (page.isClosed()) throw new Error('Muse 浏览器已关闭，生成已停止')
    const state = await pageState(page)
    if (state.quotaAlert) throw new Error('Muse 账号额度不足')
    if (state.approval) throw new Error('Muse 请求额外操作确认，生成已停止；请在 Muse 中处理')
    if (state.count > 0 && state.text) {
      if (state.text !== emitted) {
        if (!state.text.startsWith(emitted)) throw new Error('Muse 修改了已输出内容，请重新生成')
        const delta = state.text.slice(emitted.length)
        emitted = state.text; changed = Date.now()
        onDelta(delta)
      }
      if (!state.generating && state.inputReady && Date.now() - changed >= stableMs) {
        return emitted
      }
    }
    await sleep(pollMs)
  }
  throw new Error('Muse 生成超时，已停止等待；请检查会话和额度')
}

export async function exportSession(context) {
  const state = await context.storageState()
  return { cookies: state.cookies.filter(c => c.domain === 'muse.ai' || c.domain.endsWith('.muse.ai')),
    origins: state.origins.filter(o => o.origin === SITE) }
}

async function sessionReady(page, context) {
  const cookies = await context.cookies(SITE)
  const active = cookies.some(c => c.name === 'hatch_sess' && c.value && (c.expires < 0 || c.expires * 1000 > Date.now()))
  if (!active || new URL(page.url()).origin !== SITE) return false
  try {
    return await page.evaluate(async () => {
      const response = await fetch('/api/session', { credentials: 'include' })
      if (!response.ok) return false
      const session = await response.json()
      return session.status === 'assigned'
    })
  } catch { return false }
}

export function transcript(messages) {
  if (!Array.isArray(messages) || !messages.length || messages.some(m => !['system', 'developer', 'user', 'assistant'].includes(m.role) || typeof m.content !== 'string')) throw new Error('Muse 仅支持纯文本写作消息')
  const text = messages.map(m => `[${m.role}]\n${m.content}`).join('\n\n')
  if (text.length > 200000) throw new Error('Muse 单次上下文过长，请缩短输入')
  return '请仅回答下面的写作任务，输出文字；不要访问外部服务、发送消息、操作文件或发布内容。\n\n' + text
}

export async function runWorker(command) {
  const login = command.action === 'login'
  if (!['login', 'generate', 'check', 'usage'].includes(command.action)) throw new Error('未知 Muse 操作')
  const channel = process.env.NOVEL_MUSE_BROWSER_CHANNEL || (!fs.existsSync(chromium.executablePath()) && process.platform === 'win32' ? 'msedge' : undefined)
  let browser, context
  try {
    browser = await chromium.launch({ headless: !login, ...(channel ? { channel } : {}) })
    ownedBrowser = browser
    if (parentDisconnected) throw new Error('Muse 调用已取消')
    context = await browser.newContext({ ...(command.session ? { storageState: command.session } : {}) })
    const page = await context.newPage()
    page.setDefaultTimeout(30000)
    await page.goto(SITE + (login || command.action === 'usage' ? '/' : '/thread/new'), { waitUntil: 'domcontentloaded', timeout: 60000 })
    if (login) {
      const deadline = Date.now() + 600000
      let ready = false
      while (Date.now() < deadline && !page.isClosed()) {
        if (await sessionReady(page, context)) { ready = true; break }
        await sleep(1000)
      }
      if (!ready) throw new Error('Muse 登录已取消或超时')
      emit({ type: 'session', session: await exportSession(context) })
      emit({ type: 'complete' })
      return
    }
    if (!await sessionReady(page, context)) throw new Error('Muse 会话已失效，请重新登录')
    if (command.action === 'usage') {
      try { emit({ type: 'usage', usage: await readMuseUsage(page) }) }
      catch (error) { throw new Error(error.message.startsWith('Muse') ? error.message : 'Muse 设置用量读取失败，请稍后刷新或重新登录') }
      emit({ type: 'session', session: await exportSession(context) })
      emit({ type: 'complete' }); return
    }
    if (command.action === 'check') {
      emit({ type: 'session', session: await exportSession(context) })
      emit({ type: 'complete' }); return
    }
    await page.waitForFunction(() => {
      const hydration = document.querySelector('[data-hatch-shell-hydration-state]')
      return !!document.querySelector('textarea:not([disabled])') && (!hydration || hydration.getAttribute('data-hatch-shell-hydration-state') === 'hydrated') && !document.body.innerText.includes('Connecting...')
    }, null, { timeout: 90000 })
    if (new URL(page.url()).pathname !== '/thread/new' || (await pageState(page)).count !== 0) throw new Error('未能打开 Muse 空白会话，已停止，防止串入历史内容')
    const input = page.locator('textarea').first()
    await input.fill(transcript(command.messages))
    const clicked = await page.evaluate(() => {
      const button = [...document.querySelectorAll('button,[role=button]')].find(b =>
        b.getClientRects().length && !b.disabled && /send|发送/i.test((b.getAttribute('aria-label') || '') + ' ' + (b.getAttribute('data-testid') || '')))
      if (!button) return false
      button.click(); return true
    })
    if (!clicked) await input.press('Enter')
    await page.waitForFunction(() => !document.querySelector('textarea')?.value, null, { timeout: 10000 })
    await collectReply(page, delta => emit({ type: 'delta', text: delta }))
    emit({ type: 'session', session: await exportSession(context) })
    emit({ type: 'complete' })
  } finally {
    if (context) await context.close().catch(() => {})
    if (browser) await browser.close().catch(() => {})
    ownedBrowser = undefined
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const input = createInterface({ input: process.stdin, crlfDelay: Infinity })
  const parentGone = () => { parentDisconnected = true; if (ownedBrowser) ownedBrowser.close().catch(() => {}) }
  try {
    const data = await new Promise((resolve, reject) => {
      input.once('line', resolve)
      input.once('close', () => reject(new Error('Muse 调用已取消')))
    })
    input.close()
    process.stdin.on('end', parentGone)
    process.stdin.resume()
    if (data.length > 4000000) throw new Error('请求过大')
    await runWorker(JSON.parse(data))
  } catch (error) {
    const safe = /^(Muse|未知 Muse|未能打开 Muse|请求过大)/.test(error.message || '') ? error.message : 'Muse 浏览器操作失败，请检查浏览器安装、登录状态和网站连接'
    emit({ type: 'error', message: safe.slice(0, 250) })
    process.exitCode = 1
  } finally {
    process.stdin.removeListener('end', parentGone)
    process.stdin.destroy()
  }
}
