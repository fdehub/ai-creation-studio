<script setup>
import { ref } from 'vue'
import { store, activeWorkData } from '../store.js'

const toggleVolume = (volume) => {
  volume.isExpanded = !volume.isExpanded
}

const addChapter = (volume) => {
  const newId = Date.now()
  volume.chapters.push({
    id: newId,
    title: `新章节 ${newId.toString().slice(-4)}`,
    wordCount: 0,
    status: '草稿',
    date: '-',
    content: ''
  })
  volume.isExpanded = true
}

const addVolume = () => {
  activeWorkData.value.chapters.push({
    id: Date.now(),
    title: `第 ${activeWorkData.value.chapters.length + 1} 卷：新卷名`,
    isExpanded: true,
    chapters: [],
    isEditing: false
  })
}

const editVolume = (volume) => {
  volume.isEditing = true
}

const saveVolume = (volume) => {
  volume.isEditing = false
}

const deleteVolume = (volumeId) => {
  if (confirm('确认删除该分卷吗？卷内所有章节将被删除，且不可恢复！')) {
    activeWorkData.value.chapters = activeWorkData.value.chapters.filter(v => v.id !== volumeId)
  }
}

const editChapter = (chapterId) => {
  store.activeChapterId = chapterId
  store.activeMenuItem = '写作编辑器'
}

const deleteChapter = (volume, chapterId) => {
  if (confirm('确认删除该章节吗？此操作不可恢复。')) {
    volume.chapters = volume.chapters.filter(c => c.id !== chapterId)
  }
}

