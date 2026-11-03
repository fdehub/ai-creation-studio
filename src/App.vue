<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { store, activeWorkData, backendAPI, saveState, flushAll } from './store.js'
import { apiFetch, setBackendToken } from './api.js'
import HomePage from './components/HomePage.vue'
import Sidebar from './components/Sidebar.vue'
import MyWorks from './components/MyWorks.vue'
import Dashboard from './components/Dashboard.vue'
import WritingEditor from './components/WritingEditor.vue'
import CharacterWorkshop from './components/CharacterWorkshop.vue'
import WorldviewConstruction from './components/WorldviewConstruction.vue'
import StoryStructure from './components/StoryStructure.vue'
import PlotEngine from './components/PlotEngine.vue'
import ChapterManagement from './components/ChapterManagement.vue'
import AIChatAssistant from './components/AIChatAssistant.vue'
import MaterialLibrary from './components/MaterialLibrary.vue'
import WritingAnalysis from './components/WritingAnalysis.vue'
import IntelligentSentinel from './components/IntelligentSentinel.vue'
import StrategySettings from './components/StrategySettings.vue'
import PromptEngineering from './components/PromptEngineering.vue'
import ComicStudio from './components/ComicStudio.vue'
import UiIcon from './components/UiIcon.vue'

const showSpotlight = ref(false)
const showBookDropdown = ref(false)
const mainArea = ref(null)
const isWorkPage = computed(() => !['首页','我的作品','策略与设置','提示词工程'].includes(store.activeMenuItem))
watch(() => store.activeMenuItem, async () => { showBookDropdown.value = false; await nextTick(); if (mainArea.value) { mainArea.value.scrollTop = 0; mainArea.value.scrollLeft = 0 } })
const isDark = ref(document.documentElement.dataset.theme === 'dark')
const toggleTheme = () => { store.generalSettings.theme = isDark.value ? 'light' : 'dark' }

const switchBook = (id) => {
  store.activeWorkId = id
  showBookDropdown.value = false
}

const showError = e => alert(e.message)
const connectionError = ref('')
const tokenInput = ref('')
const revisionList = ref(null)
const searchText = ref('')
const loadWorks = async () => {
  connectionError.value = ''
  try { await backendAPI.fetchWorks() } catch (e) { connectionError.value = e.message }
}
const connectBackend = async () => { setBackendToken(tokenInput.value); tokenInput.value = ''; await loadWorks() }
const showRevisions = async () => {
  try {
    await flushAll()
    revisionList.value = await (await apiFetch(`/works/${store.activeWorkId}/revisions`)).json()
  } catch (e) { alert(e.message) }
}
const restoreRevision = async id => {
  if (!confirm('恢复此版本？当前内容也会先保存为备份。')) return
  try { await backendAPI.restoreRevision(store.activeWorkId, id); revisionList.value = null }
  catch (e) { alert(e.message) }
}
const searchResults = computed(() => {
  const query = searchText.value.trim().toLowerCase()
  if (!query) return []
  const work = activeWorkData.value
  const records = [
    ...(work.characters || []).map(c => ({ type: '人物', title: c.name, context: c.description })),
    ...(work.worldview || []).flatMap(cat => (cat.items || []).map(i => ({ type: '设定', title: i.name, context: i.desc }))),
    ...(work.chapters || []).flatMap(v => (v.chapters || []).map(c => ({ type: '章节', title: c.title, context: (c.summary || '') + ' ' + (c.content || ''), chapterId: c.id })))
  ]
  return records.filter(r => `${r.title} ${r.context}`.toLowerCase().includes(query)).slice(0, 30)
})
const openSearchResult = item => {
  if (item.chapterId) { store.activeChapterId = item.chapterId; store.activeMenuItem = '写作编辑器' }
  else store.activeMenuItem = item.type === '人物' ? '人物工坊' : '世界观构筑'
  showSpotlight.value = false
}
onMounted(loadWorks)
watch(() => store.generalSettings.theme, theme => {
  const dark = theme === 'dark' || (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches)
  document.documentElement.dataset.theme = dark ? 'dark' : 'light'
  isDark.value = dark
}, { immediate: true })

