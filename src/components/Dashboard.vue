<script setup>
import { computed } from 'vue'
import { store, activeWorkData } from '../store.js'

const getWorkWordCount = (work) => {
  if (!work || !work.chapters) return work.wordCount || 0
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

const navigateTo = (menuItem) => {
  store.activeMenuItem = menuItem
}
const chapterList = computed(() => (activeWorkData.value.chapters || []).flatMap(v => v.chapters || []))
const writtenChapters = computed(() => chapterList.value.filter(c => (c.content || '').trim()).length)
const chapterProgress = computed(() => chapterList.value.length ? Math.round(writtenChapters.value / chapterList.value.length * 100) : 0)
</script>

<template>
  <div class="dashboard-container">
    <div class="header-welcome">
      <div>
        <h2 class="greeting">作品创作概览</h2>
        <p class="subtitle">梳理当前进度，继续推进你的故事。</p>
      </div>
      <button class="btn-primary continue-btn" @click="navigateTo('写作编辑器')">
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
        继续创作
      </button>
    </div>

    <div class="bento-grid">
      <!-- 核心进度卡片 (大) -->
      <div class="bento-item progress-card span-2">
        <div class="card-header">
          <h3>《{{ activeWorkData.title }}》</h3>
          <span class="status-badge">{{ activeWorkData.status }}</span>
        </div>
        <div class="progress-section">
          <div class="progress-stats">
            <div class="stat">
              <span class="label">当前字数</span>
              <span class="value">{{ getWorkWordCount(activeWorkData) }}</span>
            </div>
            <div class="stat">
              <span class="label">已写章节 / 全部章节</span>
              <span class="value">{{ writtenChapters }} / {{ chapterList.length }}</span>
            </div>
          </div>
          <div class="progress-bar-container">
            <div class="progress-bar" :style="{ width: chapterProgress + '%' }">
              <div class="progress-glow"></div>
            </div>
          </div>
          <div class="progress-footer">{{ chapterProgress }}% 的章节已写入正文</div>
        </div>
      </div>

      <!-- 快捷入口卡片 1 -->
      <div class="bento-item shortcut-card ai-chat" @click="navigateTo('AI对话助手')">
        <div class="shortcut-icon">
          <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
        </div>
        <h3>AI 助手</h3>
        <p>呼唤您的私人编辑</p>
      </div>

      <!-- 快捷入口卡片 2 -->
      <div class="bento-item shortcut-card character" @click="navigateTo('人物工坊')">
        <div class="shortcut-icon">
          <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>
        </div>
        <h3>人物工坊</h3>
        <p>打磨角色设定</p>
      </div>

      <!-- 最新动态时间轴 -->
      <div class="bento-item timeline-card span-2 row-span-2">
        <div class="card-header">
          <h3>近期动态</h3>
        </div>
        <div class="timeline" v-if="activeWorkData.activities && activeWorkData.activities.length">
          <div class="timeline-item" v-for="act in activeWorkData.activities" :key="act.id">
            <div class="timeline-icon" :class="act.icon">
              <template v-if="act.icon === 'edit'">
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
              </template>
              <template v-else-if="act.icon === 'ai'">
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a10 10 0 0 1 10 10v1a5 5 0 0 1-5 5h-1v-2a3 3 0 0 0-3-3H9a3 3 0 0 0-3 3v2H5a5 5 0 0 1-5-5V12A10 10 0 0 1 12 2z"></path></svg>
              </template>
              <template v-else>
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>
              </template>
            </div>
            <div class="timeline-content">
              <span class="time">{{ act.time }}</span>
              <p class="text">{{ act.msg }}</p>
            </div>
          </div>
        </div>
      </div>

      <!-- 快捷入口卡片 3 -->
      <div class="bento-item shortcut-card world span-2" @click="navigateTo('世界观构筑')">
        <div class="shortcut-icon">
          <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>
        </div>
        <div class="shortcut-text-area">
          <h3>世界观构筑</h3>
          <p>进入词条库，AI 脑暴补全设定</p>
        </div>
      </div>

    </div>
  </div>
</template>

<style scoped>
.dashboard-container {
  padding: 32px;
  max-width: 1200px;
  margin: 0 auto;
}

.header-welcome {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 32px;
  background: linear-gradient(135deg, var(--accent-color) 0%, var(--accent-hover) 100%);
  padding: 32px 40px;
  border-radius: 20px;
  color: white;
  box-shadow: var(--shadow-md);
}

.greeting {
  font-size: 28px;
  font-weight: 700;
  margin: 0 0 12px 0;
}

.subtitle {
  font-size: 15px;
  margin: 0;
  opacity: 0.9;
}

.continue-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  background-color: var(--panel-bg);
  color: var(--accent-color);
  padding: 12px 24px;
  border-radius: 12px;
  font-size: 16px;
  font-weight: 600;
  border: none;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}

