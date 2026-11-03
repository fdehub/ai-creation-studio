import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { ref, computed, watch, nextTick, reactive } from 'vue'
import { consumeOutline, readSSE } from '../src/sse.js'
import { apiFetch, setBackendToken, hasModelCredentials, modelAuthHeaders } from '../src/api.js'
import { listChatSessions, saveChatSession } from '../src/chat_sessions.js'
import { writingContext } from '../src/chat_context.js'
import { createWorkTasks } from '../src/work_tasks.js'
import { parseModelJSON, parseComicShots } from '../src/model_output.js'

const storage = new Map()
globalThis.localStorage = { getItem: key => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key), key: i => [...storage.keys()][i], get length() { return storage.size } }
setBackendToken('regression-placeholder')
const response = object => new Response(JSON.stringify(object), { headers: { 'Content-Type': 'application/json' } })
const wire = events => events.map(event => 'data: ' + (typeof event === 'string' ? event : JSON.stringify(event)) + '\n\n').join('')
function stream(text, split = 3) {
  const bytes = new TextEncoder().encode(text)
  return new Response(new ReadableStream({ start(controller) {
    for (let i = 0; i < bytes.length; i += split) controller.enqueue(bytes.slice(i, i + split))
    controller.close()
  } }))
}
function component(name, deps, expose) {
  const script = fs.readFileSync(new URL(`../src/components/${name}.vue`, import.meta.url), 'utf8')
    .split('</script>')[0].replace('<script setup>', '').replace(/^import .*$/gm, '')
  const defaults = { ref, computed, watch, nextTick, hasModelCredentials, modelAuthHeaders, listChatSessions, saveChatSession, writingContext, createWorkTasks, parseModelJSON, parseComicShots, onMounted: () => {}, onUnmounted: () => {},
    alert: () => {}, confirm: () => true, document: { querySelector: () => null } }
  const scope = { ...defaults, ...deps }
  return new Function(...Object.keys(scope), script + '\nreturn ' + expose)(...Object.values(scope))
}

test('SSE survives every UTF-8 byte boundary, CRLF, and multiple frames', async () => {
  const events = []
  await consumeOutline(stream(wire([{ step: '中文与😀' }, { chapters: [] }, { status: 'done' }]).replaceAll('\n', '\r\n'), 1), event => events.push(event))
  assert.equal(events[0].step, '中文与😀')
  assert.equal(events.length, 3)
  await consumeOutline(stream(wire([{ status: 'done' }]).replaceAll('\n', '\r'), 1), () => {})
})

test('SSE business errors and incomplete streams reject instead of reporting success', async () => {
  await assert.rejects(consumeOutline(stream(wire([{ error: 'upstream failure' }])), () => {}), /upstream failure/)
  await assert.rejects(consumeOutline(stream(wire([{ step: 'partial' }])), () => {}), /意外中断/)
  await assert.rejects(consumeOutline(stream('data: {"status":"do'), () => {}), /未完整结束/)
})

let storeModule
let works = new Map()
let writes = []
let failWrite = false
let pauseWrite = null
async function fetchMock(url, options = {}) {
  const path = new URL(url, 'http://localhost').pathname
  const method = options.method || 'GET'
  if (path === '/api/works' && method === 'GET') return response([...works.values()])
  if (path === '/api/works' && method === 'POST') {
    const work = { ...JSON.parse(options.body), id: works.size + 1 }
    works.set(work.id, structuredClone(work)); return response(work)
  }
  const id = Number(path.split('/').at(-1))
  if (method === 'PUT') {
    if (failWrite) return new Response('{"detail":"disk unavailable"}', { status: 503 })
    if (pauseWrite) { const wait = pauseWrite; pauseWrite = null; await wait }
    const work = JSON.parse(options.body)
    writes.push({ id, work: structuredClone(work) }); works.set(id, work)
    return response(work)
  }
  if (method === 'DELETE') { works.delete(id); return response({ ok: true }) }
  return response(works.get(id))
}