// Global hotkey for spotlight
const handleHotkey = (e) => {
  if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
    e.preventDefault()
    showSpotlight.value = true
  }
  if (e.key === 'Escape' && showSpotlight.value) {
    showSpotlight.value = false
  }
}
window.addEventListener('keydown', handleHotkey)
onUnmounted(() => window.removeEventListener('keydown', handleHotkey))
</script>

<template>
  <div class="layout">
    <Sidebar />
    <main class="content">
      <header class="global-topbar" :class="{'with-book': isWorkPage && store.activeWorkId}">
        <div class="topbar-left"><span class="topbar-context">工作台</span><span class="topbar-slash">/</span><h1 class="page-title-simple">{{ store.activeMenuItem === '首页' ? '创作中心' : store.activeMenuItem }}</h1></div>
        <div class="topbar-right">
          <div v-if="store.activeWorkId && !['首页', '我的作品', '策略与设置', '提示词工程'].includes(store.activeMenuItem)" class="book-selector-container">
            <button class="book-selector" @click="showBookDropdown = !showBookDropdown" :aria-expanded="showBookDropdown" aria-label="切换当前作品"><UiIcon name="book" :size="14" /><span class="book-title">{{ activeWorkData.title }}</span><span class="book-chevron">⌄</span></button>
            <div class="book-dropdown" v-if="showBookDropdown"><button class="dropdown-item" v-for="w in store.works" :key="w.id" @click="switchBook(w.id)" :class="{ active: w.id === store.activeWorkId }">{{ w.title }}</button></div>
          </div>
          <button class="global-search" @click="showSpotlight = true" aria-label="搜索全书内容"><UiIcon name="search" :size="16" /><span>搜索作品内容</span><kbd>Ctrl K</kbd></button>
          <span v-if="store.activeMenuItem !== 'AI对话助手'" class="save-indicator" :class="{pending:saveState.pending,error:saveState.error}"><UiIcon name="check" :size="13" /><span>{{ saveState.error ? '作品保存失败' : saveState.pending ? '作品待保存' : '作品已保存' }}</span></span>
          <button v-if="isWorkPage && store.activeMenuItem !== 'AI对话助手'" class="topbar-save" @click="flushAll().catch(showError)">保存作品</button>
          <button v-if="isWorkPage && store.activeWorkId && store.activeMenuItem !== 'AI对话助手'" class="icon-btn history-button" title="作品历史版本" aria-label="作品历史版本" @click="showRevisions"><UiIcon name="history" :size="17" /></button>
          <button class="icon-btn" :title="isDark ? '切换浅色模式' : '切换深色模式'" aria-label="切换主题" @click="toggleTheme"><UiIcon :name="isDark ? 'sun' : 'moon'" :size="17" /></button>
        </div>
      </header>
      <div v-if="connectionError" class="notice-bar" role="alert">
        {{ connectionError }}
        <input v-model="tokenInput" type="password" placeholder="后端访问令牌" autocomplete="off" />
        <button @click="connectBackend">连接</button><button @click="loadWorks">重试</button>
      </div>
      <div v-if="saveState.error" class="notice-bar" role="alert">{{ saveState.error }} <button @click="flushAll().catch(() => {})">重试保存</button></div>
      <div v-if="saveState.recovery.length" class="notice-bar">
        发现未提交的本地草稿：
        <div v-for="draft in saveState.recovery" :key="draft.id">
          {{ JSON.parse(draft.snapshot).title }}
          <button @click="backendAPI.restoreDraft(draft).catch(showError)">恢复草稿</button>
          <button @click="backendAPI.discardDraft(draft).catch(showError)">保留后端版本</button>
        </div>
      </div>
      <div v-if="revisionList" class="notice-bar">
        <strong>修改前版本（最近 20 次正文变化）</strong>
        <button @click="revisionList = null">关闭</button>
        <span v-if="!revisionList.length">暂无备份</span>
        <div v-for="revision in revisionList" :key="revision.id">{{ new Date(revision.createdAt).toLocaleString() }} <button @click="restoreRevision(revision.id)">恢复</button></div>
      </div>
      <div ref="mainArea" class="main-area" :class="{ 'home-area': store.activeMenuItem === '首页', 'no-padding': store.activeMenuItem === '写作编辑器' || store.activeMenuItem === 'AI对话助手' || store.activeMenuItem === '首页' }">
        <div v-if="store.works.length === 0 && !['我的作品', '首页', '提示词工程', '策略与设置'].includes(store.activeMenuItem)" class="global-empty-state">
          <div class="empty-icon">📚</div>
          <h2>尚未选择作品</h2>
          <p>请先在“我的作品”中创建或打开一部小说，再使用工作台功能。</p>
          <button class="primary-btn" @click="store.activeMenuItem = '我的作品'">前往我的作品</button>
        </div>
        <template v-else>
          <HomePage v-if="store.activeMenuItem === '首页'" />
          <MyWorks v-else-if="store.activeMenuItem === '我的作品'" />
        <Dashboard v-else-if="store.activeMenuItem === '仪表盘'" />
        <WritingEditor v-else-if="store.activeMenuItem === '写作编辑器'" />
        <CharacterWorkshop v-else-if="store.activeMenuItem === '人物工坊'" />
        <WorldviewConstruction v-else-if="store.activeMenuItem === '世界观构筑'" />
        <StoryStructure v-else-if="store.activeMenuItem === '故事结构'" />
        <PlotEngine v-else-if="store.activeMenuItem === '情节引擎'" />
        <ChapterManagement v-else-if="store.activeMenuItem === '章节管理'" />
        <AIChatAssistant v-else-if="store.activeMenuItem === 'AI对话助手'" />
        <MaterialLibrary v-else-if="store.activeMenuItem === '灵感素材库'" />
        <WritingAnalysis v-else-if="store.activeMenuItem === '写作分析'" />
        <IntelligentSentinel v-else-if="store.activeMenuItem === '智能哨兵'" />
        <StrategySettings v-else-if="store.activeMenuItem === '策略与设置'" />
        <PromptEngineering v-else-if="store.activeMenuItem === '提示词工程'" />
        <ComicStudio v-else-if="store.activeMenuItem === '漫剧工坊'" />
          <div v-else class="placeholder">
            <p>“{{ store.activeMenuItem }}”功能模块正在开发中...</p>
          </div>
        </template>
      </div>
    </main>
    
    <!-- Spotlight Search Overlay -->
    <div class="spotlight-overlay" v-if="showSpotlight" @click.self="showSpotlight = false">
      <div v-dialog class="spotlight-modal">
        <div class="spotlight-input-container">
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#a78bfa" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
          <input v-model="searchText" type="text" placeholder="搜索当前作品的人物、设定和正文" autofocus class="spotlight-input" />
          <span class="esc-hint">ESC</span>
        </div>
        <div class="spotlight-results">
          <div class="spotlight-category">
            <h4>{{ searchText.trim() ? `找到 ${searchResults.length} 条结果` : '输入关键词搜索当前作品' }}</h4>
            <ul><li v-for="(item, index) in searchResults" :key="index" @click="openSearchResult(item)">
              <span class="tag">{{ item.type }}</span> {{ item.title }}
              <span class="context-hint">{{ (item.context || '').slice(0, 60) }}</span>
            </li></ul>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.notice-bar { padding: 10px 24px; background: var(--accent-bg); border-bottom: 1px solid var(--border-color); max-height: 180px; overflow: auto; }
