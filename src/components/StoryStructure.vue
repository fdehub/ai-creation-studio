<script setup>
import UiIcon from './UiIcon.vue'
import { llmFetch, hasModelCredentials, modelAuthHeaders } from '../api.js'
import { ref, computed, watch, onUnmounted } from 'vue'
import { store, getAgentConfig, activeWorkData, backendAPI, flushWork } from '../store.js'
import { createWorkTasks } from '../work_tasks.js'
import { parseModelJSON } from '../model_output.js'
const tasks = createWorkTasks(store, activeWorkData)
watch(() => store.activeWorkId, () => { tasks.cancelAll(); outlinePreview.value = null })
onUnmounted(() => tasks.dispose())

const isGenerating = ref(false)
const selectedBeatSheet = ref('waste')

const outlinePreview = ref(null)
const generateStructure = async () => {
  if (isGenerating.value) return
  const work = activeWorkData.value
  const config = getAgentConfig('EditorAgent')
  if (!hasModelCredentials(config)) return alert('请先配置 AI 模型')
  isGenerating.value = true
  const task = tasks.begin()
  try {
    task.assertCurrent()
    await flushWork(work.id)
    const source = JSON.stringify(work.chapters || [])
    const beat = { default: '三幕剧', waste: '成长逆袭与黄金三章', infinite: '无限流副本循环', system: '系统日常流' }[selectedBeatSheet.value]
    const response = await llmFetch(`${(config.baseUrl || 'https://api.openai.com/v1').replace(/\/+$/, '')}/chat/completions`, {
      signal: task.signal,
      method: 'POST', headers: { 'Content-Type': 'application/json', ...modelAuthHeaders(config) },
      body: JSON.stringify({ model: config.modelName || 'gpt-3.5-turbo', messages: [{ role: 'user', content:
        `为小说《${work.title}》规划${beat}章节节拍。简介：${work.synopsis || ''}。现有结构：${source}。只返回 JSON 数组，每项含 title 与 summary。保持已有剧情顺序，最多生成20章，不输出正文。` }] })
    })
    const result = await response.json()
    const raw = result.choices?.[0]?.message?.content || ''
    const suggestions = parseModelJSON(raw, 'array')
    if (!Array.isArray(suggestions) || !suggestions.length || suggestions.length > 100 || suggestions.some(ch => typeof ch.title !== 'string' || typeof ch.summary !== 'string')) throw new Error('模型返回的大纲格式无效')
    task.assertCurrent()
    outlinePreview.value = { workId: work.id, source, suggestions }
  } catch (e) { if (!task.cancelled) alert(`结构生成失败：${e.message}`) }
  finally { task.finish(); isGenerating.value = false }
}

const applyOutline = async () => {
  const preview = outlinePreview.value
  const work = store.works.find(w => w.id === preview?.workId)
  if (!work || store.activeWorkId !== preview.workId || JSON.stringify(work.chapters || []) !== preview.source) return alert('作品或原结构已修改，请重新生成预览')
  if (!confirm('应用新标题和摘要？现有章节正文及多余章节均会保留，后端会保留修改前版本。')) return
  const volumes = JSON.parse(preview.source)
  const existing = volumes.flatMap(v => v.chapters || [])
  const extra = []
  preview.suggestions.forEach((ch, index) => {
    if (existing[index]) { existing[index].title = ch.title; existing[index].summary = ch.summary }
    else extra.push({ id: crypto.randomUUID(), title: ch.title, summary: ch.summary, content: '', wordCount: 0, status: '大纲' })
  })
  if (extra.length) volumes.push({ id: crypto.randomUUID(), title: '新增大纲', isExpanded: true, chapters: extra })
  work.chapters = volumes
  outlinePreview.value = null
  try { await flushWork(work.id) } catch (e) { alert(e.message) }
}

const totalNodes = computed(() => {
  let count = 0
  if (!activeWorkData.value.chapters) return 0
  activeWorkData.value.chapters.forEach(act => {
    count++
    if (act.chapters) count += act.chapters.length
  })
  return count
})

const isExpanding = ref({})

