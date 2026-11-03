<script setup>
import { computed, ref, watch, nextTick, onUnmounted } from 'vue'
import { llmFetch, hasModelCredentials, modelAuthHeaders } from '../api.js'
import { store, getAgentConfig, activeWorkData } from '../store.js'
import { listChatSessions, saveChatSession } from '../chat_sessions.js'
import { writingContext } from '../chat_context.js'
import UiIcon from './UiIcon.vue'

const sessions = ref([])
const currentChat = ref(null)
const messages = computed(() => currentChat.value?.messages || [])
const inputMessage = ref('')
const messagesContainer = ref(null)
const loading = ref(false)
const isSending = ref(false)
const error = ref('')
const storageError = ref('')
const notice = ref('')
const historyOpen = ref(false)
const contextMode = ref('chapter')
const contextChapterId = ref(null)
const chapters = computed(() => (activeWorkData.value.chapters || []).flatMap(v => v.chapters || []))
const context = computed(() => writingContext(activeWorkData.value, contextChapterId.value, contextMode.value))
const history = computed(() => sessions.value.filter(s => s.messages.length).sort((a, b) => b.updatedAt - a.updatedAt))
const validSelection = computed(() => {
  const selection = store.editorSelection
  const chapter = chapters.value.find(c => c.id === selection?.chapterId)
  return selection && selection.workId === store.activeWorkId && chapter && selection.content === (chapter.content || '').replace(/\r\n/g, '\n') ? selection : null
})
const targetChapter = computed(() => chapters.value.find(c => c.id === store.activeChapterId) || chapters.value.find(c => c.id === contextChapterId.value) || chapters.value[0])
const canReplace = computed(() => validSelection.value && validSelection.value.chapterId === targetChapter.value?.id && validSelection.value.end > validSelection.value.start)
let controller, requestVersion = 0, loadVersion = 0, loadPromise = Promise.resolve(), draftTimer