.notice-bar button, .notice-bar input { margin: 4px 8px; padding: 4px 8px; }
.layout {
  display: flex;
  width: 100%;
  height: 100%;
}

.content {
  flex: 1;
  display: flex;
  flex-direction: column;
  background-color: var(--bg-color);
}

.global-topbar {
  height: 56px;
  background-color: var(--panel-bg);
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  position: relative;
  z-index: 1000;
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.page-title-simple {
  font-size: 18px;
  font-weight: 600;
  margin: 0;
  color: var(--text-primary);
}

.book-selector {
  display: flex;
  align-items: center;
  gap: 8px;
  background-color: var(--hover-bg);
  padding: 6px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.2s;
}

.book-selector:hover {
  background-color: var(--border-color);
}

.book-selector .dot {
  width: 6px;
  height: 6px;
  background-color: var(--text-category);
  border-radius: 50%;
}

.book-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  max-width: 150px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.book-selector svg {
  color: var(--text-category);
}

.global-search {
  display: flex;
  align-items: center;
  gap: 8px;
  background-color: var(--surface-subtle);
  border: 1px solid var(--border-color);
  padding: 6px 12px;
  border-radius: 6px;
  width: 280px;
}

.global-search svg {
  color: var(--text-category);
}

.global-search input {
  border: none;
  background: transparent;
  outline: none;
  font-size: 13px;
  width: 100%;
  color: var(--text-primary);
}

.global-search input::placeholder {
  color: var(--text-category);
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.icon-btn {
  background: transparent;
  border: none;
  cursor: pointer;
  color: var(--text-secondary);
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  transition: all 0.2s;
}

.icon-btn:hover {
  background-color: var(--hover-bg);
  color: var(--text-primary);
}

.main-area {
  flex: 1;
  padding: 32px;
  overflow-y: auto;
}

.main-area.no-padding {
  padding: 0;
  overflow: hidden;
}

.placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-secondary);
  font-size: 1.1rem;
}