test('per-work saves survive switching, serialize concurrent edits, and report failures', async () => {
  globalThis.fetch = fetchMock
  storeModule = await import('../src/store.js')
  const { store, backendAPI, flushAll, flushWork, saveState } = storeModule
  store.generalSettings.autoSave = false
  const a = await backendAPI.createWork({ title: 'A', chapters: [] })
  const b = await backendAPI.createWork({ title: 'B', chapters: [] })
  store.activeWorkId = a.id
  store.works.find(w => w.id === a.id).title = 'A edited'
  store.activeWorkId = b.id
  store.works.find(w => w.id === b.id).title = 'B edited'
  await nextTick(); await flushAll()
  assert.equal(works.get(a.id).title, 'A edited')
  assert.equal(works.get(b.id).title, 'B edited')
  assert.equal(saveState.pending, 0)

  let release
  pauseWrite = new Promise(resolve => { release = resolve })
  const target = store.works.find(w => w.id === a.id)
  target.title = 'version one'
  const first = flushWork(a.id)
  await new Promise(resolve => setTimeout(resolve, 5))
  target.title = 'version two'
  const second = flushWork(a.id)
  release()
  await Promise.all([first, second])
  assert.equal(works.get(a.id).title, 'version two')
  assert.equal(saveState.pending, 0)

  failWrite = true
  target.title = 'unsaved important text'
  await assert.rejects(flushWork(a.id), /disk unavailable/)
  assert.match(saveState.error, /保存失败/)
  const { loadDrafts } = await import('../src/drafts.js')
  assert.ok((await loadDrafts()).some(d => JSON.parse(d.snapshot).title === 'unsaved important text'))
  failWrite = false
  await flushAll()
  assert.equal(works.get(a.id).title, 'unsaved important text')
  assert.equal((await loadDrafts()).length, 0)
})

test('custom prompts and settings survive a new store instance with defaults merged', async () => {
  storeModule.store.prompts.editor_polish = 'custom editing rules'
  storeModule.store.generalSettings.saveInterval = '10'
  await nextTick()
  const reloaded = await import('../src/store.js?reload-regression')
  assert.equal(reloaded.store.prompts.editor_polish, 'custom editing rules')
  assert.ok(reloaded.store.prompts.comic_generate_script)
  assert.equal(reloaded.store.generalSettings.saveInterval, '10')
})

test('homepage persists generated works with the database ID', async () => {
  const answers = [{ title: 'generated', tags: ['mock'], desc: 'synopsis' }, { name: 'A' }, { name: 'B' }, [], { title: 'plot' }, []]
  const store = { prompts: new Proxy({}, { get: () => '' }), works: [] }
  let created
  const run = component('HomePage', {
    store, getAgentConfig: () => ({ apiKey: 'placeholder' }),
    llmFetch: async () => response({ choices: [{ message: { content: JSON.stringify(answers.shift()) } }] }),
    backendAPI: { createWork: async data => { created = data; const saved = { ...data, id: 42 }; store.works.unshift(saved); return saved } }
  }, 'handleGenerate')
  await run()
  assert.equal(created.title, 'generated')
  assert.equal(store.activeWorkId, 42)
})

function editorFixture(fetcher) {
  const chapter = { id: 'c', content: 'abcdefghi' }
  const work = { id: 1, title: 'test', chapters: [{ id: 'v', chapters: [chapter] }] }
  const store = { works:[work], activeChapterId: 'c', activeWorkId: 1, pendingFixRange: null, pendingFixLabel: '', prompts: {} }
  const alerts = []
  const action = component('WritingEditor', { store, activeWorkData: computed(() => work),
    saveState: { pending: 0, error: '' }, flushWork: async () => {}, readSSE,
    getAgentConfig: () => ({ apiKey: 'placeholder' }), apiFetch: fetcher,
    document: { querySelector: () => ({ selectionStart: 2, selectionEnd: 5 }) },
    alert: message => alerts.push(message)
  }, 'handleAiAction')
  return { action, chapter, alerts }
}

