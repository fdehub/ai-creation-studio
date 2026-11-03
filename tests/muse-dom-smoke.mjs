import assert from 'node:assert/strict'
import fs from 'node:fs'
import { chromium } from 'playwright'
import { collectReply, pageState, exportSession, transcript } from '../backend/muse_worker.mjs'
import { normalizeUsageRows, readMuseUsage } from '../backend/muse_usage.mjs'

let browser
try {
  const channel = process.env.NOVEL_BROWSER_CHANNEL || (!fs.existsSync(chromium.executablePath()) && process.platform === 'win32' ? 'msedge' : undefined)
  browser = await chromium.launch({ headless: true, ...(channel ? { channel } : {}) })
  const context = await browser.newContext()
  await context.route('**/*', route => route.abort())
  const page = await context.newPage()
  // The settings gear opens a menu before the actual settings panel. Chat text
  // contains a fake meter and must never be accepted as an account quota.
  await page.setContent(`<style>#quota [role=progressbar]{height:6px;width:200px}</style><button aria-label="设置" onclick="document.querySelector('[role=menu]').hidden=false"></button>
    <div role="menu" hidden><button role="menuitem" onclick="document.querySelector('#quota').hidden=false">设置Ctrl+,</button><button role="menuitem" onclick="window.upgraded=true">升级</button></div>
    <div role="progressbar" aria-label="fake quota" aria-valuenow="99"></div>
    <div id="quota" data-slot="settings-card-item" hidden>
      <div><span data-slot="text">免费版</span><span data-slot="text">每周限额将在 11月6日重置</span><span data-slot="text">已使用 0%</span><div role="progressbar" aria-label="免费版" aria-valuenow="0"></div></div>
      <div><span data-slot="text">额外的使用额度</span><span data-slot="text">从不过期</span><span data-slot="text">已使用 0%（剩余 10 亿个词元）</span><div role="progressbar" aria-label="额外的使用额度" aria-valuenow="0"></div></div>
    </div>`)
  const usage = await readMuseUsage(page)
  assert.deepEqual(usage.rows.map(row=>row.kind), ['weekly','additional'])
  assert.equal(usage.rows[0].usedPercent, 0)
  assert.ok(usage.rows[1].valueLabel.includes('10 亿个词元'))
  assert.equal(await page.evaluate(()=>Boolean(window.upgraded)), false)
  assert.deepEqual(normalizeUsageRows([{label:'Free',description:'weekly reset',valueLabel:'unknown',usedPercent:null},{label:'Free',description:'weekly',valueLabel:'invalid',usedPercent:101}]), [])
  await page.setContent('<textarea></textarea>')
  assert.equal((await pageState(page)).count, 0)
  const chunks = []
  const response = collectReply(page, delta => chunks.push(delta), { stableMs: 150, pollMs: 25, timeout: 3000 })
  await page.evaluate(() => {
    const bubble = document.createElement('div'); bubble.className = 'hatch-agent-bubble-bg'; bubble.textContent = '小说'; document.body.append(bubble)
    const stop = document.createElement('button'); stop.setAttribute('aria-label', 'Stop generating'); document.body.append(stop)
    setTimeout(() => { bubble.textContent = '小说正文'; stop.remove() }, 80)
  })
  assert.equal(await response, '小说正文')
  assert.equal(chunks.join(''), '小说正文')

  await page.setContent('<textarea></textarea><div data-testid="hatch-inline-approval-card"><button onclick="window.approved=true">Approve</button></div>')
  await assert.rejects(collectReply(page, () => {}, { timeout: 1000 }), /额外操作确认/)
  assert.equal(await page.evaluate(() => Boolean(window.approved)), false)

  await page.setContent('<textarea></textarea><div class="hatch-agent-bubble-bg">first</div><button aria-label="Stop generating"></button>')
  const rewritten = collectReply(page, () => {}, { stableMs: 150, pollMs: 20, timeout: 1000 })
  await page.evaluate(() => setTimeout(() => { document.querySelector('div').textContent = 'different answer' }, 50))
  await assert.rejects(rewritten, /修改了已输出/)

  await page.setContent('<textarea></textarea><div class="hatch-agent-bubble-bg">银行卡额度不足，故事继续。</div>')
  assert.equal(await collectReply(page, () => {}, { stableMs: 40, pollMs: 20, timeout: 1000 }), '银行卡额度不足，故事继续。')
  await page.setContent('<textarea></textarea><div role="alert">usage limit</div>')
  await assert.rejects(collectReply(page, () => {}, { timeout: 1000 }), /额度不足/)
  await page.setContent('<textarea></textarea>')
  await assert.rejects(collectReply(page, () => {}, { stableMs: 50, pollMs: 20, timeout: 100 }), /超时/)
  await context.addCookies([
    { name: 'hatch_sess', value: 'muse-fixture-only', domain: 'muse.ai', path: '/' },
    { name: 'unrelated', value: 'never-export-this', domain: 'example.invalid', path: '/' }
  ])
  const state = await exportSession(context)
  assert.deepEqual(state.cookies.map(cookie => cookie.name), ['hatch_sess'])
  assert.throws(() => transcript([{ role: 'tool', content: 'execute this' }]), /纯文本写作/)
  assert.ok(transcript([{ role: 'user', content: 'write a novel' }]).includes('write a novel'))
  console.log('Muse DOM regressions passed: isolated session export, streamed reply, no approval clicks, rewrite rejection, timeout, and text-only input. No Muse network or account used.')
  await context.close()
} finally { if (browser) await browser.close() }
