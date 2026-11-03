<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { store, getAgentConfig, backendAPI, flushWork } from '../store.js'
import { apiFetch, hasModelCredentials } from '../api.js'
import { consumeOutline } from '../sse.js'

let alive = true
const generationControllers = new Set()
const beginGeneration = () => {
  const controller = new AbortController()
  generationControllers.add(controller)
  return controller
}
const assertGeneration = (controller, work) => {
  if (!alive || controller.signal.aborted || !store.works.includes(work)) throw new Error('生成已取消，作品未被覆盖')
}
const generatedFields = ['characters', 'worldview', 'plotNodes', 'chapters', 'terms', 'timeline', 'rules']
const generationSnapshot = work => JSON.stringify(generatedFields.map(key => work[key]))
const generateProjectData = async (title, tags, synopsis, onProgress, workId, signal) => {
  const configs = Object.fromEntries(['LoreAgent', 'PlotAgent', 'EditorAgent'].map(role => [role, getAgentConfig(role)]))
  if (Object.values(configs).some(c => !hasModelCredentials(c))) throw new Error('请先为各 Agent 选择 API Key 或已连接账号')
  const response = await apiFetch('/agents/generate_industrial_outline', {
    method: 'POST', signal, headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, tags, synopsis, workId, configs, prompt: store.prompts.long_outline_generate })
  })
  let finalResult
  let chapters = []
  await consumeOutline(response, data => {
    if (signal.aborted) throw new Error('生成已取消')
    if (data.chapters) chapters = data.chapters
    if (data.step) onProgress?.(data.step, data)
    if (data.status === 'done') finalResult = data
  })
  return {
    characters: finalResult.plot?.characters || [], worldview: finalResult.worldview?.worldview || [],
    plotNodes: finalResult.plot?.plotNodes || [], chapters, terms: finalResult.worldview?.terms || [],
    timeline: finalResult.worldview?.timeline || [], rules: finalResult.worldview?.rules || []
  }
}

const openDropdownId = ref(null)
const showGlobalLoading = ref(false)

const getWorkWordCount = (work) => {
  if (!work || !work.chapters) return work?.wordCount || 0
  let total = 0
  for (const vol of work.chapters) {
    if (vol.chapters) {
      for (const chap of vol.chapters) {
        if (chap.content) {
          total += chap.content.length
        }
      }
    }
  }
  return total > 0 ? (total > 10000 ? (total/10000).toFixed(1) + '万' : total) : (work.wordCount || 0)
}

const closeDropdown = () => {
  openDropdownId.value = null
}

onMounted(() => {
  document.addEventListener('click', closeDropdown)
  

})
onUnmounted(() => {
  alive = false
  for (const controller of generationControllers) controller.abort()
  generationControllers.clear()
  document.removeEventListener('click', closeDropdown)
})

const toggleDropdown = (id) => {
  openDropdownId.value = openDropdownId.value === id ? null : id
}

const deleteWork = async (id) => {
  openDropdownId.value = null
  if (confirm("确定要永久删除这部作品吗？此操作无法恢复！")) {
    await backendAPI.deleteWork(id)
  }
}

const regenerateWork = async (id) => {
  if (showGlobalLoading.value || isGenerating.value) return
  openDropdownId.value = null
  const existingWork = store.works.find(w => w.id === id)
  if (existingWork?.chapters?.some(v => v.chapters?.some(c => c.content?.trim()))) {
    alert('该作品已有正文。请在故事结构中预览并应用新大纲，以保留正文。')
    return
  }
  if (!confirm('重新推演将替换当前无正文的大纲与设定，是否继续？')) return

  showGlobalLoading.value = true
  
  const work = store.works.find(w => w.id === id)
  if (work) {
    const controller = beginGeneration()
    const expected = generationSnapshot(work)
    store.activeWorkId = id
    try {
      generationProgress.value = '正在整理世界观、人物与故事大纲...'
      generationLogs.value = ['正在整理世界观、人物与故事大纲...']
      const result = await generateProjectData(work.title, work.tags.join(', '), work.synopsis || '', (msg) => { 
        generationProgress.value = msg 
        if (msg && !generationLogs.value.includes(msg)) generationLogs.value.push(msg)
      }, work.id, controller.signal)
      assertGeneration(controller, work)
      if (generationSnapshot(work) !== expected) throw new Error('生成期间作品已被编辑，请重新预览大纲后再应用')
      
      work.characters = result.characters || []
      work.worldview = result.worldview || []
      work.plotNodes = result.plotNodes || []
      work.chapters = result.chapters || []
      work.terms = result.terms || []
      work.timeline = result.timeline || []
      work.rules = result.rules || work.rules
      work.updatedAt = '刚刚'
      await flushWork(work.id)
      alert("✨ 重新推演完成！您可以进入工作台查看全新的故事脉络。")
    } catch (e) {
      console.error(e)
      if (alive && !controller.signal.aborted) alert(`推演失败: ${e.message}`)
    } finally {
      generationControllers.delete(controller)
    }
  }
  
  showGlobalLoading.value = false
}