test('polish never deletes original text on network failure or empty result', async () => {
  let fixture = editorFixture(async () => new Response(new ReadableStream({ start(controller) { controller.error(new Error('stream failed')) } })))
  await fixture.action('润色')
  assert.equal(fixture.chapter.content, 'abcdefghi')
  assert.ok(fixture.alerts.some(text => text.includes('stream failed')))
  fixture = editorFixture(async () => stream(wire(['[DONE]'])))
  await fixture.action('润色')
  assert.equal(fixture.chapter.content, 'abcdefghi')
})

test('polish commits the completed replacement in the selected range', async () => {
  const fixture = editorFixture(async () => stream(wire([{ choices: [{ delta: { content: 'NEW' } }] }, '[DONE]']), 1))
  await fixture.action('润色')
  assert.equal(fixture.chapter.content, 'abNEWfghi')
})

test('structure preview is non-destructive; applying preserves IDs, all text and extra chapters', async () => {
  const work = { id: 7, title: 'test', chapters: [{ id: 'volume', chapters: [
    { id: 'one', title: 'old', content: 'important text', comicShots: ['keep'] },
    { id: 'two', title: 'extra', content: 'also important' }
  ] }] }
  const store = { works: [work], activeWorkId:work.id }
  const ui = component('StoryStructure', { store, activeWorkData: computed(() => work),
    getAgentConfig: () => ({ apiKey: 'placeholder' }), flushWork: async () => {}, backendAPI: {},
    llmFetch: async () => response({ choices: [{ message: { content: JSON.stringify([{ title: 'new title', summary: 'new summary' }]) } }] })
  }, '{generateStructure, applyOutline, outlinePreview}')
  const before = JSON.stringify(work)
  await ui.generateStructure()
  assert.equal(JSON.stringify(work), before)
  assert.ok(ui.outlinePreview.value)
  await ui.applyOutline()
  assert.equal(work.chapters[0].id, 'volume')
  assert.equal(work.chapters[0].chapters[0].id, 'one')
  assert.equal(work.chapters[0].chapters[0].content, 'important text')
  assert.deepEqual(work.chapters[0].chapters[0].comicShots, ['keep'])
  assert.equal(work.chapters[0].chapters[1].content, 'also important')
  assert.equal(work.chapters[0].chapters[0].summary, 'new summary')
})

test('chat sends the configured prompt with the actual cited chapter and persists the reply', async () => {
  let sent
  const ui = component('AIChatAssistant', { store: { activeWorkId: 'chat-test', activeChapterId: 'chapter', prompts: { chat_assistant: 'help {title}' } },
    activeWorkData: computed(() => ({ id:'chat-test', title: 'test', tags: [], chapters:[{chapters:[{id:'chapter',title:'chapter one',content:'Actual chapter source'}]}] })), getAgentConfig: () => ({ apiKey: 'placeholder' }),
    llmFetch: async (url, options) => { sent = JSON.parse(options.body); return response({ choices: [{ message: { content: 'answer' } }] }) }
  }, '{inputMessage, sendMessage, messages}')
  ui.inputMessage.value = 'question'
  await ui.sendMessage()
  assert.ok(sent.messages[0].content.startsWith('help test'))
  assert.ok(sent.messages[0].content.includes('Actual chapter source'))
  assert.equal(ui.messages.value.at(-1).content, 'answer')
  assert.equal((await listChatSessions('chat-test'))[0].messages.at(-1).content, 'answer')
})

test('chat context names the selected source, rejects an absent previous chapter, and bounds long citations', () => {
  const work={chapters:[{chapters:[{id:'a',title:'First',content:'previous source'},{id:'b',title:'Second',content:'z'.repeat(30000)}]}],worldview:[{title:'World',items:[{name:'City',desc:'Real setting'}]}],characters:[{name:'A',description:'Actual character'}]}
  assert.equal(writingContext(work,'a','previous').available,false)
  assert.ok(writingContext(work,'b','previous').text.includes('previous source'))
  assert.equal(writingContext(work,'b','chapter').text.length,24000)
  assert.equal(writingContext(work,'b','chapter').truncated,true)
  assert.ok(writingContext(work,'b','world').text.includes('Real setting'))
  assert.ok(writingContext(work,'b','world').text.includes('Actual character'))
})