const scrollToBottom = async () => { await nextTick(); if (messagesContainer.value) messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight }
async function persist(chat) {
  if (!chat) return
  chat.updatedAt = Date.now()
  try { await saveChatSession(chat); if (String(chat.workId) === String(store.activeWorkId)) storageError.value = ''; return true }
  catch { if (String(chat.workId) === String(store.activeWorkId)) storageError.value = '对话尚未保存，请重试或复制保留内容。'; return false }
}
function stopRequest() {
  controller?.abort()
  controller = null
  requestVersion++
  isSending.value = false
}
async function loadSessions(workId) {
  const version = ++loadVersion
  clearTimeout(draftTimer)
  stopRequest(); loading.value = true; currentChat.value = null; sessions.value = []; inputMessage.value = ''; error.value = ''
  contextChapterId.value = chapters.value.some(c => c.id === store.activeChapterId) ? store.activeChapterId : chapters.value[0]?.id
  try {
    const records = await listChatSessions(workId)
    if (version !== loadVersion) return
    sessions.value = records
    currentChat.value = records[0] || null
    inputMessage.value = currentChat.value?.draft || ''
    storageError.value = ''
  } catch { if (version === loadVersion) storageError.value = '无法读取本机对话记录，请检查浏览器存储权限。' }
  finally { if (version === loadVersion) { loading.value = false; scrollToBottom() } }
}
function newChat() {
  if (currentChat.value) { currentChat.value.draft = inputMessage.value; persist(currentChat.value) }
  stopRequest(); currentChat.value = null; inputMessage.value = ''; error.value = ''; notice.value = ''; historyOpen.value = false
}
function selectChat(chat) {
  if (currentChat.value) { currentChat.value.draft = inputMessage.value; persist(currentChat.value) }
  stopRequest(); currentChat.value = chat; inputMessage.value = chat.draft || ''; error.value = ''; historyOpen.value = false; scrollToBottom()
}
async function sendMessage() {
  if (isSending.value || !inputMessage.value.trim()) return
  const userText = inputMessage.value.trim()
  const requestedWork = String(store.activeWorkId)
  await loadPromise
  if (isSending.value || loading.value || String(store.activeWorkId) !== requestedWork) return
  const config = getAgentConfig('EditorAgent')
  if (!hasModelCredentials(config)) { error.value = '请先在设置中连接账号或配置模型。'; return }
  const work = activeWorkData.value
  const citation = writingContext(work, contextChapterId.value, contextMode.value)
  if (!citation.available) { error.value = citation.label; return }
  if (!currentChat.value) {
    currentChat.value = { id: crypto.randomUUID(), workId: String(store.activeWorkId), title: userText.slice(0, 24), createdAt: Date.now(), updatedAt: Date.now(), messages: [], draft: '' }
    sessions.value.unshift(currentChat.value)
  }
  const chat = currentChat.value
  const question = { id: crypto.randomUUID(), role: 'user', content: userText, citation: citation.label, failed: false }
  chat.messages.push(question); chat.draft = ''
  isSending.value = true; error.value = ''; notice.value = ''
  const version = ++requestVersion
  const abort = new AbortController(); controller = abort
  if (!await persist(chat)) { chat.messages.pop(); if (version === requestVersion) isSending.value = false; return }
  if (version !== requestVersion || abort.signal.aborted) { question.failed = true; await persist(chat); return }
  if (inputMessage.value.trim() === userText) inputMessage.value = ''
  scrollToBottom()
  const timeout = setTimeout(() => abort.abort(), 250000)
  try {
    const prompt = store.prompts.chat_assistant.replace(/{title}/g, work.title || '未命名作品').replace(/{tags}/g, (work.tags || []).join('/'))
    const system = prompt + (citation.text ? '\n\n【用户明确引用的作品资料】\n' + citation.text + '\n【引用资料结束】\n请根据上述实际资料回答；没有资料的部分不要声称已阅读。' : '\n用户未引用正文，请勿声称已阅读章节或设定。')
    const body = { model: config.modelName || 'gpt-4o-mini', messages: [{ role: 'system', content: system }, ...chat.messages.filter(m => m.role !== 'error' && !m.failed).slice(-8).map(m => ({ role: m.role === 'ai' ? 'assistant' : 'user', content: m.content }))] }
    const baseUrl = (config.baseUrl || 'https://api.openai.com/v1').replace(/\/+$/, '')
    const response = await llmFetch(baseUrl + '/chat/completions', { method: 'POST', signal: abort.signal, headers: { 'Content-Type': 'application/json', ...modelAuthHeaders(config) }, body: JSON.stringify(body) })
    if (!response.ok) throw new Error(`模型请求失败：${response.status}`)
    const result = await response.json()
    if (abort.signal.aborted) throw new Error('已停止等待')
    const content = result.choices?.[0]?.message?.content
    if (typeof content !== 'string' || !content.trim()) throw new Error('模型没有返回有效正文，请重试')
    chat.messages.push({ id: crypto.randomUUID(), role: 'ai', content })
  } catch (e) {
    question.failed = true
    chat.messages.push({ id: crypto.randomUUID(), role: 'error', content: abort.signal.aborted ? '已停止等待回复。平台可能仍在处理这次请求。' : e.message, retryText: userText })
  } finally {
    clearTimeout(timeout)
    await persist(chat)
    if (version === requestVersion) { isSending.value = false; controller = null; scrollToBottom() }
  }
}
function handleKeydown(event) {
  if (event.key !== 'Enter' || event.shiftKey || event.isComposing || event.keyCode === 229) return
  event.preventDefault(); sendMessage()
}
function sendShortcut(text, mode = 'chapter') { contextMode.value = mode; inputMessage.value = text; error.value = '' }
function sendToEditor(text, mode) {
  const chapter = targetChapter.value
  if (!chapter || (mode === 'replace' && !canReplace.value)) return
  const selection = validSelection.value?.chapterId === chapter.id ? { ...validSelection.value } : null
  store.activeChapterId = chapter.id
  store.pendingEditorAction = { text, mode, workId: store.activeWorkId, chapterId: chapter.id, selection }
  store.activeMenuItem = '写作编辑器'
}
const insertToEditor = text => sendToEditor(text, 'insert')
const replaceInEditor = text => sendToEditor(text, 'replace')
async function copyMessage(text) { try { await navigator.clipboard.writeText(text); notice.value = '已复制'; } catch { error.value = '复制未完成，请选中文字手动复制。' } }
watch(() => store.activeWorkId, workId => { loadPromise = loadSessions(workId) }, { immediate: true })
watch(chapters, list => { if (!list.some(c => c.id === contextChapterId.value)) contextChapterId.value = list.some(c => c.id === store.activeChapterId) ? store.activeChapterId : list[0]?.id }, { immediate: true })
watch(inputMessage, () => { clearTimeout(draftTimer); draftTimer = setTimeout(() => { if (currentChat.value) { currentChat.value.draft = inputMessage.value; persist(currentChat.value) } }, 400) })
watch(messages, scrollToBottom, { deep: true })
onUnmounted(() => { loadVersion++; clearTimeout(draftTimer); if (currentChat.value) { currentChat.value.draft = inputMessage.value; persist(currentChat.value) }; stopRequest() })
</script>