const stats = computed(() => [
  { label: '作品总数', value: store.works.length, icon: '📚' },
  { label: '累计创作字数', value: store.works.reduce((total, w) => total + (w.chapters || []).flatMap(v => v.chapters || []).reduce((n, c) => n + (c.content || '').length, 0), 0), icon: '✒️' },
  { label: '草稿', value: store.works.filter(w => w.status === '草稿').length, icon: '📝' },
  { label: '生成中断', value: store.works.filter(w => w.status === '生成中断').length, icon: '⏸' }
])

const showCreateModal = ref(false)
const newWork = ref({
  title: '',
  tags: '',
  synopsis: ''
})

const isGenerating = ref(false)
const generationProgress = ref('')
const generationLogs = ref([])
const logsContainer = ref(null)

const handleCreate = async () => {
  if (isGenerating.value || showGlobalLoading.value) return
  if (!newWork.value.title.trim()) {
    alert("作品名称不能为空！")
    return
  }
  
  isGenerating.value = true
  const controller = beginGeneration()
  let currentWork
  let generationStarted = false
  const title = newWork.value.title.trim()
  
  const tagsStr = newWork.value.tags
  const synopsisStr = newWork.value.synopsis
  
  // PRE-CREATE the work to ensure no token waste!
  const gradients = [
    'linear-gradient(135deg, #a18cd1 0%, #fbc2eb 100%)',
    'linear-gradient(135deg, #84fab0 0%, #8fd3f4 100%)',
    'linear-gradient(135deg, #ff9a9e 0%, #fecfef 100%)',
    'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    'linear-gradient(135deg, #11998e 0%, #38ef7d 100%)'
  ]
  const tempWork = {
      title,
      tags: tagsStr.split(/[,，\s]+/).filter(t => t),
      synopsis: synopsisStr,
      cover: gradients[Math.floor(Math.random() * gradients.length)],
      createdAt: '刚刚',
      updatedAt: '刚刚',
      wordCount: '0',
      status: '草稿',
      characters: [],
      worldview: [],
      plotNodes: [],
      chapters: [],
      terms: [],
      timeline: [],
      materials: [],
      activities: [{ id: 1, time: '刚刚', msg: '创建作品档案。' }]
  }
  
  generationProgress.value = '正在创建作品档案...'
  generationLogs.value = ['正在创建作品档案...']
  
  try {
    const createdWork = await backendAPI.createWork(tempWork)
    currentWork = store.works.find(w => w.id === createdWork.id)
    assertGeneration(controller, currentWork)
    
    // Set activeWorkId immediately so auto-save works during streaming
    store.activeWorkId = currentWork.id
    const configs = ['LoreAgent', 'PlotAgent', 'EditorAgent'].map(getAgentConfig)
    if (configs.some(config => !hasModelCredentials(config))) {
      store.activeMenuItem = '写作编辑器'
      newWork.value = { title: '', tags: '', synopsis: '' }
      return
    }
    generationStarted = true
    let expected = generationSnapshot(currentWork)
    const assertUnedited = () => {
      assertGeneration(controller, currentWork)
      if (generationSnapshot(currentWork) !== expected) throw new Error('生成期间作品已被编辑，已停止覆盖')
    }
    
    generationProgress.value = '正在整理故事资料，准备开始创作...'
    generationLogs.value.push('正在整理故事资料，准备开始创作...')
    
    const result = await generateProjectData(
      title,
      tagsStr, 
      synopsisStr,
      (msg, partialData) => {
        assertUnedited()
        generationProgress.value = msg
        if (msg && !generationLogs.value.includes(msg)) {
          generationLogs.value.push(msg)
          setTimeout(() => {
            if (logsContainer.value) {
              logsContainer.value.scrollTop = logsContainer.value.scrollHeight
            }
          }, 50)
        }
        
        // INCREMENTAL SAVING!
        if (partialData) {
          if (partialData.chapters) currentWork.chapters = partialData.chapters;
          if (partialData.worldview) {
            currentWork.worldview = partialData.worldview;
            currentWork.terms = partialData.terms || [];
            currentWork.timeline = partialData.timeline || [];
          }
          if (partialData.characters) currentWork.characters = partialData.characters;
          if (partialData.plotNodes) currentWork.plotNodes = partialData.plotNodes;
          if (partialData.rules) currentWork.rules = partialData.rules;
        }
        expected = generationSnapshot(currentWork)
      }, currentWork.id, controller.signal
    )
    assertUnedited()
    
    // Final save of all data
    currentWork.characters = result.characters || currentWork.characters
    currentWork.worldview = result.worldview || currentWork.worldview
    currentWork.plotNodes = result.plotNodes || currentWork.plotNodes
    currentWork.chapters = result.chapters || currentWork.chapters
    currentWork.terms = result.terms || currentWork.terms
    currentWork.timeline = result.timeline || currentWork.timeline

    currentWork.rules = result.rules || currentWork.rules
    await flushWork(currentWork.id)
    assertGeneration(controller, currentWork)
    store.activeWorkId = currentWork.id
    store.activeMenuItem = '写作编辑器' // Automatically jump to editor

    showCreateModal.value = false
    newWork.value = { title: '', tags: '', synopsis: '' }
    generationLogs.value = []
  } catch (e) {
    if (generationStarted && store.works.includes(currentWork)) currentWork.status = '生成中断'
    console.error(e)
    if (alive && !controller.signal.aborted) alert(`开书失败或中断: ${e.message}。已创建的作品会保留。`)
  } finally {
    generationControllers.delete(controller)
    isGenerating.value = false
    showCreateModal.value = false
  }
}

const continueWriting = (id) => {
  store.activeWorkId = id
  store.activeMenuItem = '仪表盘'
}

const resumeWork = async (id) => {
  openDropdownId.value = null
  if (showGlobalLoading.value) return
  const work = store.works.find(w => w.id === id)
  if (!work) return
  store.activeWorkId = id
  showGlobalLoading.value = true
  const original = structuredClone(JSON.parse(JSON.stringify(work.chapters || [])))
  const controller = beginGeneration()
  let expected = JSON.stringify(work.chapters)
  const assertUnedited = () => {
    assertGeneration(controller, work)
    if (JSON.stringify(work.chapters) !== expected) throw new Error('续传期间章节已被编辑，已停止覆盖')
  }
  try {
    const response = await apiFetch('/agents/resume_industrial_outline', {
      method: 'POST', signal: controller.signal, headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: work.title, synopsis: work.synopsis || '', workId: id,
        characters: work.characters, plotNodes: work.plotNodes, chapters: original,
        prompt: store.prompts.long_outline_generate, config: getAgentConfig('EditorAgent') })
    })
    await consumeOutline(response, data => {
      assertUnedited()
      if (data.chapters?.length) {
        const merged = JSON.parse(JSON.stringify(original))
        const newChapters = data.chapters.flatMap(v => v.chapters || [])
        const ids = new Set(merged.flatMap(v => v.chapters || []).map(c => c.id))
        if (newChapters.some(ch => ids.has(ch.id))) throw new Error('服务器返回了重复章节，续传已停止')
        if (!merged.length) work.chapters = data.chapters
        else {
          merged[merged.length - 1].chapters.push(...newChapters)
          work.chapters = merged
        }
        expected = JSON.stringify(work.chapters)
      }
    })
    assertUnedited()
    work.status = '草稿'
    await flushWork(id)
    alert('断点续传完成，内容已保存。')
  } catch (e) {
    if (store.works.includes(work)) work.status = '生成中断'
    if (alive && !controller.signal.aborted) alert(`续传失败：${e.message}`)
  } finally {
    generationControllers.delete(controller)
    showGlobalLoading.value = false
  }
}
</script>