test('changing works cancels chat waiting and never attaches an old response to the new work', async () => {
  let finish
  const store=reactive({activeWorkId:'isolated-A',activeChapterId:'a',prompts:{chat_assistant:'help {title}'}})
  const work=computed(()=>({id:store.activeWorkId,title:store.activeWorkId,chapters:[{chapters:[{id:'a',title:'a',content:'source'}]}]}))
  const ui=component('AIChatAssistant',{store,activeWorkData:work,getAgentConfig:()=>({apiKey:'fixture'}),llmFetch:()=>new Promise(resolve=>{finish=resolve})},'{inputMessage,sendMessage,messages,isSending}')
  ui.inputMessage.value='old work question'
  const request=ui.sendMessage()
  for(let i=0;i<20&&!finish;i++) await new Promise(resolve=>setTimeout(resolve,0))
  assert.ok(finish)
  store.activeWorkId='isolated-B'
  await nextTick()
  finish(response({choices:[{message:{content:'Must not appear in B'}}]}))
  await request
  assert.ok(!ui.messages.value.some(m=>m.content==='Must not appear in B'))
  assert.equal((await listChatSessions('isolated-B')).length,0)
  const saved=await listChatSessions('isolated-A')
  assert.equal(saved[0].messages[0].content,'old work question')
  assert.equal(saved[0].messages.at(-1).role,'error')
})

test('editor applies chat replacements only when the selected original still matches', async () => {
  for (const stale of [false, true]) {
    const chapter = { id: 'c', content: 'abcdefghi' }
    const store = { activeWorkId: 1, activeChapterId: 'c', pendingFixRange: null, pendingFixLabel: '',
      pendingEditorAction: { workId: 1, chapterId: 'c', mode: 'replace', text: 'NEW',
        selection: { start: 2, end: 5, content: stale ? 'old version' : 'abcdefghi' } } }
    component('WritingEditor', { store, activeWorkData: computed(() => ({ id: 1, chapters: [{ chapters: [chapter] }] })),
      saveState: { pending: 0, error: '' }, flushWork: async () => {}, readSSE,
      getAgentConfig: () => ({ apiKey: 'placeholder' }), apiFetch: async () => {} }, '{}')
    await nextTick()
    assert.equal(chapter.content, stale ? 'abcdefghi' : 'abNEWfghi')
    assert.equal(store.pendingEditorAction, null)
  }
})

test('account model configuration uses only an account reference and survives migration', async () => {
  assert.equal(hasModelCredentials({ authType: 'account', accountId: 'account-fixture', apiKey: '' }), true)
  assert.deepEqual(modelAuthHeaders({ authType: 'account', accountId: 'account-fixture', apiKey: 'must-not-forward' }), { 'X-Novel-Account': 'account-fixture' })
  const storageKey = 'ai-novel-platform-data-v6'
  const previous = localStorage.getItem(storageKey)
  localStorage.setItem(storageKey, JSON.stringify({ llmConfigs: [{ id: 'linked', authType: 'account', accountId: 'account-fixture', apiKey: '' }] }))
  localStorage.setItem('ai-novel-platform-data-old-fixture', JSON.stringify({ llmConfigs: [{ id: 'legacy', apiKey: 'legacy-fixture-only' }] }))
  const loaded = await import('../src/store.js?account-migration-fixture')
  assert.equal(loaded.store.llmConfigs[0].accountId, 'account-fixture')
  localStorage.setItem(storageKey, previous)
  localStorage.removeItem('ai-novel-platform-data-old-fixture')
})

test('provider authorization errors do not reset the application session', async () => {
  const previousFetch = globalThis.fetch
  let count = 0
  globalThis.fetch = async () => { count++; return new Response('{"detail":"provider authorization required"}', { status: 401 }) }
  try { await assert.rejects(apiFetch('/proxy/chat'), /provider authorization required/); assert.equal(count, 1) }
  finally { globalThis.fetch = previousFetch }
})

