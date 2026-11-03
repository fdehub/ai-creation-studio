<script setup>
import { apiFetch } from '../api.js'
import MaterialImage from './MaterialImage.vue'
import { ref, computed, onUnmounted, watch } from 'vue'
import { store, activeWorkData } from '../store.js'
import { createWorkTasks } from '../work_tasks.js'
const tasks = createWorkTasks(store, activeWorkData)
watch(() => store.activeWorkId, () => { tasks.cancelAll(); showModal.value = false })
onUnmounted(() => tasks.dispose())

const safeLink = url => /^https?:\/\//i.test(url || '') ? url : '#'
const tags = ['全部', '赛博朋克', '废土', '星际', '人物参考', '战斗设定']
const activeTag = ref('全部')

const filteredMaterials = computed(() => {
  const mats = activeWorkData.value.materials || []
  if (activeTag.value === '全部') return mats
  return mats.filter(m => m.tag === activeTag.value)
})

const showModal = ref(false)
const newMat = ref({ title: '', tag: '赛博朋克', type: 'text', content: '', url: '', desc: '' })
const selectedFile = ref(null)

const handleFileChange = (e) => {
  const file = e.target.files[0]
  if (!file) return
  
  // 后端还会校验真实图片签名和大小。
  const validTypes = ['image/jpeg', 'image/png', 'image/webp']
  if (!validTypes.includes(file.type)) {
    alert('格式错误：仅支持 jpg/png/webp 格式图片。')
    e.target.value = ''
    return
  }
  if (file.size > 10 * 1024 * 1024) {
    alert('体积过大：单个文件不得超过 10MB。')
    e.target.value = ''
    return
  }
  if (newMat.value.url.startsWith('blob:')) URL.revokeObjectURL(newMat.value.url)
  selectedFile.value = file
  newMat.value.url = URL.createObjectURL(file)
}

const uploading = ref(false)
const clearPreview = () => {
  if (newMat.value.url.startsWith('blob:')) URL.revokeObjectURL(newMat.value.url)
  selectedFile.value = null
}
watch(showModal, visible => { if (!visible) clearPreview() })
onUnmounted(clearPreview)
const addMaterial = async () => {
  if (uploading.value) return
  if (!newMat.value.title) return alert('请输入素材标题')
  const work = activeWorkData.value
  const material = { ...newMat.value }
  const task = tasks.begin()
  uploading.value = true
  try {
    task.assertCurrent()
    if (material.type === 'image') {
      if (!selectedFile.value) throw new Error('请先选择本地图片')
      const data = await new Promise((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = () => resolve(reader.result)
        reader.onerror = () => reject(new Error('读取图片失败'))
        reader.readAsDataURL(selectedFile.value)
      })
      const response = await apiFetch('/uploads', { method: 'POST', signal: task.signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ data }) })
      material.url = (await response.json()).url
    }
    task.assertCurrent()
    work.materials ||= []
    work.materials.unshift({ id: crypto.randomUUID(), ...material })
    showModal.value = false
    clearPreview()
    newMat.value = { title: '', tag: '赛博朋克', type: 'text', content: '', url: '', desc: '' }
  } catch (e) { if (!task.cancelled) alert(`素材保存失败：${e.message}`) }
  finally { task.finish(); uploading.value = false }
}

const displayLimit = ref(20)
const limitedMaterials = computed(() => {
  return filteredMaterials.value.slice(0, displayLimit.value)
})
const loadMore = () => { displayLimit.value += 20 }
</script>