.continue-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(0,0,0,0.15);
}

/* Bento Grid */
.bento-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  grid-auto-rows: minmax(180px, auto);
  gap: 24px;
}

.bento-item {
  background: var(--panel-bg);
  border-radius: 20px;
  padding: 24px;
  border: 1px solid var(--border-color);
  box-shadow: 0 4px 16px rgba(0,0,0,0.02);
  transition: transform 0.3s, box-shadow 0.3s;
}

.bento-item:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 24px rgba(0,0,0,0.06);
}

.span-2 {
  grid-column: span 2;
}

.row-span-2 {
  grid-row: span 2;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.card-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
}

.status-badge {
  background-color: var(--surface-subtle);
  color: var(--text-secondary);
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 13px;
  font-weight: 600;
}

/* Progress Card */
.progress-card {
  display: flex;
  flex-direction: column;
}

.progress-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.progress-stats {
  display: flex;
  justify-content: space-between;
  margin-bottom: 12px;
}

.stat {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat .label {
  font-size: 13px;
  color: var(--text-category);
}

.stat .value {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  font-family: monospace;
}

.progress-bar-container {
  height: 12px;
  background-color: var(--hover-bg);
  border-radius: 6px;
  overflow: hidden;
  position: relative;
  margin-bottom: 12px;
}

.progress-bar {
  height: 100%;
  background: linear-gradient(90deg, var(--accent-color), var(--accent-color));
  border-radius: 6px;
  position: relative;
  transition: width 1s ease-out;
}

.progress-glow {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  left: 0;
  background: linear-gradient(90deg, rgba(255,255,255,0) 0%, rgba(255,255,255,0.4) 50%, rgba(255,255,255,0) 100%);
  animation: shine 2s infinite;
}

@keyframes shine {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}

.progress-footer {
  font-size: 13px;
  color: var(--text-secondary);
  text-align: right;
}

/* Shortcut Cards */
.shortcut-card {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: flex-start;
  cursor: pointer;
}

.shortcut-card.world {
  flex-direction: row;
  align-items: center;
  justify-content: flex-start;
  gap: 20px;
}

.shortcut-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}

.shortcut-card.world .shortcut-icon {
  margin-bottom: 0;
}

.ai-chat .shortcut-icon,.character .shortcut-icon,.world .shortcut-icon { background:var(--surface-subtle); color:var(--text-secondary); }

.shortcut-card h3 {
  margin: 0 0 8px 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
}

.shortcut-card p {
  margin: 0;
  font-size: 13px;
  color: var(--text-secondary);
}

/* Timeline */
.timeline {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding-left: 8px;
}

.timeline-item {
  display: flex;
  gap: 16px;
  position: relative;
}

.timeline-item::before {
  content: '';
  position: absolute;
  top: 24px;
  bottom: -20px;
  left: 11px;
  width: 2px;
  background-color: var(--hover-bg);
}

.timeline-item:last-child::before {
  display: none;
}

.timeline-icon {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: var(--panel-bg);
  border: 2px solid var(--border-color);
  color: var(--text-secondary);
  position: relative;
  z-index: 1;
}

.timeline-icon.edit,.timeline-icon.ai,.timeline-icon.world { border-color:var(--border-color); color:var(--text-secondary); }

.timeline-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding-top: 2px;
}

.time {
  font-size: 12px;
  color: var(--text-category);
}

.text {
  margin: 0;
  font-size: 14px;
  color: var(--text-primary);
  line-height: 1.5;
}

@media (max-width: 1024px) {
  .bento-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