<template>
  <div class="my-works-container">
    <!-- Hero Section -->
    <section class="hero-section">
      <div class="hero-content">
        <h1 class="greeting">我的作品</h1>
        <p class="subtitle">管理你的小说项目，继续写作，或开始漫剧改编。</p>
      </div>
      <button class="create-btn" @click="showCreateModal = true">
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
        创建新作品
      </button>
    </section>

    <!-- Statistics Section -->
    <section class="stats-grid">
      <div class="stat-card" v-for="(stat, index) in stats" :key="index">
        <div class="stat-icon">{{ stat.icon }}</div>
        <div class="stat-info">
          <div class="stat-value">{{ stat.value }}</div>
          <div class="stat-label">{{ stat.label }}</div>
        </div>
      </div>
    </section>

    <!-- Works Grid Section -->
    <section class="works-section">
      <div class="section-header">
        <h2>近期创作</h2>
        <span class="view-all">共 {{ store.works.length }} 部作品</span>
      </div>
      <div class="works-grid">
        <div class="work-card" v-for="work in store.works" :key="work.id" @click="continueWriting(work.id)" style="cursor: pointer;">
          <div class="work-cover" :style="{ background: work.cover }">
            <div class="work-status" :class="{ 'interrupted': work.status === '生成中断' }" :style="work.status === '生成中断' ? 'background: rgba(239, 68, 68, 0.9);' : ''">{{ work.status }}</div>
          </div>
          <div class="work-details">
            <h3 class="work-title">{{ work.title }}</h3>
            <div class="work-tags">
              <span class="tag" v-for="tag in work.tags" :key="tag">{{ tag }}</span>
            </div>
            <div class="work-meta">
              <span>{{ getWorkWordCount(work) }}字</span>
              <span class="dot">•</span>
              <span>{{ work.updatedAt }}更新</span>
            </div>
          </div>
          <div class="work-actions">
            <button class="action-btn primary" @click.stop="continueWriting(work.id)">进入工作台</button>
            <div class="dropdown-wrapper">
              <button class="action-btn secondary" @click.stop="toggleDropdown(work.id)">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="1"></circle><circle cx="19" cy="12" r="1"></circle><circle cx="5" cy="12" r="1"></circle></svg>
              </button>
              
              <div class="dropdown-menu" v-if="openDropdownId === work.id">
                <div class="dropdown-item" v-if="work.status === '生成中断'" @click.stop="resumeWork(work.id)" style="color: var(--accent-color); font-weight: bold;">
                  <span class="dropdown-icon">▶️</span>接着推演
                </div>
                <div class="dropdown-item" @click.stop="regenerateWork(work.id)">
                  <span class="dropdown-icon">✨</span>重新推演
                </div>
                <div class="dropdown-item danger" @click.stop="deleteWork(work.id)">
                  <span class="dropdown-icon">🗑️</span>删除作品
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Create Modal -->
    <div class="modal-overlay" v-if="showCreateModal" @click.self="showCreateModal = false">
      <div v-dialog class="modal-content">
        <h2>✨ 创建新作品</h2>
        <p class="modal-desc">为您的下一部杰作奠定基础。</p>
        
        <div class="form-group">
          <label>作品名称</label>
          <input type="text" v-model="newWork.title" placeholder="例如：星渊黎明" class="modal-input" autofocus />
        </div>
        
        <div class="form-group">
          <label>核心标签</label>
          <input type="text" v-model="newWork.tags" placeholder="例如：科幻, 太空歌剧 (用逗号分隔)" class="modal-input" />
        </div>

        <div class="form-group">
          <label>一句话简介</label>
          <textarea v-model="newWork.synopsis" placeholder="简要描述故事的核心冲突或看点..." class="modal-input textarea"></textarea>
        </div>

        <div class="modal-actions" v-if="!isGenerating">
          <button class="btn-cancel" @click="showCreateModal = false">取消</button>
          <button class="btn-confirm" @click="handleCreate">✨ AI 一键开书</button>
        </div>
        
        <div class="generating-state" v-else>
          <div class="log-console" ref="logContainer">
            <div v-for="(log, idx) in generationLogs" :key="idx" class="log-line">
              <span class="log-time">[{{ new Date().toLocaleTimeString() }}]</span>
              <span class="log-msg">{{ log }}</span>
            </div>
            <div class="log-line active-line">
              <span class="log-time">[{{ new Date().toLocaleTimeString() }}]</span>
              <span class="log-msg blink">_</span>
            </div>
          </div>
          
          <div class="current-status" style="margin-top: 15px;">
            <svg class="spinner" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="2" x2="12" y2="6"></line><line x1="12" y1="18" x2="12" y2="22"></line><line x1="4.93" y1="4.93" x2="7.76" y2="7.76"></line><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"></line><line x1="2" y1="12" x2="6" y2="12"></line><line x1="18" y1="12" x2="22" y2="12"></line><line x1="4.93" y1="19.07" x2="7.76" y2="16.24"></line><line x1="16.24" y1="7.76" x2="19.07" y2="4.93"></line></svg>
            <span class="status-text">{{ generationProgress }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Global Loading Overlay -->
    <div class="modal-overlay global-loading" v-if="showGlobalLoading">
      <div class="generating-state global">
        <svg class="spinner" xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="2" x2="12" y2="6"></line><line x1="12" y1="18" x2="12" y2="22"></line><line x1="4.93" y1="4.93" x2="7.76" y2="7.76"></line><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"></line><line x1="2" y1="12" x2="6" y2="12"></line><line x1="18" y1="12" x2="22" y2="12"></line><line x1="4.93" y1="19.07" x2="7.76" y2="16.24"></line><line x1="16.24" y1="7.76" x2="19.07" y2="4.93"></line></svg>
        <span class="loading-text">{{ generationProgress }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.my-works-container {
  display: flex;
  flex-direction: column;
  gap: 32px;
  max-width: 1200px;
  margin: 0 auto;
}

/* Hero Section */
.hero-section {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: linear-gradient(135deg, rgba(255,255,255,0.8) 0%, rgba(255,255,255,0.4) 100%);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255,255,255,0.5);
  border-radius: 20px;
  padding: 32px 40px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.03);
}