function workFixture() {
  const make = id => ({id,title:id,tags:[],characters:[],plotNodes:[],worldview:[],terms:[],timeline:[],rules:[],
    chapters:[{chapters:[{id:id+'-chapter',content:'章节正文'}]}]})
  const store = reactive({works:[make('A'),make('B')],activeWorkId:'A',prompts:new Proxy({},{get:()=>''})})
  return {store,activeWorkData:computed(()=>store.works.find(w=>w.id===store.activeWorkId))}
}

test('model output rejects null, malformed fields and invalid comic shots', () => {
  for (const value of ['null','[]','{"name":{}}','{"tags":"invalid"}','{"states":[null]}','{"states":[{"chapterRange":"bad"}]}','{"items":[null]}']) assert.throws(()=>parseModelJSON(value))
  for (const value of ['[null]','["bad"]','{}']) assert.throws(()=>parseModelJSON(value,'array'))
  for (const value of ['[]','[{"desc":"x"}]','[{"desc":"x","prompt":"","dialogue":null}]']) assert.throws(()=>parseComicShots(value))
  assert.equal(parseComicShots('```json\n[{"desc":"画面","prompt":"prompt"}]\n```').length,1)
})

for (const [name,action,answer] of [
  ['PlotEngine','generateTwist',{title:'late twist',desc:'late'}],
  ['CharacterWorkshop','generateCharacter',{name:'late character'}],
  ['CharacterWorkshop','scanPastCharacters',[{name:'late character'}]],
  ['WorldviewConstruction','autoConstructCategory',[{name:'late item',desc:'late'}]]
]) test(`${name}.${action} ignores late responses after switching works, even if transport ignores abort`, async () => {
  const fixture=workFixture()
  let finish,signal
  const before=JSON.stringify(fixture.store.works)
  const ui=component(name,{...fixture,getAgentConfig:()=>({apiKey:'fixture'}),flushWork:async()=>{},
    apiFetch:(_url,options)=>{signal=options.signal;return new Promise(resolve=>{finish=resolve})}},
    action==='autoConstructCategory'?'{run:autoConstructCategory,newCategoryName}':`{run:${action}}`)
  if(ui.newCategoryName) ui.newCategoryName.value='category'
  const pending=ui.run()
  assert.ok(finish,'request must have started')
  fixture.store.activeWorkId='B'
  await nextTick()
  assert.equal(signal.aborted,true)
  finish(response({choices:[{message:{content:JSON.stringify(answer)}}]}))
  await pending
  assert.equal(JSON.stringify(fixture.store.works),before)
})

test('comic batch stops after the in-flight request and never writes after cancellation', async () => {
  const fixture=workFixture()
  fixture.activeWorkData.value.chapters[0].chapters.push({id:'another',content:'more text'})
  let finish,calls=0
  const ui=component('ComicStudio',{...fixture,getAgentConfig:()=>({apiKey:'fixture'}),
    apiFetch:()=>{calls++;return new Promise(resolve=>{finish=resolve})}},'{generateBatchComicScript,stopBatchGeneration}')
  const pending=ui.generateBatchComicScript()
  ui.stopBatchGeneration()
  finish(response({choices:[{message:{content:'[{"desc":"scene","prompt":"draw"}]'}}]}))
  await pending
  assert.equal(calls,1)
  assert.ok(fixture.activeWorkData.value.chapters[0].chapters.every(c=>!c.comicShots))
})

test('character deletion flushes the captured work and removes only the selected character', async () => {
  const fixture=workFixture()
  fixture.activeWorkData.value.characters=[{id:1,name:'first'},{id:2,name:'second'}]
  const saved=[]
  const remove=component('CharacterWorkshop',{...fixture,flushWork:async id=>saved.push(id)},'deleteCharacter')
  await remove(1)
  assert.deepEqual(saved,['A'])
  assert.equal(fixture.activeWorkData.value.characters[0].name,'second')
})

