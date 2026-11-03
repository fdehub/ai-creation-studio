// Capture the real UI with fictional demo data in an isolated local instance.
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { spawn, spawnSync } from 'node:child_process'
import { chromium } from 'playwright'

const root = path.resolve(import.meta.dirname, '..')
const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'creation-screenshots-'))
const output = path.join(root, 'docs', 'screenshots')
const uiPort = Number(process.env.NOVEL_SCREENSHOT_UI_PORT || 16273)
const apiPort = Number(process.env.NOVEL_SCREENSHOT_API_PORT || 18200)
const origin = `http://127.0.0.1:${uiPort}`
const python = process.env.PYTHON || path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')
const children = []
let browser
let serverLogs = ''

function start(command, args, settings) {
  const child = spawn(command, args, { cwd: root, windowsHide: true, env: { ...process.env, ...settings }, stdio: ['ignore', 'pipe', 'pipe'] })
  child.stdout.on('data', chunk => { serverLogs = (serverLogs + chunk).slice(-12000) })
  child.stderr.on('data', chunk => { serverLogs = (serverLogs + chunk).slice(-12000) })
  child.on('error', error => { serverLogs += error.message })
  children.push(child)
}
async function ready(url) {
  for (let i = 0; i < 100; i++) {
    if (children.some(child => child.exitCode !== null || !child.pid)) throw new Error('Isolated screenshot server failed to start')
    try { if ((await fetch(url)).ok) return } catch { /* Wait for this instance's listener. */ }
    await new Promise(resolve => setTimeout(resolve, 100))
  }
  throw new Error('Screenshot server startup timed out')
}

const manuscript = `第一章  末班渡船

雾从海面升起来的时候，沈知遥刚刚修好一段旧录音。

磁带里没有人说话，只有潮水拍打石阶的声音。可在第十七秒，一声清脆的船铃穿过底噪，随后传来一个女孩的低语：“别让最后一盏灯熄灭。”

她停下手中的笔。那是二十年前，母亲留给她的最后一句话。

窗外的钟楼敲过九点。档案馆的管理员早已离开，走廊只剩一盏暖黄的壁灯。沈知遥把磁带翻过来，在褪色的标签背面看见一行刚浮现的字迹：今晚，旧渡口。

她赶到码头时，末班渡船正要离岸。陆川站在船头，深蓝色的雨衣被风吹得鼓起。他没有问她为什么来，只把一张船票递到她面前。

“这班船昨天就停运了。”她说。

“我知道。”陆川抬头看向灯塔，“但有人替你买了今天的票。”

船票上没有日期，只有一道细细的银线。沈知遥将它举向灯光，银线慢慢拼成一幅地图，终点落在海图之外的一座小岛上。

就在这时，远处的灯塔忽然熄灭。录音机在她的背包里自行转动起来，磁带另一端的人，轻轻喊出了她的名字。`

const shots = [
  { shot: 1, desc: '远景。夜雾漫过旧渡口，灯塔的光束掠过海面。沈知遥沿着湿漉漉的石阶跑向最后一班渡船。', dialogue: '旁白：有些来信，要等一场大雾才会抵达。', prompt: 'Wide establishing shot of a foggy harbor at night, a young archivist running toward an old ferry, lighthouse beam across dark blue water, wet stone steps, cinematic composition, atmospheric lighting, illustrated storyboard, 16:9' },
  { shot: 2, desc: '中景。陆川站在船头，递来一张没有日期的船票。暖色船灯照亮两人的侧脸，身后是安静的海。', dialogue: '沈知遥：“这班船昨天就停运了。”\n陆川：“但有人替你买了今天的票。”', prompt: 'Medium two-person shot on the bow of an old ferry, a sailor in a navy raincoat handing a small ticket to a young woman, warm cabin light against cool mist, expressive faces, cinematic comic panel, 16:9' },
  { shot: 3, desc: '特写。船票上的银线在光下重新排列，拼成一幅指向未知小岛的地图。手指轻轻颤动。', dialogue: '旁白：那条航线，不在任何一本海图上。', prompt: 'Extreme close-up of hands holding an aged ferry ticket, silver lines forming a mysterious island map, delicate luminous details, shallow depth of field, suspenseful illustrated storyboard, 16:9' },
  { shot: 4, desc: '反打。灯塔突然熄灭，沈知遥回过头。背包里透出录音机的红色指示灯，海雾吞没了岸线。', dialogue: '录音机：“知遥，你终于来了。”', prompt: 'Over-the-shoulder shot of a young archivist turning toward an unlit lighthouse, a small red recorder light inside her bag, ferry disappearing into sea fog, dramatic blue-gray palette, cinematic comic composition, 16:9' }
]