<template>
  <div class="material-container">
    <div class="header-actions">
      <div>
        <h2 class="page-title">灵感素材库</h2>
        <p class="page-desc">收集整理碎片化的灵感、参考图和文献，构建你的专属情绪板。</p>
      </div>
      <div class="action-buttons">
        <button class="btn-primary" @click="showModal = true">
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
          采集新素材
        </button>
      </div>
    </div>

    <div class="tags-filter">
      <button 
        v-for="tag in tags" 
        :key="tag" 
        class="filter-tag"
        :class="{ active: activeTag === tag }"
        @click="activeTag = tag"
      >
        {{ tag }}
      </button>
    </div>

    <div class="masonry-grid">
      <TransitionGroup name="list">
        <div 
          class="material-card glass-panel" 
          v-for="mat in limitedMaterials" 
          :key="mat.id"
        >
        <MaterialImage v-if="mat.type === 'image'" :url="mat.url" :title="mat.title" />
        <div class="mat-content">
          <div class="mat-header">
            <span class="mat-badge" :class="mat.type">
              {{ mat.type === 'image' ? '图片' : (mat.type === 'text' ? '文本' : '链接') }}
            </span>
            <span class="mat-tag">{{ mat.tag }}</span>
          </div>
          <h3 class="mat-title">{{ mat.title }}</h3>
          <p v-if="mat.type === 'text'" class="mat-quote">{{ mat.content }}</p>
          <p v-if="mat.desc" class="mat-desc">{{ mat.desc }}</p>
          <a v-if="mat.type === 'link'" :href="safeLink(mat.url)" target="_blank" rel="noopener noreferrer" class="mat-link">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path></svg>
            {{ mat.url }}
          </a>
        </div>
      </div>
      </TransitionGroup>
    </div>

    <div v-if="filteredMaterials.length > displayLimit" class="load-more-container" style="text-align: center; margin-bottom: 24px;">
      <button class="btn-secondary load-more-btn" @click="loadMore" style="padding: 8px 24px; border-radius: 20px;">加载更多素材</button>
    </div>

    <!-- Create Modal -->
    <div class="modal-overlay" v-if="showModal" @click.self="showModal = false">
      <div v-dialog class="modal-content">
        <h2>📥 新增灵感素材</h2>
        <div class="form-group">
          <label>素材标题</label>
          <input type="text" v-model="newMat.title" class="modal-input" autofocus />
        </div>
        <div class="form-group">
          <label>类型</label>
          <select v-model="newMat.type" class="modal-input">
            <option value="text">文本片段</option>
            <option value="image">图片 (输入 URL或色块)</option>
            <option value="link">网页链接</option>
          </select>
        </div>
        <div class="form-group" v-if="newMat.type === 'text'">
          <label>内容</label>
          <textarea v-model="newMat.content" class="modal-input textarea"></textarea>
        </div>
        <div class="form-group" v-if="newMat.type === 'link'">
          <label>URL 链接地址</label>
          <input type="text" v-model="newMat.url" class="modal-input" />
        </div>
        <div class="form-group" v-if="newMat.type === 'image'">
          <label>上传本地图片 (最大 10 MB)</label>
          <input type="file" accept="image/png, image/jpeg, image/webp" @change="handleFileChange" class="modal-input" />
          <div v-if="selectedFile" style="margin-top: 8px; font-size: 12px; color: var(--text-secondary);">已选择: {{ selectedFile.name }} ({{ (selectedFile.size/1024/1024).toFixed(2) }}MB)</div>
        </div>
        <div class="form-group">
          <label>标签</label>
          <select v-model="newMat.tag" class="modal-input">
            <option v-for="tag in tags.slice(1)" :key="tag" :value="tag">{{ tag }}</option>
          </select>
        </div>
        <div class="form-group">
          <label>补充说明 (选填)</label>
          <input type="text" v-model="newMat.desc" class="modal-input" />
        </div>
        <div class="modal-actions">
          <button class="btn-cancel" @click="showModal = false">取消</button>
          <button class="btn-confirm" :disabled="uploading" @click="addMaterial">{{ uploading ? '保存中…' : '保存素材' }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.material-container {
  padding: 32px;
  max-width: 1200px;
  margin: 0 auto;
}

.header-actions {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: 24px;
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
}

.tags-filter {
  display: flex;
  gap: 12px;
  margin-bottom: 32px;
  flex-wrap: wrap;
}

.filter-tag {
  background-color: var(--panel-bg);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  padding: 6px 16px;
  border-radius: 20px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.filter-tag:hover {
  background-color: var(--surface-subtle);
}

.filter-tag.active {
  background-color: var(--text-primary);
  color: white;
  border-color: var(--text-primary);
}

/* Masonry Fallback using CSS columns */
.masonry-grid {
  column-count: 3;
  column-gap: 24px;
}

@media (max-width: 1024px) {
  .masonry-grid { column-count: 2; }
}

@media (max-width: 768px) {
  .masonry-grid { column-count: 1; }
}

.material-card {
  break-inside: avoid;
  background: var(--panel-bg);
  border-radius: 16px;
  overflow: hidden;
  border: 1px solid var(--border-color);
  box-shadow: 0 4px 16px rgba(0,0,0,0.02);
  margin-bottom: 24px;
  transition: transform 0.3s, box-shadow 0.3s;
}

.material-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 24px rgba(0,0,0,0.06);
}

.mat-image {
  height: 160px;
  width: 100%;
}

.mat-content {
  padding: 20px;
}

.mat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.mat-badge {
  font-size: 11px;
  padding: 4px 8px;
  border-radius: 4px;
  font-weight: 600;
}
.mat-badge.image,.mat-badge.text,.mat-badge.link { background-color:var(--surface-subtle); color:var(--text-secondary); }

.mat-tag {
  font-size: 12px;
  color: var(--text-category);
}

.mat-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 8px 0;
}

.mat-quote {
  font-size: 15px;
  color: var(--text-primary);
  font-style: italic;
  line-height: 1.6;
  margin: 0 0 12px 0;
  padding-left: 12px;
  border-left: 3px solid var(--accent-color);
}

.mat-desc {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
  margin: 0;
}

.mat-link {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--accent-color);
  text-decoration: none;
  margin-top: 12px;
  word-break: break-all;
}

.mat-link:hover {
  text-decoration: underline;
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
}

.modal-content h2 { margin-top: 0; font-size: 20px; color: var(--text-primary); }
.form-group { margin-bottom: 16px; }
.form-group label { display: block; margin-bottom: 6px; font-size: 13px; color: var(--text-category); }
.modal-input { width: 100%; padding: 10px; border: 1px solid var(--border-color); border-radius: 8px; font-size: 14px; box-sizing: border-box; }
.modal-input.textarea { height: 80px; resize: vertical; }
.modal-actions { display: flex; justify-content: flex-end; gap: 12px; margin-top: 24px; }
.btn-cancel { padding: 10px 16px; border: none; background: var(--hover-bg); border-radius: 8px; cursor: pointer; }
.btn-confirm { padding: 10px 16px; border: none; background: var(--accent-color); color: white; border-radius: 8px; cursor: pointer; }
</style>