.global-empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  background: var(--bg-color);
  text-align: center;
}
.global-empty-state .empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.5;
}
.global-empty-state h2 {
  font-size: 20px;
  color: var(--text-color);
  margin-bottom: 8px;
}
.global-empty-state p {
  color: var(--text-secondary);
  margin-bottom: 24px;
}
.global-empty-state .primary-btn {
  background: var(--primary-color);
  color: #fff;
  border: none;
  padding: 10px 24px;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}
.global-empty-state .primary-btn:hover {
  filter: brightness(1.1);
  transform: translateY(-1px);
}

.book-selector-container {
  position: relative;
}

.book-selector {
  cursor: pointer;
  padding: 6px 12px;
  border-radius: 6px;
  transition: background-color 0.2s;
  display: flex;
  align-items: center;
  gap: 8px;
}

.book-selector:hover {
  background-color: var(--hover-color);
}

.book-selector svg {
  transition: transform 0.2s;
}

.book-selector svg.rotated {
  transform: rotate(180deg);
}

.book-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  margin-top: 8px;
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  box-shadow: 0 10px 25px rgba(0,0,0,0.1);
  width: 200px;
  z-index: 9999;
  padding: 4px;
}

.dropdown-item {
  padding: 8px 12px;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.9rem;
  color: var(--text-color);
}

.dropdown-item:hover {
  background-color: var(--hover-color);
}

.dropdown-item.active {
  background-color: var(--hover-color);
  font-weight: bold;
}

.spotlight-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: rgba(0,0,0,0.4);
  backdrop-filter: blur(4px);
  z-index: 9999;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 12vh;
}

.spotlight-modal {
  width: 600px;
  background: var(--card-bg);
  border-radius: 12px;
  box-shadow: 0 20px 40px rgba(0,0,0,0.2);
  overflow: hidden;
  border: 1px solid var(--border-color);
}

.spotlight-input-container {
  display: flex;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color);
  gap: 12px;
}

.spotlight-input {
  flex: 1;
  border: none;
  background: transparent;
  font-size: 1.1rem;
  color: var(--text-color);
  outline: none;
}

.esc-hint {
  font-size: 0.8rem;
  color: var(--text-muted);
  background: var(--hover-color);
  padding: 2px 6px;
  border-radius: 4px;
}

.spotlight-results {
  padding: 16px;
}

.spotlight-category h4 {
  font-size: 0.85rem;
  color: var(--text-muted);
  margin-bottom: 8px;
  padding-left: 8px;
}

.spotlight-category ul {
  list-style: none;
}

.spotlight-category li {
  padding: 10px 12px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  gap: 12px;
  cursor: pointer;
  color: var(--text-color);
  font-size: 0.95rem;
}

.spotlight-category li:hover {
  background: var(--hover-color);
}

.tag-char {
  background: rgba(246, 211, 101, 0.2);
  color: var(--accent-color);
}

.tag-item {
  background: rgba(167, 139, 250, 0.2);
  color: var(--primary-color);
}

.context-hint {
  font-size: 0.8rem;
  color: var(--text-muted);
  margin-left: auto;
}
</style>
