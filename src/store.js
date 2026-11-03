import { reactive, watch, computed } from 'vue'
import { apiFetch, hasModelCredentials } from './api.js'
import { saveDraft, removeDraft, loadDrafts } from './drafts.js'

const STORAGE_KEY = 'ai-novel-platform-data-v6'

const defaultState = {
  activeMenuItem: '首页',
  activeWorkId: 1,
  activeChapterId: 11,
  pendingFixRange: null,
  pendingFixLabel: '',
  editorSelection: null,
  pendingEditorAction: null,
  llmConfigs: [
    { id: 'default', name: 'OpenAI (默认)', apiKey: '', baseUrl: '', modelName: 'gpt-4-turbo-preview' }
  ],
  agentAssignments: {
    EditorAgent: 'default',
    PlotAgent: 'default',
    LoreAgent: 'default'
  },
  prompts: {
    // 工业化流水线推演大纲
    long_outline_generate: `你是一个顶级网文主笔编辑(EditorAgent)。你要为一个长篇小说规划细纲。
【全书总篇幅：100章】（系统将读取此数字，并循序渐进循环推演直到完成该目标）
目标：本次循环请生成第 {start} 章到第 {end} 章的大纲（共 {count} 章）。
严格输出 JSON 数组，格式：
[ { "chapterNum": "第X章", "title": "章名", "summary": "本章剧情一句话概括" } ]
要求：
1. 紧密衔接上文："{last_summary}"
2. 参考核心角色和长线剧情节点。
3. 严格遵循 JSON 格式，不要返回 markdown 代码块，纯 JSON 数组。`,

    // 世界观构筑
    worldview_auto_construct: `你是一个顶级网文世界观架构师。你需要为一个叫做《{title}》的{tags}小说构筑一个大类。\n所在面板：{tab}。大类名称：“{category}”。\n请生成2到3个具体词条设定，要求网文味浓厚，有设定感和悬念。\n输出格式严格为 JSON 数组：\n[{"name": "词条名", "desc": "详细描述..."}]\n不要输出 markdown，纯 json 文本。`,
    worldview_expand_item: `你是一个顶级网文世界观架构师。目前正在构建小说《{title}》。\n在大类“{category}”中，有一个核心设定叫：“{name}”。\n其描述为：“{desc}”。\n请基于该设定，向下深挖出 1-2 个具体的“衍生子设定”（例如：如果父设定是某个组织，子设定可以是它的隐秘机构、核心功法或代表人物）。\n输出格式严格为 JSON 数组：\n[{"name": "子设定名称", "desc": "子设定详细描述..."}]\n不要输出 markdown，纯 json 文本。`,
    worldview_polish_item: `你是一个顶级网文世界观架构师。目前正在构建小说《{title}》（{tags}）的设定。\n当前大类：“{category}”。\n词条名称：“{name}”。\n原描述：“{desc}”。\n请根据以上信息，为该词条生成一段极具网文张力、悬念感和脑洞的详细设定描述（大约50-100字左右）。\n要求：直接输出描述内容，不要输出任何其他的解释文字、标题或 Markdown 标记。`,
    
    // 情节引擎
    plot_generate_twist: `你是一位深谙好莱坞编剧理论与爆款网文节奏的情节架构师。\n小说《{title}》（{tags}）。\n请根据现有剧情进展，生成一个出人意料且符合逻辑的【剧情转折】。\n输出严格为 JSON 格式：\n{"type": "起|承|转|合|反转|高潮", "title": "节点标题", "tension": 80, "desc": "剧情描述（100字内）"}`,
    
    // 人物工坊
    character_generate: `你是一位顶级网文角色设定师。请为小说《{title}》（{tags}）随机生成一个充满戏剧冲突的新角色。
要求：
1. faction (阵营) 必须严格从 ["主角", "反派", "配角"] 这3个词中选择其一，绝对不能写其他身份描述！
2. 身份背景写在 description 中，并包含核心性格和秘密。
3. 必须包含 states 数组（境界与装备）。
输出严格为 JSON 格式：
{"name": "姓名", "faction": "主角|反派|配角", "tags": ["标签1", "标签2", "标签3"], "description": "角色小传（100字左右）", "states": [{"chapterRange": [1, 90], "stats": "当前境界/身份", "equips": "核心装备/功法"}]}`,
    character_expand: `你是一位顶级网文角色设定师。目前小说《{title}》中有一名角色“{name}”（阵营：{faction}）。\n当前设定：“{description}”。\n请针对该角色进行脑洞扩写，增加更多不为人知的秘密、深层动机或伏笔。\n直接输出扩写后的角色小传，不要返回标题和 markdown。`,
    
    // 写作辅助
    editor_continue: `你是一位深谙“现代言情、黑道大佬与甜宠拉扯”题材的白金级网文大神。请根据上下文，紧接着续写后续剧情。
【核心写作军规】
1. 强化危险与禁忌的性张力：这是“小白兔误入狼窝/被闺蜜的黑道小叔盯上”的题材。男女主同框时，必须刻画出男主作为上位者的绝对压迫感、危险气息，以及女主心底的局促、背德感与生理性紧张。
2. 细节烘托氛围 (Show, Don't Tell)：男主的情绪不要明写，通过他指尖弹烟灰的动作、解开衬衫顶扣的漫不经心、或是锁定猎物般的深邃眼神来展现。女主的紧张要通过呼吸错乱、视线闪躲、指节发白来体现。
3. 极限推拉的对话交锋：对话必须充满暧昧的试探、步步紧逼的压迫，或是看似长辈关心实则充满占有欲的潜台词。绝不要说废话。
4. 续写长度约200-500字，请务必“拖慢节奏”，把这种让人脸红心跳的危险氛围拉满。绝对不要轻易得出最终结论，绝对不要擅自写出“本章完”！
5. 直接输出纯续写内容，不要返回任何多余解释。`,
    editor_conclude: `你是一位顶级的现言小说作家，精通“暧昧拉扯”与“断章”技巧。请为当前章节写一个极其勾人的收尾。
【核心写作军规】
1. 定格危险与暧昧：收尾时不要空洞总结，请用一个极具侵略性的动作（如男主突然拉近距离、阴影笼罩女主）、一句意味深长的低语、或一个让女主心跳骤停的突发事件来定格画面。
2. 强化禁忌悬念：悬念要卡在两人关系即将越界、或者某种危险秘密即将曝光的最高潮瞬间。
3. 绝对半截断章：不要去解答当前的悬念！如果男主刚刚逼近，或者女主刚刚退无可退，请直接在此处“强行切断”，让读者抓心挠肝！
4. 字数控制在50-200字以内。
5. 直接输出纯正文收尾，不要多余废话。在输出内容的最后一行，必须单独输出一行“【本章完】”。`,
    comic_generate_script: `你是一位顶级的电影分镜师和 AI 绘画提示词专家。
请将提供的纯文本小说内容，按照影视化标准拆解为连续的分镜头剧本，并为每个镜头生成用于 Midjourney 绘画的英文 Prompt。
要求输出严格的 JSON 数组格式，不要包含任何 markdown 标记：
[{
  "shot": 1,
  "desc": "中文画面描述（时间、地点、人物动作、表情、机位）",
  "dialogue": "台词或旁白（如果没有则为空）",
  "prompt": "英文绘画提示词（主体描述, 环境, 光影, 镜头语言 --ar 16:9）"
}]
小说原文：\n{content}`,
    editor_polish: `你是一位资深网文编辑。请对用户提供的文本进行润色。\n要求：\n1. 修复语病，提升文笔流畅度。\n2. 增强动作描写、情绪渲染和氛围感。\n3. 保持原有剧情走向不变。\n4. 直接输出润色后的文本，不要多余解释。`,
    editor_expand: `你是一位擅长环境描写和心理刻画的网文作家。请对用户提供的段落进行扩写。\n要求：\n1. 增加环境氛围烘托、人物心理活动、细致的动作表情描写。\n2. 使画面更加丰满立体，字数增加 1.5 到 2 倍左右。\n3. 严格遵循原意，直接输出扩写后文本。`,
    editor_shorten: `你是一位行文干练的网文作者。请对用户提供的段落进行缩写（精简）。\n要求：\n1. 剔除啰嗦、冗余的修饰，加快叙事节奏。\n2. 提炼核心剧情、关键对话和核心动作。\n3. 字数大幅度精简，直接输出精简后文本。`,
    
    // 故事结构
    outline_expand: `你是一位金牌网文大纲拆解师。当前小说《{title}》。\n现在有一卷大纲，标题为“{volumeTitle}”，简介为“{volumeDesc}”。\n请将其裂变为 3 到 5 个具体的【章节细纲】。每一章需要有标题和剧情要点（字数控制在50字左右）。\n输出严格为 JSON 数组：\n[{"chapterNum": "章节编号(如: 第1章)", "title": "章节标题", "summary": "本章剧情要点"}]`,
    
    // 全局助理
    chat_assistant: `你是一位陪伴式 AI 写作教练。你非常了解网文创作的套路和技巧，语言幽默风趣。你现在正在辅助作者构思小说《{title}》（{tags}）。请根据作者的问题，给出有启发性的建议和点子。`,
    
    // 首页创作
    book_generate: `你是一位畅销网文策划编辑。请帮作者构思一本极具潜力的爆款新书。\n题材：{genre}\n目标读者：{audience}\n视角：{perspective}\n篇幅：{length}\n核心构思：{prompt}\n严格输出 JSON 格式：\n{"title": "书名", "tags": ["标签1", "标签2"], "wordCount": "0万", "status": "构思中", "desc": "一段极具吸引力的新书简介（约50字）"}`
  },
  generalSettings: { theme: 'light', autoSave: true, saveInterval: '2', particleEffects: true },
  works: []
}