const expandOutline = async (act) => {
  if (isExpanding.value[act.id]) return
  const task = tasks.begin(), work = task.work
  const config = getAgentConfig('EditorAgent')
  if (!hasModelCredentials(config)) {
    task.finish()
    alert("请先在【AI引擎策略】中配置 API Key 或连接账号！")
    return
  }

  isExpanding.value[act.id] = true
  try {
    task.assertCurrent()
    const prompt = store.prompts.outline_expand
      .replace(/{title}/g, work.title)
      .replace(/{volumeTitle}/g, act.title)
      .replace(/{volumeDesc}/g, act.summary)

    const baseUrl = config.baseUrl ? config.baseUrl.replace(/\/+$/, '') : 'https://api.openai.com/v1'
    
    const response = await llmFetch(`${baseUrl}/chat/completions`, {
      signal: task.signal,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...modelAuthHeaders(config)
      },
      body: JSON.stringify({
        model: config.modelName || 'gpt-3.5-turbo',
        messages: [{ role: 'system', content: prompt }],
        temperature: 0.7
      })
    })

    if (!response.ok) throw new Error(`请求失败: ${response.status}`)

    const data = await response.json()
    const content = data.choices[0].message.content
    
    let parsedData = null
    try {
      const jsonMatch = content.match(/```json\n([\s\S]*?)\n```/)
      const rawJson = jsonMatch ? jsonMatch[1] : content
      parsedData = parseModelJSON(rawJson, rawJson.trim().startsWith('[') ? 'array' : 'object')
    } catch (err) {
      console.warn("JSON解析失败", err)
      throw new Error("AI 返回的数据格式异常，解析彻底失败。")
    }

    let chaptersArray = Array.isArray(parsedData) ? parsedData : (parsedData.chapters || [])
    chaptersArray = parseModelJSON(JSON.stringify(chaptersArray), 'array')
    task.assertCurrent()
    if (!work.chapters?.includes(act)) return
    if (chaptersArray.length > 0) {
      if (!act.chapters) act.chapters = []
      act.chapters.push(...chaptersArray.map(ch => ({
        id: Date.now() + Math.random(),
        num: ch.chapterNum || ch.num || '新章节',
        title: ch.title || '无标题',
        summary: ch.summary || ''
      })))
      act.isExpanded = true
    } else {
      throw new Error("模型返回的细纲为空")
    }

  } catch (e) {
    if (task.cancelled) return
    console.error("Expand failed", e)
    alert(`细纲裂变失败: ${e.message}`)
  } finally {
    task.finish()
    isExpanding.value[act.id] = false
  }
}

const deleteAct = (actIndex) => {
  if(confirm('确定删除此节点及所属的所有子节点吗？')) {
    activeWorkData.value.chapters.splice(actIndex, 1)
  }
}

const deleteSequence = (actIndex, seqIndex) => {
  activeWorkData.value.chapters[actIndex].chapters.splice(seqIndex, 1)
}

const addNode = () => {
  activeWorkData.value.chapters ||= []
  activeWorkData.value.chapters.push({ id: crypto.randomUUID(), title: '新分卷', isExpanded: true, chapters: [] })
}

const refreshData = async () => {
  try { await backendAPI.fetchWorks() } catch (e) { alert(e.message) }
}
</script>