const exportTXT = () => {
  if (!activeWorkData.value || !activeWorkData.value.chapters) {
    alert('没有可导出的内容')
    return
  }
  
  let content = `${activeWorkData.value.title || '无名作品'}\n\n`
  
  for (const vol of activeWorkData.value.chapters) {
    content += `【${vol.title}】\n\n`
    if (vol.chapters) {
      for (const chap of vol.chapters) {
        content += `\n${chap.title}\n\n`
        content += (chap.content || '') + '\n\n'
      }
    }
  }
  
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${activeWorkData.value.title || '小说导出'}.txt`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
</script>

<template>
  <div class="chapter-container">
    <div class="header-actions">
      <div>
        <h2 class="page-title">章节管理</h2>
        <p class="page-desc">管理分卷与章节，整理故事结构，或导出完整正文。</p>
      </div>
      <div class="action-buttons">
        <button class="ui-button ui-button--secondary" @click="exportTXT">
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
          导出TXT
        </button>
        <button class="ui-button ui-button--primary" @click="addVolume">
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="12" y1="18" x2="12" y2="12"></line><line x1="9" y1="15" x2="15" y2="15"></line></svg>
          新建分卷
        </button>
      </div>
    </div>

    <div class="volumes-list">
      <div class="volume-item" v-for="volume in activeWorkData.chapters" :key="volume.id">
        <!-- Volume Header -->
        <div class="volume-header" @click="!volume.isEditing && toggleVolume(volume)">
          <div class="vol-left">
            <svg class="chevron" :class="{ expanded: volume.isExpanded }" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>
            <input v-if="volume.isEditing" type="text" v-model="volume.title" class="vol-title-input" @blur="saveVolume(volume)" @keyup.enter="saveVolume(volume)" @click.stop autofocus />
            <h3 v-else class="vol-title" @dblclick.stop="editVolume(volume)">{{ volume.title }}</h3>
            <span class="vol-count">共 {{ volume.chapters.length }} 章</span>
          </div>
          <div class="vol-right">
            <button class="icon-btn action-icon" @click.stop="editVolume(volume)" title="重命名卷">
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
            </button>
            <button class="icon-btn action-icon danger" @click.stop="deleteVolume(volume.id)" title="删除分卷">
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
            </button>
            <button class="icon-btn" @click.stop="addChapter(volume)">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
              加一章
            </button>
          </div>
        </div>

        <!-- Chapters List -->
        <div class="chapters-wrapper" v-show="volume.isExpanded">
          <div class="chapter-list">
            <div class="chapter-item" v-for="chapter in volume.chapters" :key="chapter.id">
              <div class="chapter-sequence-mark" aria-hidden="true">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="12" r="1"></circle><circle cx="9" cy="5" r="1"></circle><circle cx="9" cy="19" r="1"></circle><circle cx="15" cy="12" r="1"></circle><circle cx="15" cy="5" r="1"></circle><circle cx="15" cy="19" r="1"></circle></svg>
              </div>
              <div class="chap-info">
                <h4 class="chap-title">{{ chapter.title }}</h4>
                <div class="chap-meta">
                  <span class="meta-item word-count">{{ (chapter.content || '').trim().length }} 字</span>
                  <span class="meta-item date">{{ chapter.date || '-' }}</span>
                </div>
              </div>
              <div class="chap-status">
                <span class="status-badge" :class="{
                  'status-published': chapter.status === '已发布',
                  'status-draft': chapter.status === '草稿',
                  'status-outline': chapter.status === '大纲'
                }">{{ chapter.status }}</span>
              </div>
              <div class="chap-actions">
                <button class="icon-btn" title="编辑" @click.stop="editChapter(chapter.id)">
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
                </button>
                <button class="icon-btn danger" title="删除" @click.stop="deleteChapter(volume, chapter.id)">
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg>
                </button>
              </div>
            </div>
            
            <div v-if="volume.chapters.length === 0" class="empty-state">
              暂无章节，点击右上角“加一章”开始创作
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chapter-container {
  padding: 32px;
  max-width: 1000px;
  margin: 0 auto;
}

.header-actions {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: 32px;
}

.page-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 8px 0;
}

.page-desc {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 0;
}

.btn-primary {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
  background-color: var(--accent-color);
  color: white;
  box-shadow: var(--accent-glow);
}

.btn-primary:hover {
  background-color: var(--accent-hover);
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

/* Volume Styles */
.volumes-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.volume-item {
  background: var(--panel-bg);
  border-radius: 12px;
  border: 1px solid var(--border-color);
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0,0,0,0.02);
}

.volume-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background-color: var(--surface-subtle);
  cursor: pointer;
  user-select: none;
  transition: background-color 0.2s;
}

.volume-header:hover {
  background-color: var(--hover-bg);
}

.volume-header:hover .action-icon {
  opacity: 1;
}

.vol-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.action-icon {
  padding: 4px;
  color: var(--text-category);
  opacity: 0;
  transition: all 0.2s;
}

.action-icon:hover {
  color: var(--text-primary);
  background: var(--hover-bg);
}
.action-icon.danger:hover {
  color: var(--danger-color);
  background: var(--danger-bg);
}

.chevron {
  color: var(--text-category);
  transition: transform 0.3s;
}

.chevron.expanded {
  transform: rotate(90deg);
}

.vol-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.vol-title-input {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  border: 1px solid var(--border-color);
  border-radius: 4px;
  padding: 2px 6px;
  outline: none;
}
.vol-title-input:focus {
  border-color: var(--accent-color);
}

.vol-count {
  font-size: 13px;
  color: var(--text-secondary);
  background: var(--border-color);
  padding: 2px 8px;
  border-radius: 12px;
}

.icon-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  background: transparent;
  border: 1px solid var(--border-color);
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s;
}

.icon-btn:hover {
  background: var(--panel-bg);
  color: var(--text-primary);
  border-color: var(--border-color);
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}

/* Chapters Styles */
.chapters-wrapper {
  border-top: 1px solid var(--border-color);
}

.chapter-list {
  display: flex;
  flex-direction: column;
}

.empty-state {
  padding: 32px;
  text-align: center;
  color: var(--text-category);
  font-size: 14px;
  font-style: italic;
}

.chapter-item {
  display: flex;
  align-items: center;
  padding: 16px 24px;
  border-bottom: 1px solid var(--bg-color);
  transition: background-color 0.2s;
}

.chapter-item:last-child {
  border-bottom: none;
}

.chapter-item:hover {
  background-color: var(--surface-subtle);
}

.drag-handle {
  color: var(--border-color);
  cursor: grab;
  padding-right: 16px;
  display: flex;
  align-items: center;
}

.drag-handle:hover {
  color: var(--text-category);
}

.chap-info {
  flex: 1;
}

.chap-title {
  margin: 0 0 4px 0;
  font-size: 15px;
  font-weight: 500;
  color: var(--text-primary);
}

.chap-meta {
  display: flex;
  gap: 16px;
}

.meta-item {
  font-size: 13px;
  color: var(--text-secondary);
}

.chap-status {
  width: 100px;
  display: flex;
  justify-content: center;
}

.status-badge {
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 12px;
  font-weight: 500;
}

.status-published { background-color: var(--success-bg); color: var(--success-color); }
.status-draft { background-color: var(--surface-subtle); color: var(--text-secondary); }
.status-outline { background-color: var(--hover-bg); color: var(--text-secondary); }

.chap-actions {
  display: flex;
  gap: 8px;
  margin-left: 24px;
}

.chap-actions .icon-btn {
  padding: 6px;
}

.icon-btn.danger:hover {
  color: var(--danger-color);
  border-color: var(--danger-border);
  background-color: var(--danger-bg);
}
</style>