// Extract only local settings to save
const extractLocalState = (state) => {
  return {
    llmConfigs: state.llmConfigs,
    schemaVersion: 7,
    agentAssignments: state.agentAssignments,
    prompts: state.prompts,
    generalSettings: state.generalSettings
  }
}

const savedState = localStorage.getItem(STORAGE_KEY)
let initialState = defaultState
if (savedState) {
  try {
    const parsed = JSON.parse(savedState)
    if (parsed && parsed.llmConfigs) {
      initialState.prompts = { ...initialState.prompts, ...parsed.prompts }
      initialState.generalSettings = { ...initialState.generalSettings, ...parsed.generalSettings }
      initialState.llmConfigs = parsed.llmConfigs
      if (parsed.agentAssignments) initialState.agentAssignments = parsed.agentAssignments
    }
  } catch (e) {
    console.warn("Error parsing local state", e)
  }
}

// Salvage from old v6 keys if needed
if (!initialState.llmConfigs || initialState.llmConfigs.every(c => !hasModelCredentials(c))) {
  for (let i = 0; i < localStorage.length; i++) {
    const k = localStorage.key(i);
    if (k && k.includes('ai-novel-platform-data')) {
      try {
        const data = JSON.parse(localStorage.getItem(k));
        if (data && data.llmConfigs && data.llmConfigs.some(c => hasModelCredentials(c))) {
          initialState.llmConfigs = data.llmConfigs;
          if (data.agentAssignments) initialState.agentAssignments = data.agentAssignments;
          console.log(`Successfully salvaged API keys from ${k}`);
          break;
        }
      } catch (e) {}
    }
  }
}