<template>
  <div class="structure-container">
    
    <!-- Top Header -->
    <div class="page-header">
      <div class="title-group">
        <UiIcon name="layers" :size="23" class="page-heading-icon" />
        <h2 class="page-title">故事结构</h2>
      </div>
      
      <div class="action-buttons">
        <button class="btn-ghost" @click="refreshData">
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"></path><path d="M3 3v5h5"></path></svg>
          刷新
        </button>
        <div class="beat-sheet-selector">
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20"></path></svg>
          <select v-model="selectedBeatSheet" class="ui-select-small">
            <option value="default">经典三幕剧</option>
            <option value="waste">退婚废柴打脸流 (黄金三章)</option>
            <option value="infinite">无限流副本循环 (高冲突)</option>
            <option value="system">系统日常流 (卡高潮点)</option>
          </select>
        </div>
        <button class="btn-warning" @click="generateStructure" :disabled="isGenerating">
          <svg v-if="!isGenerating" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>
          <svg v-else class="spinner" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="2" x2="12" y2="6"></line><line x1="12" y1="18" x2="12" y2="22"></line><line x1="4.93" y1="4.93" x2="7.76" y2="7.76"></line><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"></line><line x1="2" y1="12" x2="6" y2="12"></line><line x1="18" y1="12" x2="22" y2="12"></line><line x1="4.93" y1="19.07" x2="7.76" y2="16.24"></line><line x1="16.24" y1="7.76" x2="19.07" y2="4.93"></line></svg>
          {{ isGenerating ? '按节拍生成中...' : '按节拍生成大纲' }}
        </button>
        <button class="btn-primary" @click="addNode">
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
          添加节点
        </button>
      </div>
    </div>

    <section v-if="outlinePreview" class="outline-preview">
      <h3>新大纲预览</h3>
      <p>应用后保留已有章节的正文、分卷及章节 ID；只更新对应章节的标题与摘要。</p>
      <ol><li v-for="(chapter, index) in outlinePreview.suggestions" :key="index"><strong>{{ chapter.title }}</strong>：{{ chapter.summary }}</li></ol>
      <button class="btn-primary" @click="applyOutline">保留正文并应用大纲</button>
      <button class="btn-ghost" @click="outlinePreview = null">取消</button>
    </section>
    <!-- Main Tree Container -->
    <div class="tree-container">
      
      <!-- Tree Header -->
      <div class="tree-header">
        <div class="tree-title">
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
          叙事结构树
        </div>
        <div class="tree-meta">
          {{ totalNodes }} 个节点
        </div>
      </div>

      <!-- Tree Body -->
      <div class="tree-body">
        
        <template v-if="activeWorkData.chapters && activeWorkData.chapters.length">
          
          <div class="act-group" v-for="(act, aIndex) in activeWorkData.chapters" :key="act.id">
            
            <!-- Act Item -->
            <div class="tree-item act-item">
              <div class="item-content">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="act-icon"><path d="M20.2 6 3 11l-.9-2.4c-.3-1.1.3-2.2 1.3-2.5l13.5-4c1.1-.3 2.2.3 2.5 1.3Z"></path><path d="m6.2 5.3 3.1 3.9"></path><path d="m12.4 3.4 3.1 4"></path><path d="M3 11h18v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"></path></svg>
                <span class="act-title">{{ act.title }}</span>
              </div>
              <div class="item-actions">
                <button class="expand-btn" @click="expandOutline(act)" :disabled="isExpanding[act.id]" title="生成更多细纲">
                  <span v-if="isExpanding[act.id]">⌛ AI推演中...</span>
                  <span v-else>✨ 深挖细纲</span>
                </button>
                <button class="delete-btn" @click="deleteAct(aIndex)" title="删除此幕">
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"></path><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path></svg>
                </button>
              </div>
            </div>

            <!-- Sequence Items -->
            <div class="sequence-list" v-if="act.chapters && act.chapters.length">
              <div class="tree-item sequence-item" v-for="(seq, sIndex) in act.chapters" :key="seq.id">
                <div class="item-content">
                  <span class="tag-sequence">序列</span>
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="seq-icon"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
                  <span class="seq-title">{{ seq.title }}</span>
                </div>
                <div class="item-actions">
                  <button class="delete-btn" @click="deleteSequence(aIndex, sIndex)" title="删除此序列">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"></path><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path></svg>
                  </button>
                </div>
              </div>
            </div>
            
          </div>
          
        </template>
        
        <div v-else class="empty-state">
          <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
          <p>尚未创建故事结构，点击右上角由 AI 自动生成。</p>
        </div>

      </div>

    </div>

    <!-- Fullscreen Loading Overlay (Optional but nice UX) -->
    <div class="loading-overlay" v-if="isGenerating">
      <div class="loader-box">
        <div class="spinner-large"></div>
        <p>AI 正在构思精妙绝伦的树状结构...</p>
      </div>
    </div>
    
  </div>
</template>

<style scoped>
.outline-preview { padding: 24px; margin: 16px 0; background: var(--panel-bg); border: 1px solid var(--border-color); border-radius: 12px; max-height: 420px; overflow: auto; }
.outline-preview li { margin: 12px 0; }
.structure-container {
  padding: 32px 48px;
  max-width: 1200px;
  margin: 0 auto;
  position: relative;
  min-height: calc(100vh - 64px);
}