<template>
  <div class="chat-workspace" :class="{ 'has-history': history.length, 'history-open': historyOpen }">
    <button v-if="historyOpen" class="chat-history-scrim" aria-label="关闭对话列表" @click="historyOpen = false"></button>
    <aside v-if="history.length" class="conversation-rail" aria-label="当前作品的对话记录">
      <div class="conversation-heading"><span>对话记录</span><button aria-label="新建对话" @click="newChat"><UiIcon name="plus" :size="18" /></button></div>
      <button v-for="chat in history" :key="chat.id" class="conversation-row" :class="{selected:chat.id === currentChat?.id}" :aria-pressed="chat.id === currentChat?.id" @click="selectChat(chat)"><UiIcon name="chat" :size="16" /><span>{{ chat.title }}</span></button>
      <p class="conversation-note">按作品分开，保存在当前浏览器。</p>
    </aside>
    <section class="conversation-main">
      <div class="conversation-toolbar"><div><button v-if="history.length" class="history-toggle" @click="historyOpen = !historyOpen" aria-label="查看对话记录"><UiIcon name="chat" :size="17" /></button><span class="chat-scope"><UiIcon name="book" :size="14" />{{ activeWorkData.title }}</span></div><button class="chat-new-button" @click="newChat"><UiIcon name="plus" :size="15" />新对话</button></div>
      <div v-if="loading" class="chat-loading" role="status">正在读取本机对话…</div>
      <div v-else-if="!messages.length" class="chat-empty">
        <span class="chat-empty-mark"><UiIcon name="spark" :size="26" /></span>
        <h2>让灵感，再往前一步</h2><p>讨论角色，打磨段落，或为下一场戏找到切入点。</p>
        <div class="chat-suggestions"><button @click="sendShortcut('请检查这章的错别字与不通顺的句子，逐项给出修改建议。')"><UiIcon name="pen" :size="19" /><strong>打磨一个章节</strong><span>从措辞到叙述，找到可改进的地方</span></button><button @click="sendShortcut('请根据引用的人物与世界观，梳理角色动机和潜在冲突。','world')"><UiIcon name="users" :size="19" /><strong>梳理人物关系</strong><span>让动机与冲突更清晰</span></button><button @click="sendShortcut('请把这章拆成三到五个关键场景，概括画面、台词和情绪变化。')"><UiIcon name="film" :size="19" /><strong>构思改编场景</strong><span>从小说文字，走向镜头表达</span></button></div>
      </div>
      <div v-else class="conversation-messages" ref="messagesContainer" aria-live="polite" aria-relevant="additions">
        <article v-for="msg in messages" :key="msg.id" class="chat-message" :class="msg.role"><div class="chat-speaker">{{ msg.role === 'user' ? '你' : msg.role === 'error' ? '请求提示' : '创作助手' }}</div><div class="chat-message-body">{{ msg.content }}</div><small v-if="msg.citation" class="chat-citation">引用：{{ msg.citation }}</small><div v-if="msg.role === 'ai'" class="chat-message-actions"><button @click="copyMessage(msg.content)">复制</button><button :disabled="!targetChapter" @click="insertToEditor(msg.content)">{{ validSelection?.chapterId === targetChapter?.id ? '插入光标处' : '插入章节末尾' }}</button><button :disabled="!canReplace" :title="canReplace ? '替换编辑器中选中的正文' : '请先在编辑器中选中正文'" @click="replaceInEditor(msg.content)">替换选中</button><span v-if="targetChapter" :title="targetChapter.title">目标：{{ targetChapter.title }}</span></div><button v-if="msg.role === 'error'" class="chat-retry" @click="inputMessage = msg.retryText">重新编辑问题 <UiIcon name="arrow" :size="13" /></button></article>
        <div v-if="isSending" class="chat-thinking" role="status"><span></span>正在构思回复，平台繁忙时可能需要较长时间…</div>
      </div>
      <div class="chat-composer-area">
        <div v-if="error || storageError" class="chat-alert" role="alert">{{ storageError || error }}<button v-if="storageError" @click="currentChat ? persist(currentChat) : loadSessions(store.activeWorkId)">重试保存/读取</button><button v-else-if="error.includes('设置')" @click="store.activeMenuItem = '策略与设置'">前往设置</button></div>
        <div class="chat-reference"><span>引用资料</span><select v-model="contextMode" aria-label="引用资料范围" :disabled="isSending"><option value="chapter">所选章节</option><option value="previous">所选章节的上一章</option><option value="world">人物与世界观</option><option value="none">不引用正文</option></select><select v-if="['chapter','previous'].includes(contextMode)" v-model="contextChapterId" aria-label="引用章节" :disabled="isSending"><option v-if="!chapters.length" :value="null">暂无章节</option><option v-for="chapter in chapters" :key="chapter.id" :value="chapter.id">{{ chapter.title }}</option></select></div>
        <div class="chat-composer"><textarea v-model="inputMessage" aria-label="创作问题" placeholder="写下你的问题，或选择上方的创作建议…" @keydown="handleKeydown" :disabled="loading"></textarea><div class="chat-composer-bottom"><span>{{ context.available ? (context.length ? `已引用 ${context.length.toLocaleString()} 字${context.truncated ? '（已截取）' : ''}` : '本次不引用作品正文') : context.label }}</span><button v-if="isSending" class="chat-submit" @click="stopRequest">停止等待</button><button v-else class="chat-submit" aria-label="发送消息" :disabled="!inputMessage.trim() || loading || !context.available" @click="sendMessage">发送 <UiIcon name="arrow" :size="15" /></button></div></div>
        <div class="chat-composer-hint"><span>Enter 发送 · Shift + Enter 换行</span><span role="status">{{ storageError ? '本机保存异常' : notice || '对话保存在当前浏览器' }}</span></div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.chat-workspace{width:100%;height:100%;min-height:0;min-width:0;display:flex;background:var(--panel-bg);position:relative}