export const store = reactive(initialState)

watch(store, (newState) => {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(extractLocalState(newState))) }
  catch { saveState.error = '浏览器设置存储失败，请检查可用空间' }
}, { deep: true })

export const getAgentConfig = (agentName) => {
  const configId = store.agentAssignments[agentName]
  return store.llmConfigs.find(c => c.id === configId) || store.llmConfigs[0]
}

// Global active work data getter
export const activeWorkData = computed(() => {
  return store.works.find(w => w.id === store.activeWorkId) || store.works[0] || {}
})

// Save queues are independent per work; responses never replace newer edits.
export const saveState = reactive({ pending: 0, localPending: 0, error: '', connected: false, recovery: [] })
const known = new Map()
const pending = new Map()
let sequence = 0
const sessionId = globalThis.crypto?.randomUUID?.() || String(Date.now())
const json = data => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) })
const snapshot = work => JSON.stringify(work)

function updatePending() { saveState.pending = pending.size }

function schedule(work) {
  const id = work.id
  const entry = pending.get(id) || { running: null, timer: null }
  entry.snapshot = snapshot(work)
  entry.revision = `${sessionId}-${++sequence}`
  clearTimeout(entry.timer)
  pending.set(id, entry)
  updatePending()
  clearTimeout(entry.localTimer)
  entry.localTimer = setTimeout(() => { persistLocal(id, entry) }, 150)
  if (store.generalSettings.autoSave) {
    entry.timer = setTimeout(() => { flushWork(id).catch(() => {}) },
      Math.max(1, Number(store.generalSettings.saveInterval) || 2) * 1000)
  }
}

function persistLocal(id, entry) {
  clearTimeout(entry.localTimer)
  if (entry.localRevision === entry.revision) return entry.localWrite
  entry.localRevision = entry.revision
  saveState.localPending++
  entry.localWrite = saveDraft(id, entry.revision, entry.snapshot)
    .catch(() => { saveState.error = '本地草稿写入失败，请保持页面打开并手动保存' })
    .finally(() => { saveState.localPending-- })
  return entry.localWrite
}