/* Page Header */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.title-group {
  display: flex;
  align-items: center;
  gap: 12px;
}

.title-icon {
  filter: drop-shadow(0 2px 4px rgba(245, 158, 11, 0.2));
}

.page-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
}

.action-buttons {
  display: flex;
  align-items: center;
  gap: 12px;
}

.btn-ghost, .btn-warning, .btn-primary {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid transparent;
}

.btn-ghost {
  background: var(--panel-bg);
  border-color: var(--border-color);
  color: var(--text-secondary);
}

.btn-ghost:hover {
  background: var(--surface-subtle);
  color: var(--text-primary);
}

.btn-warning {
  background: var(--accent-bg);
  color: var(--accent-color);
  border-color: var(--accent-border);
}

.btn-warning:hover:not(:disabled) {
  background: var(--accent-border);
}

.btn-warning:disabled {
  opacity: 0.7;
  cursor: wait;
}

.btn-primary {
  background: var(--accent-color);
  color: white;
}

.btn-primary:hover {
  background: var(--accent-hover);
}

/* Main Tree Container */
.tree-container {
  background: var(--panel-bg);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.02);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.tree-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  border-bottom: 1px solid var(--border-color);
  background: var(--surface-subtle);
}

.tree-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.tree-meta {
  font-size: 13px;
  color: var(--text-category);
}

/* Tree Body & List */
.tree-body {
  padding: 12px 24px 32px 24px;
}

.act-group {
  margin-bottom: 12px;
}

.tree-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  border-radius: 8px;
  transition: background 0.2s;
}

.tree-item:hover {
  background: var(--surface-subtle);
}

.item-content {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* Act specifically */
.act-item {
  margin-top: 12px;
}

.act-icon {
  color: var(--text-secondary);
}

.act-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

/* Sequence specifically */
.sequence-list {
  padding-left: 28px; /* Indent */
  position: relative;
}

.sequence-list::before {
  content: '';
  position: absolute;
  top: 0;
  bottom: 0;
  left: 14px;
  width: 1px;
  background-color: var(--border-color);
}

.sequence-item {
  position: relative;
}

.tag-sequence {
  font-size: 12px;
  color: var(--accent-color);
  background-color: var(--accent-bg);
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 500;
}

.seq-icon {
  color: var(--text-category);
}

.seq-title {
  font-size: 14px;
  color: var(--text-secondary);
}

/* Actions */
.item-actions {
  opacity: 0;
  transition: opacity 0.2s;
  display: flex;
  gap: 8px;
}

.tree-item:hover .item-actions {
  opacity: 1;
}

.expand-btn {
  background: var(--accent-bg);
  border: none;
  color: var(--accent-color);
  cursor: pointer;
  padding: 6px 12px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s;
  font-size: 12px;
  font-weight: 600;
}

.expand-btn:hover:not(:disabled) {
  background: var(--accent-border);
}

.delete-btn {
  background: transparent;
  border: none;
  color: var(--danger-color);
  cursor: pointer;
  padding: 6px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s;
}

.delete-btn:hover {
  background: var(--danger-bg);
}

/* Empty State */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 0;
  color: var(--text-category);
}

.empty-state svg {
  margin-bottom: 16px;
  opacity: 0.4;
}

/* Loading Overlay */
.loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(255,255,255,0.8);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  border-radius: 12px;
}

.loader-box {
  background: var(--panel-bg);
  padding: 40px;
  border-radius: 16px;
  box-shadow: 0 10px 40px rgba(0,0,0,0.1);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.spinner-large {
  width: 40px;
  height: 40px;
  border: 4px solid var(--hover-bg);
  border-top-color: var(--accent-color);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  100% { transform: rotate(360deg); }
}
.spinner {
  animation: spin 1s linear infinite;
}
.beat-sheet-selector {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--card-bg);
  padding: 6px 12px;
  border-radius: 6px;
  border: 1px solid var(--border-color);
  color: var(--primary-color);
}

.ui-select-small {
  border: none;
  background: transparent;
  font-size: 0.85rem;
  color: var(--text-primary);
  outline: none;
  cursor: pointer;
  padding-right: 16px;
}
</style>