const chapter = (id, title, content, summary, comicShots = []) => ({ id, title, content, summary, comicShots, status: '草稿', wordCount: content.length })
const demos = [
  { title: '第七次日落', tags: ['科幻', '冒险'], synopsis: '一位星际邮差在时间静止的小镇，寻找一封寄往明天的信。', status: '草稿', cover: 'linear-gradient(140deg, #bc5067, #ed8b9c)', chapters: [{ id: 'sunset-volume', title: '第一卷  时间之外', isExpanded: true, chapters: [
    chapter('sunset-1', '第一章  寄往明天的信', '小镇的日落每天都会准时重来。直到第七天，邮差在信箱里发现了一封来自明天的信。', '邮差发现时间循环中的第一处异常。'),
    chapter('sunset-2', '第二章  停摆的时钟', '', '追查信封邮戳，找到钟楼里唯一还在走动的秒针。')
  ] }] },
  { title: '雾港来信', tags: ['悬疑', '都市', '轻科幻'], synopsis: '声音档案修复师收到一盘来自过去的磁带，循着母亲留下的船铃声，踏上雾港之外的未知航线。', status: '草稿', cover: 'linear-gradient(140deg, #263345, #64748b)', chapters: [{ id: 'harbor-volume', title: '第一卷  灯塔来信', isExpanded: true, chapters: [
    chapter('harbor-1', '第一章  末班渡船', manuscript, '旧磁带留下约定，知遥在渡口收到一张没有日期的船票。', shots),
    chapter('harbor-2', '第二章  无声的灯塔', '天快亮时，渡船停在了一座没有名字的小岛边。沈知遥抬头望去，灯塔的窗户里放着一台与母亲一模一样的录音机。', '两人登岛，在灯塔中发现另一个声音档案。', shots.slice(0, 2)),
    chapter('harbor-3', '第三章  海图之外', '', '沿着银线地图寻找旧档案室，揭开航线为何消失的秘密。')
  ] }], characters: [
    { id: 'demo-shen', name: '沈知遥', faction: '主角', tags: ['档案修复师', '敏锐', '执着'], description: '二十七岁，声音档案修复师。擅长从杂音中辨认细节，在一盘旧磁带里听见母亲的声音，决定重新调查雾港的旧事。', avatarUrl: 'linear-gradient(135deg, #d78194, #ad4b65)', states: [{ chapterRange: [1, 12], stats: '初到雾港，寻找母亲留下的线索', equips: '旧式录音机、修复工具、银线船票' }] },
    { id: 'demo-lu', name: '陆川', faction: '配角', tags: ['渡船领航员', '寡言', '守诺'], description: '旧渡船的领航员，熟悉雾港每一段潮汐。他知道灯塔熄灭意味着什么，却始终没有说出船票真正的来历。', avatarUrl: 'linear-gradient(135deg, #73869b, #334155)', states: [] }
  ], worldview: [{ id: 'demo-world', title: '雾港与航线', icon: '🌊', items: [{ name: '银线船票', desc: '只在灯下显影的旧船票，会为持票人标出一条不存在于公开海图上的航线。', type: 'Normal' }] }] }
]