test('regenerating an outline preserves edits made while the model is waiting', async () => {
  const fixture=workFixture()
  fixture.activeWorkData.value.chapters[0].chapters[0].content=''
  let finish
  const ui=component('MyWorks',{store:fixture.store,getAgentConfig:()=>({apiKey:'fixture'}),consumeOutline,
    flushWork:async()=>{},apiFetch:()=>new Promise(resolve=>{finish=resolve})},'{regenerateWork}')
  const pending=ui.regenerateWork('A')
  fixture.activeWorkData.value.chapters[0].chapters[0].content='new important manuscript'
  finish(stream(wire([{chapters:[{chapters:[{id:'replacement',content:''}]}]},{status:'done',plot:{},worldview:{}}])))
  await pending
  assert.equal(fixture.activeWorkData.value.chapters[0].chapters[0].content,'new important manuscript')
})

test('failed work creation never marks an unrelated work interrupted', async () => {
  const fixture=workFixture()
  const ui=component('MyWorks',{store:fixture.store,backendAPI:{createWork:async()=>{throw new Error('mock disk unavailable')}},
    getAgentConfig:()=>({apiKey:'fixture'})},'{handleCreate,newWork}')
  ui.newWork.value.title='new work'
  const before=JSON.stringify(fixture.store.works)
  await ui.handleCreate()
  assert.equal(JSON.stringify(fixture.store.works),before)
})

test('work creation without model configuration creates a usable blank draft', async () => {
  const fixture=workFixture()
  let requests=0
  const ui=component('MyWorks',{store:fixture.store,getAgentConfig:()=>({}),apiFetch:async()=>{requests++},
    backendAPI:{createWork:async data=>{const work={...data,id:'new'};fixture.store.works.push(work);return work}}},'{handleCreate,newWork}')
  ui.newWork.value.title='blank draft'
  await ui.handleCreate()
  assert.equal(requests,0)
  assert.equal(fixture.store.activeWorkId,'new')
  assert.equal(fixture.store.activeMenuItem,'写作编辑器')
  assert.equal(fixture.activeWorkData.value.status,'草稿')
})

test('worldview rules are stored on the work rather than a temporary computed category', async () => {
  const fixture=workFixture()
  delete fixture.activeWorkData.value.rules
  const ui=component('WorldviewConstruction',{...fixture},'{activeTab,addCategory,editForm,confirmEditItem}')
  ui.activeTab.value='最高法则'
  await nextTick()
  ui.addCategory()
  ui.editForm.value.name='persistent rule'
  ui.confirmEditItem()
  assert.equal(fixture.activeWorkData.value.rules[0].name,'persistent rule')
})

test('changing worldview tabs cancels generation instead of writing into the new category', async () => {
  const fixture=workFixture()
  let finish
  const ui=component('WorldviewConstruction',{...fixture,getAgentConfig:()=>({apiKey:'fixture'}),
    apiFetch:()=>new Promise(resolve=>{finish=resolve})},'{autoConstructCategory,activeTab}')
  const pending=ui.autoConstructCategory()
  ui.activeTab.value='术语'
  await nextTick()
  finish(response({choices:[{message:{content:'[{"name":"late","desc":"late"}]'}}]}))
  await pending
  assert.equal(fixture.activeWorkData.value.worldview.length,0)
  assert.equal(fixture.activeWorkData.value.terms.length,0)
})

test('outline resume preserves concurrent manuscript edits', async () => {
  const fixture=workFixture()
  let finish
  const run=component('MyWorks',{store:fixture.store,getAgentConfig:()=>({apiKey:'fixture'}),consumeOutline,
    flushWork:async()=>{},apiFetch:()=>new Promise(resolve=>{finish=resolve})},'resumeWork')
  const pending=run('A')
  fixture.activeWorkData.value.chapters[0].chapters[0].content='edited during resume'
  finish(stream(wire([{chapters:[{chapters:[{id:'new',content:''}]}]},{status:'done'}])))
  await pending
  assert.equal(fixture.activeWorkData.value.chapters[0].chapters[0].content,'edited during resume')
  assert.equal(fixture.activeWorkData.value.chapters[0].chapters.length,1)
})