.conversation-rail{width:218px;flex:0 0 218px;background:var(--surface-subtle);border-right:1px solid var(--border-color);padding:22px 14px;display:flex;flex-direction:column;gap:5px;overflow:auto}
.conversation-heading{display:flex;justify-content:space-between;align-items:center;padding:0 9px 16px;font-size:12px;color:var(--text-secondary)}
.conversation-heading button,.history-toggle{display:inline-flex;align-items:center;justify-content:center;border:0;background:transparent;color:var(--text-secondary);padding:5px;border-radius:5px}
.conversation-row{display:flex;align-items:center;gap:9px;text-align:left;padding:11px 10px;border:0;background:transparent;border-radius:6px;color:var(--text-secondary);min-width:0;font-size:12px}
.conversation-row>span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.conversation-row:hover,.conversation-row.selected{background:var(--panel-bg);color:var(--text-primary)}
.conversation-note{font-size:10px;line-height:1.8;color:var(--text-category);margin:auto 9px 0;padding-top:25px}
.conversation-main{flex:1;min-width:0;min-height:0;display:flex;flex-direction:column}
.conversation-toolbar{min-height:51px;display:flex;align-items:center;justify-content:space-between;padding:12px 28px;gap:12px;border-bottom:1px solid var(--border-color)}
.conversation-toolbar>div{min-width:0;display:flex;align-items:center;gap:8px}
.chat-scope{display:flex;align-items:center;gap:7px;color:var(--text-secondary);font-size:11px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.chat-new-button{display:flex;align-items:center;gap:5px;border:0;background:transparent;color:var(--text-secondary);font-size:11px;white-space:nowrap;padding:4px}
.history-toggle{display:none}
.chat-empty{flex:1;min-height:0;overflow:auto;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:35px 28px 20px;text-align:center}
.chat-empty-mark{display:flex;align-items:center;justify-content:center;background:var(--accent-bg);color:var(--accent-color);border-radius:14px;width:53px;height:53px;margin-bottom:21px}
.chat-empty h2{font-size:27px;letter-spacing:.3px;font-weight:600;margin:0 0 12px;color:var(--text-primary)}
.chat-empty>p{font-size:13px;color:var(--text-secondary);margin:0 0 28px;line-height:1.8}
.chat-suggestions{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;max-width:750px;width:100%}
.chat-suggestions button{display:flex;align-items:flex-start;flex-direction:column;text-align:left;padding:18px;border:1px solid var(--border-color);background:var(--panel-bg);color:var(--text-primary);border-radius:8px;gap:11px;min-width:0}
.chat-suggestions button:hover{border-color:var(--accent-border);background:var(--accent-bg)}
.chat-suggestions svg{color:var(--accent-color)}
.chat-suggestions strong{font-size:13px;font-weight:500}
.chat-suggestions span{font-size:11px;color:var(--text-secondary);line-height:1.6}
.conversation-messages{flex:1;min-height:0;overflow:auto;padding:27px max(25px,calc((100% - 740px)/2));display:flex;flex-direction:column;gap:27px}
.chat-message{font-size:14px;line-height:1.9;min-width:0}
.chat-speaker{font-size:11px;color:var(--text-category);margin-bottom:8px}
.chat-message-body{white-space:pre-wrap;overflow-wrap:anywhere}
.chat-message.user{background:var(--surface-subtle);padding:13px 17px;border-radius:8px;margin-left:35px}
.chat-message.error{border-left:2px solid var(--accent-border);padding-left:15px;color:var(--text-secondary)}
.chat-citation{font-size:10px;color:var(--text-category);display:block;margin-top:7px}
.chat-message-actions{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin-top:12px;font-size:11px}
.chat-message-actions button,.chat-retry{border:0;background:transparent;color:var(--text-secondary);font-size:11px;padding:3px 0}
.chat-message-actions button:hover,.chat-retry:hover{color:var(--accent-color)}
.chat-message-actions span{color:var(--text-category);max-width:220px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;font-size:10px}
.chat-retry{display:flex;align-items:center;gap:6px;margin-top:9px}
.chat-thinking{font-size:12px;color:var(--text-secondary);display:flex;align-items:center;gap:8px;line-height:1.8}
.chat-thinking>span{width:7px;height:7px;flex-shrink:0;border-radius:50%;background:var(--accent-color);animation:thinking 1.2s ease-in-out infinite}
.chat-composer-area{width:100%;max-width:800px;margin:0 auto;padding:15px 28px 20px;flex-shrink:0}
.chat-reference{display:flex;align-items:center;gap:8px;margin-bottom:10px;flex-wrap:wrap;font-size:11px;color:var(--text-category)}
.chat-reference select{min-width:0;max-width:230px;padding:5px 8px;border:1px solid var(--border-color);border-radius:4px;background:var(--panel-bg);font-size:11px;color:var(--text-secondary)}
.chat-composer{border:1px solid var(--border-color);background:var(--panel-bg);border-radius:10px;padding:13px 15px;box-shadow:0 3px 14px #20253005}
.chat-composer:focus-within{border-color:var(--accent-border);box-shadow:0 0 0 3px var(--accent-bg)}
.chat-composer textarea{display:block;resize:none;width:100%;height:66px;border:0;background:transparent;color:var(--text-primary);font:13px/1.8 var(--font-family);padding:0;outline:none}
.chat-composer-bottom{display:flex;align-items:center;justify-content:space-between;gap:10px}
.chat-composer-bottom>span{font-size:10px;color:var(--text-category);min-width:0}
.chat-submit{display:inline-flex;align-items:center;gap:7px;background:var(--accent-color);color:var(--accent-foreground);border:0;border-radius:6px;padding:8px 13px;font-size:12px;white-space:nowrap}
.chat-composer-hint{display:flex;justify-content:space-between;gap:10px;font-size:10px;color:var(--text-category);margin-top:9px}
.chat-alert{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;color:var(--accent-color);background:var(--accent-bg);padding:10px 12px;border-radius:6px;font-size:12px;margin-bottom:12px}
.chat-alert button{border:0;background:transparent;color:inherit;text-decoration:underline}
.chat-loading{flex:1;display:grid;place-content:center;color:var(--text-secondary);font-size:13px}
.chat-history-scrim{display:none}
@keyframes thinking{50%{opacity:.35}}
@media(max-width:1000px){.conversation-rail{width:180px;flex-basis:180px}.chat-empty{padding:25px 22px}.chat-empty h2{font-size:24px}.chat-suggestions{gap:8px}.chat-suggestions button{padding:14px}.conversation-toolbar{padding:12px 22px}}
@media(max-width:800px){.conversation-rail{display:none}.history-toggle{display:inline-flex}.history-open .conversation-rail{display:flex;position:absolute;inset:0 auto 0 0;z-index:5;width:230px;box-shadow:var(--shadow-lg)}.history-open .chat-history-scrim{display:block;position:absolute;inset:0;background:#0006;border:0;z-index:4}.chat-empty h2{font-size:23px}.chat-composer-area{padding:12px 20px 16px}}
@media(max-width:550px){.chat-empty{justify-content:flex-start;padding:28px 18px 18px}.chat-empty-mark{width:43px;height:43px;margin-bottom:14px}.chat-empty h2{font-size:20px}.chat-empty>p{font-size:12px;margin-bottom:19px}.chat-suggestions{grid-template-columns:1fr;gap:7px}.chat-suggestions button{padding:12px;display:grid;grid-template-columns:20px 1fr;gap:5px 10px}.chat-suggestions svg{grid-row:1/3}.chat-suggestions span{grid-column:2}.chat-suggestions strong{font-size:12px}.conversation-toolbar{padding:10px 16px}.chat-composer-area{padding:10px 14px 13px}.chat-composer-hint{font-size:9px}.chat-composer-hint>span:first-child{display:none}.chat-reference select{max-width:100%;flex:1}.chat-reference>span{width:100%}.conversation-messages{padding:20px 17px}.chat-message.user{margin-left:15px}}
@media(prefers-reduced-motion:reduce){.chat-thinking>span{animation:none}}
</style>