try {
  start(python, ['-m', 'uvicorn', 'main:app', '--app-dir', 'backend', '--host', '127.0.0.1', '--port', String(apiPort)], {
    NOVEL_DATA_DIR: directory, NOVEL_ACCESS_TOKEN: '', NOVEL_ALLOWED_ORIGINS: origin,
    NOVEL_PROVIDER_HOSTS: '', NOVEL_LOCAL_PROVIDER_HOSTS: ''
  })
  start(process.execPath, ['node_modules/vite/bin/vite.js'], { NOVEL_FRONTEND_PORT: String(uiPort), NOVEL_API_PROXY: `http://127.0.0.1:${apiPort}` })
  await ready(`http://127.0.0.1:${apiPort}/`)
  await ready(origin)
  const session = await fetch(origin + '/api/session', { method: 'POST', headers: { Origin: origin } })
  if (!session.ok) throw new Error('Could not establish isolated screenshot session')
  const { token } = await session.json()
  for (const data of demos) {
    const response = await fetch(origin + '/api/works', { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }, body: JSON.stringify(data) })
    if (!response.ok) throw new Error('Could not create fictional screenshot work')
  }

  const channel = process.env.NOVEL_BROWSER_CHANNEL || (!fs.existsSync(chromium.executablePath()) && process.platform === 'win32' ? 'msedge' : undefined)
  browser = await chromium.launch({ headless: true, ...(channel ? { channel } : {}) })
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1, locale: 'zh-CN', colorScheme: 'light' })
  await context.route('**/*', route => {
    const url = new URL(route.request().url())
    if (url.origin !== origin || /^\/api\/(proxy|agents|accounts)(\/|$)/.test(url.pathname)) return route.abort()
    return route.continue()
  })
  const page = await context.newPage()
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  await page.goto(origin)
  await page.locator('.creator-work-row').filter({ hasText: '雾港来信' }).waitFor()
  fs.mkdirSync(output, { recursive: true })
  const capture = async filename => {
    await page.evaluate(() => document.fonts.ready)
    await page.mouse.move(1420, 990)
    if (await page.getByText('发现未提交的本地草稿：', { exact: true }).count()) throw new Error('Unexpected recovery state in screenshot fixture')
    await page.screenshot({ path: path.join(output, filename), fullPage: false, animations: 'disabled' })
  }
  await capture('workspace.png')

  await page.locator('.creator-work-row').filter({ hasText: '雾港来信' }).getByRole('button', { name: '继续创作', exact: true }).click()
  await page.locator('.chapter-item').first().click()
  await page.getByRole('textbox', { name: '章节正文', exact: true }).waitFor()
  if (!(await page.locator('.content-editor').inputValue()).includes('雾从海面升起来')) throw new Error('Editor did not load the fictional manuscript')
  await capture('writing-editor.png')

  await page.locator('.menu-item').filter({ hasText: '漫剧工坊' }).click()
  await page.locator('.control-panel select').selectOption('harbor-1')
  await page.locator('.shot-card').first().waitFor()
  if (await page.locator('.shot-card').count() !== 4) throw new Error('Comic fixture did not load all example shots')
  await capture('comic-studio.png')
  if (errors.length) throw new Error('Screenshot pages raised runtime errors: ' + errors.join('; '))
  console.log('Captured 3 real UI screenshots with fictional works and sample storyboards. No real account, private database or model request used.')
} catch (error) {
  console.error(error.message)
  console.error(serverLogs)
  process.exitCode = 1
} finally {
  if (browser) await browser.close()
  for (const child of children) {
    if (child.exitCode !== null || !child.pid) continue
    if (process.platform === 'win32') spawnSync('taskkill', ['/PID', String(child.pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore' })
    else child.kill()
    await new Promise(resolve => { if (child.exitCode !== null) return resolve(); child.once('exit', resolve); setTimeout(resolve, 5000).unref() })
  }
  const target = fs.realpathSync(directory)
  if (path.dirname(target) !== fs.realpathSync(os.tmpdir()) || !path.basename(target).startsWith('creation-screenshots-')) throw new Error('Unsafe screenshot temp cleanup path')
  fs.rmSync(target, { recursive: true, force: true })
}