export async function flushWork(id) {
  const entry = pending.get(id)
  if (!entry) return
  clearTimeout(entry.timer)
  if (entry.running) {
    await entry.running
    if (pending.has(id)) return flushWork(id)
    return
  }
  const revision = entry.revision
  const payload = entry.snapshot
  entry.running = (async () => {
    try {
      await persistLocal(id, entry)
      await apiFetch(`/works/${id}`, { ...json(JSON.parse(payload)), method: 'PUT' })
      await entry.localWrite
      await removeDraft(id, revision)
      if (entry.revision === revision) pending.delete(id)
      saveState.error = ''
    } catch (e) {
      saveState.error = `保存失败：${e.message}。未提交的内容保留在本地草稿中。`
      throw e
    } finally {
      entry.running = null
      updatePending()
    }
  })()
  await entry.running
  if (pending.has(id)) return flushWork(id)
}

export async function flushAll() {
  await Promise.all([...pending.keys()].map(flushWork))
}

export const backendAPI = {
  async fetchWorks() {
    await flushAll()
    const response = await apiFetch('/works')
    const remoteWorks = await response.json()
    // Edits made while the fetch was in flight must not be replaced by its response.
    const works = remoteWorks.map(work => pending.has(work.id) ? JSON.parse(pending.get(work.id).snapshot) : work)
    for (const current of store.works) {
      if (pending.has(current.id) && !works.some(w => w.id === current.id)) works.push(current)
    }
    for (const work of works) known.set(work.id, snapshot(work))
    store.works = works
    saveState.connected = true
    if (!works.some(w => w.id === store.activeWorkId)) store.activeWorkId = works[0]?.id || null
    saveState.recovery = (await loadDrafts()).filter(d => {
      const remote = works.find(w => w.id === d.id)
      return !remote || snapshot(remote) !== d.snapshot
    })
  },
  async getWork(id) { return (await apiFetch(`/works/${id}`)).json() },
  async createWork(workData) {
    const work = await (await apiFetch('/works', json(workData))).json()
    known.set(work.id, snapshot(work))
    store.works.unshift(work)
    return work
  },
  async updateWork(id, data) {
    return (await apiFetch(`/works/${id}`, { ...json(data), method: 'PUT' })).json()
  },
  async deleteWork(id) {
    const entry = pending.get(id)
    clearTimeout(entry?.timer)
    clearTimeout(entry?.localTimer)
    if (entry?.localWrite) await entry.localWrite
    if (entry?.running) await entry.running.catch(() => {})
    await apiFetch(`/works/${id}`, { method: 'DELETE' })
    pending.delete(id)
    known.delete(id)
    await removeDraft(id)
    store.works = store.works.filter(w => w.id !== id)
    if (store.activeWorkId === id) store.activeWorkId = store.works[0]?.id || null
    updatePending()
  },
  async restoreDraft(draft) {
    const data = JSON.parse(draft.snapshot)
    const index = store.works.findIndex(w => w.id === draft.id)
    if (index < 0) {
      delete data.id
      data.title += '（恢复副本）'
      await this.createWork(data)
      await removeDraft(draft.id)
    } else {
      store.works[index] = data
    }
    saveState.recovery = saveState.recovery.filter(d => d.id !== draft.id)
  },
  async discardDraft(draft) {
    await removeDraft(draft.id, draft.revision)
    saveState.recovery = saveState.recovery.filter(d => d.id !== draft.id)
  },
  async restoreRevision(id, revisionId) {
    await flushWork(id)
    const work = await (await apiFetch(`/works/${id}/revisions/${revisionId}/restore`, { method: 'POST' })).json()
    known.set(id, snapshot(work))
    const index = store.works.findIndex(w => w.id === id)
    if (index >= 0) store.works[index] = work
  }
}

watch(() => store.works, works => {
  for (const work of works) {
    const current = snapshot(work)
    if (known.get(work.id) !== current) {
      known.set(work.id, current)
      schedule(work)
    }
  }
}, { deep: true, flush: 'sync' })

watch(() => store.generalSettings.autoSave, enabled => { if (enabled) flushAll().catch(() => {}) })

watch(() => store.activeWorkId, (id, previous) => {
  if (previous != null) flushWork(previous).catch(() => {})
})

if (globalThis.window) {
  window.addEventListener('beforeunload', event => {
    if (pending.size || saveState.localPending) {
      event.preventDefault()
      event.returnValue = ''
    }
  })
  window.addEventListener('pagehide', () => { flushAll().catch(() => {}) })
}

export const secureFetch = apiFetch