.greeting {
  font-size: 28px;
  font-weight: 700;
  margin: 0 0 8px 0;
  color: var(--text-primary);
  letter-spacing: -0.5px;
}

.subtitle {
  font-size: 15px;
  color: var(--text-secondary);
  margin: 0;
}

.create-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  background-color: var(--accent-color);
  color: white;
  border: none;
  border-radius: 12px;
  padding: 14px 24px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: var(--accent-glow);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.create-btn:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
  background-color: var(--accent-hover);
}

/* Stats Section */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
}

.stat-card {
  display: flex;
  align-items: center;
  background-color: var(--panel-bg);
  padding: 24px;
  border-radius: 16px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.02);
  border: 1px solid var(--border-color);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.stat-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.04);
}

.stat-icon {
  font-size: 32px;
  margin-right: 16px;
  background: var(--accent-bg);
  height: 60px;
  width: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
}

.stat-info {
  display: flex;
  flex-direction: column;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;
}

.stat-label {
  font-size: 13px;
  color: var(--text-category);
  margin-top: 4px;
  font-weight: 500;
}

/* Works Section */
.works-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
}

.section-header h2 {
  font-size: 20px;
  font-weight: 600;
  margin: 0;
  color: var(--text-primary);
}

.view-all {
  font-size: 14px;
  color: var(--accent-color);
  text-decoration: none;
  font-weight: 500;
}

.view-all:hover {
  text-decoration: underline;
}

.works-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 24px;
}

.work-card {
  background-color: var(--panel-bg);
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.02);
  border: 1px solid var(--border-color);
  transition: all 0.3s ease;
  display: flex;
  flex-direction: column;
}

.work-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.06);
}

.work-cover {
  height: 140px;
  position: relative;
  display: flex;
  padding: 16px;
}

.work-status {
  position: absolute;
  top: 12px;
  right: 12px;
  background-color: rgba(255, 255, 255, 0.9);
  color: var(--text-primary);
  padding: 4px 10px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
  backdrop-filter: blur(4px);
}

.work-details {
  padding: 20px;
  flex: 1;
}

.work-title {
  font-size: 18px;
  font-weight: 600;
  margin: 0 0 12px 0;
  color: var(--text-primary);
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.work-tags {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.tag {
  background-color: var(--hover-bg);
  color: var(--text-secondary);
  font-size: 12px;
  padding: 4px 8px;
  border-radius: 4px;
  font-weight: 500;
}

.work-meta {
  font-size: 13px;
  color: var(--text-category);
  display: flex;
  align-items: center;
  gap: 6px;
}

.work-actions {
  display: flex;
  padding: 0 20px 20px;
  gap: 12px;
}

.action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.action-btn.primary {
  flex: 1;
  background-color: var(--accent-bg);
  color: var(--accent-color);
  padding: 10px;
}

.action-btn.primary:hover {
  background-color: var(--accent-bg);
}

.action-btn.secondary {
  background-color: var(--hover-bg);
  color: var(--text-secondary);
  width: 40px;
}

.action-btn.secondary:hover {
  background-color: var(--border-color);
}

/* Dropdown Menu */
.dropdown-wrapper {
  position: relative;
}

.dropdown-menu {
  position: absolute;
  bottom: calc(100% + 8px);
  right: 0;
  background: var(--panel-bg);
  border-radius: 12px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
  border: 1px solid var(--border-color);
  padding: 8px;
  min-width: 140px;
  z-index: 10;
  animation: scaleIn 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  transform-origin: bottom right;
}

@keyframes scaleIn {
  from { opacity: 0; transform: scale(0.95); }
  to { opacity: 1; transform: scale(1); }
}

.dropdown-item {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  cursor: pointer;
  transition: background-color 0.2s;
}

.dropdown-item:hover {
  background-color: var(--hover-bg);
}

.dropdown-item.danger {
  color: var(--danger-color);
}
.dropdown-item.danger:hover {
  background-color: var(--danger-bg);
}

.dropdown-icon {
  margin-right: 8px;
  font-size: 14px;
}

/* Modal Styles */
.modal-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background-color: rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.modal-content {
  background: var(--panel-bg);
  width: 480px;
  border-radius: 20px;
  padding: 32px;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
  animation: slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes slideUp {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}

.modal-content h2 {
  margin: 0 0 8px 0;
  font-size: 22px;
  color: var(--text-primary);
}

.modal-desc {
  margin: 0 0 24px 0;
  font-size: 14px;
  color: var(--text-secondary);
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-category);
  margin-bottom: 6px;
}

.modal-input {
  width: 100%;
  padding: 12px 14px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  font-size: 14px;
  box-sizing: border-box;
  transition: border-color 0.2s;
  outline: none;
}

.modal-input:focus {
  border-color: var(--accent-color);
}

.modal-input.textarea {
  min-height: 80px;
  resize: vertical;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 32px;
}

.btn-cancel {
  padding: 10px 20px;
  background: var(--hover-bg);
  border: none;
  border-radius: 8px;
  color: var(--text-secondary);
  font-weight: 500;
  cursor: pointer;
}

.btn-cancel:hover {
  background: var(--border-color);
}

.btn-confirm {
  padding: 10px 24px;
  background: var(--accent-color);
  border: none;
  border-radius: 8px;
  color: white;
  font-weight: 600;
  cursor: pointer;
}

.btn-confirm:hover {
  background: var(--accent-hover);
}

.generating-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 24px;
  padding: 30px 20px;
  background-color: var(--bg-hover);
  border-radius: 12px;
  margin-top: 10px;
}

.progress-tracker {
  display: flex;
  flex-direction: column;
  width: 100%;
  gap: 16px;
}

.log-console {
  background-color: #1a1a2e;
  border-radius: 8px;
  padding: 16px;
  font-family: 'Fira Code', 'Courier New', Courier, monospace;
  font-size: 13px;
  color: #a9b7c6;
  height: 200px;
  overflow-y: auto;
  box-shadow: inset 0 2px 10px rgba(0,0,0,0.5);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.log-line {
  display: flex;
  gap: 8px;
  line-height: 1.5;
}

.log-time {
  color: #6a8759;
  flex-shrink: 0;
}

.log-msg {
  color: #cc7832;
}

.active-line .log-msg {
  color: #ffc66d;
}

.blink {
  animation: blink 1s step-end infinite;
}

@keyframes blink {
  50% { opacity: 0; }
}

.current-status {
  display: flex;
  align-items: center;
  gap: 12px;
  color: var(--primary-color);
  font-weight: 600;
  font-size: 15px;
}

.spinner {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  100% {
    transform: rotate(360deg);
  }
}

.generating-state.global {
  margin-top: 0;
  background: var(--panel-bg);
  padding: 24px 40px;
  border-radius: 16px;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
  color: var(--accent-color);
  font-size: 18px;
}

.global-loading {
  z-index: 999;
}

@keyframes spin {
  100% { transform: rotate(360deg); }
}
.spinner {
  animation: spin 1s linear infinite;
}
</style>
