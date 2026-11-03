<script setup>
import { apiFetch, hasModelCredentials, modelAuthHeaders } from '../api.js'
import { ref, watch, onUnmounted } from 'vue'
import { store, getAgentConfig, activeWorkData } from '../store.js'
import { createWorkTasks } from '../work_tasks.js'
import { parseModelJSON } from '../model_output.js'
const tasks = createWorkTasks(store, activeWorkData)
watch(() => store.activeWorkId, () => { tasks.cancelAll(); showEditModal.value = false; showThreadModal.value = false })
onUnmounted(() => tasks.dispose())

const isGenerating = ref(false)

const generateTwist = async () => {
  if (isGenerating.value) return
  const task = tasks.begin(), work = task.work
  isGenerating.value = true
  try {
    task.assertCurrent()
    const config = getAgentConfig('PlotAgent')
    if (!hasModelCredentials(config)) {
      alert("请先在【AI引擎策略】中配置 API Key 或连接账号！")
      return
    }
    
    const prompt = store.prompts.plot_generate_twist
      .replace(/{title}/g, work.title)
      .replace(/{tags}/g, work.tags.join('/'))

    const baseUrl = config.baseUrl ? config.baseUrl.replace(/\/+$/, '') : 'https://api.openai.com/v1'
    
    const response = await apiFetch('/api/proxy/chat', {
      signal: task.signal,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        url: `${baseUrl}/chat/completions`,
        headers: {
          ...modelAuthHeaders(config),
          'Content-Type': 'application/json'
        },
        body: {
          model: config.modelName || 'gpt-3.5-turbo',
          messages: [{ role: 'system', content: prompt }],
          temperature: 0.8
        }
      })
    })

    if (!response.ok) throw new Error(`请求失败: ${response.status}`)
    const data = await response.json()
    const content = data.choices[0].message.content
    
    const twistData = parseModelJSON(content)
    task.assertCurrent()

    work.plotNodes ||= []
    work.plotNodes.push({
      id: Date.now(),
      type: twistData.type || '反转',
      title: twistData.title || '未知剧情',
      tension: twistData.tension || 80,
      desc: twistData.desc || content,
      isAi: true
    })
  } catch (e) {
    if (task.cancelled) return
    console.error("Twist generation failed", e)
    alert("生成剧情失败！" + e.message)
  } finally {
    task.finish()
    isGenerating.value = false
  }
}

const showEditModal = ref(false)
const isEditingNew = ref(false)
const editingNode = ref(null)
const editForm = ref({ title: '', desc: '', tension: 50, type: '起' })

const showThreadModal = ref(false)
const threadForm = ref({ title: '', desc: '', deadline: 20 })

const addNode = () => {
  editingNode.value = null
  isEditingNew.value = true
  editForm.value = { title: '', desc: '', tension: 50, type: '起' }
  showEditModal.value = true
}

const editNode = (node) => {
  editingNode.value = node
  isEditingNew.value = false
  editForm.value = { 
    title: node.title || '', 
    desc: node.desc || '', 
    tension: node.tension || 50, 
    type: node.type || '起' 
  }
  showEditModal.value = true
}

const confirmEditNode = () => {
  const title = (editForm.value.title || '').trim()
  if (!title) {
    alert('标题不能为空')
    return
  }
  const desc = (editForm.value.desc || '').trim() || '暂无描述'
  const tension = Number(editForm.value.tension) || 50
  
  if (isEditingNew.value) {
    activeWorkData.value.plotNodes.push({
      id: Date.now(),
      title,
      desc,
      tension,
      type: editForm.value.type,
      isAi: false
    })
  } else {
    editingNode.value.title = title
    editingNode.value.desc = desc
    editingNode.value.tension = tension
    editingNode.value.type = editForm.value.type
  }
  showEditModal.value = false
}

const deleteNode = (index) => {
  if (confirm('确定要删除这个剧情节点吗？此操作无法恢复。')) {
    activeWorkData.value.plotNodes.splice(index, 1)
  }
}

const addThread = () => {
  threadForm.value = { title: '', desc: '', deadline: 20 }
  showThreadModal.value = true
}

const confirmThread = () => {
  const title = (threadForm.value.title || '').trim()
  if (!title) {
    alert('伏笔标题不能为空')
    return
  }
  const deadline = Number(threadForm.value.deadline) || 20
  if (!activeWorkData.value.threads) {
    activeWorkData.value.threads = []
  }
  activeWorkData.value.threads.push({
    id: Date.now(),
    title,
    desc: (threadForm.value.desc || '').trim(),
    status: deadline < 5 ? '🚨 濒临遗忘' : '待填坑',
    deadline
  })
  showThreadModal.value = false
}

const deleteThread = (index) => {
  if (confirm('确定要删除这个伏笔吗？')) {
    activeWorkData.value.threads.splice(index, 1)
  }
}
</script>

<template>
  <div class="plot-container">
    <div class="header-actions">
      <div>
        <h2 class="page-title">情节引擎</h2>
        <p class="page-desc">整理故事节点和伏笔，用 AI 探索下一次剧情转折。</p>
      </div>
      <div class="action-buttons">
        <button class="btn-primary" @click="generateTwist" :disabled="isGenerating">
          <svg v-if="!isGenerating" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>
          <svg v-else class="spinner" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="2" x2="12" y2="6"></line><line x1="12" y1="18" x2="12" y2="22"></line><line x1="4.93" y1="4.93" x2="7.76" y2="7.76"></line><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"></line><line x1="2" y1="12" x2="6" y2="12"></line><line x1="18" y1="12" x2="22" y2="12"></line><line x1="4.93" y1="19.07" x2="7.76" y2="16.24"></line><line x1="16.24" y1="7.76" x2="19.07" y2="4.93"></line></svg>
          {{ isGenerating ? 'AI 剧本推演中...' : '生成剧情转折' }}
        </button>
      </div>
    </div>

    <div class="plot-layout">
      <!-- Main Timeline -->
      <div class="timeline-container">
        <div class="timeline-line"></div>
        
        <div 
          class="node-card" 
          v-for="(node, index) in activeWorkData.plotNodes" 
          :key="node.id"
          :class="{ 'ai-generated': node.isAi }"
        >
          <div class="node-marker">
            <span class="node-type">{{ node.type }}</span>
          </div>
          <div class="node-content">
            <div class="node-header">
              <h3 class="node-title">
                {{ node.title }}
                <span v-if="node.isAi" class="ai-badge">✨ AI 推演</span>
              </h3>
              <div class="tension-meter">
                <span class="tension-label">张力</span>
                <div class="tension-bar-bg">
                  <div class="tension-bar" :style="{ width: node.tension + '%' }" :class="{
                    'low': node.tension < 40,
                    'medium': node.tension >= 40 && node.tension < 75,
                    'high': node.tension >= 75
                  }"></div>
                </div>
                <span class="tension-val">{{ node.tension }}</span>
              </div>
            </div>
            <p class="node-desc">{{ node.desc }}</p>
            <div class="node-actions">
              <button class="split-btn" v-if="node.isAi" disabled title="章节拆分尚未接入，请在故事结构中添加细纲">
                ➦ 裂变为章节序列
              </button>
              <button class="icon-btn" @click="editNode(node)" title="修改节点">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
              </button>
              <button class="icon-btn" @click="deleteNode(index)" title="删除节点">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
              </button>
            </div>
          </div>
        </div>

        <div class="add-node-area">
          <button class="add-node-btn" @click="addNode" title="手动添加剧情节点">
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
          </button>
        </div>
      </div>

      <!-- Thread Manager Sidebar -->
      <aside class="thread-manager-panel">
        <div class="thread-header">
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-2 2Zm0 0a2 2 0 0 1-2-2v-9c0-1.1.9-2 2-2h2"></path><path d="M18 14h-8"></path><path d="M15 18h-5"></path><path d="M10 6h8v4h-8V6Z"></path></svg>
          <h3>悬念追踪看板</h3>
        </div>
        <p class="thread-desc">Thread Manager: 追踪伏笔收束进度，临近期限自动干预生成引擎。</p>
        
        <div class="thread-list">
          <div class="thread-item" v-for="(thread, index) in activeWorkData.threads" :key="thread.id" :class="{'thread-danger': thread.deadline < 5}">
            <div class="thread-info">
              <span class="thread-title">{{ thread.title }}</span>
              <div style="display: flex; gap: 8px; align-items: center;">
                <span class="thread-status" v-if="thread.deadline < 5">🚨 濒临遗忘</span>
                <button class="icon-btn-small" @click="deleteThread(index)" title="删除伏笔" style="background:none; border:none; color:var(--text-category); cursor:pointer;">
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                </button>
              </div>
            </div>
            <div class="thread-meta">
              <span>距离收束截止：剩余 {{ thread.deadline }} 章</span>
            </div>
          </div>
          <div class="add-thread-btn" @click="addThread">
            + 埋设新伏笔
          </div>
        </div>
      </aside>
    </div>

    <!-- Edit/Add Node Modal -->
    <div class="modal-overlay" v-if="showEditModal" @click.self="showEditModal = false">
      <div v-dialog class="modal-content" style="width: 500px;">
        <h3>{{ isEditingNew ? '新增剧情节点' : '修改剧情节点' }}</h3>
        <p class="modal-desc">{{ isEditingNew ? '手动插入一段自己构思的剧情发展。' : '调整当前情节的内容和张力属性。' }}</p>
        
        <div class="input-group" style="margin-bottom: 16px;">
          <label style="display:block; margin-bottom: 8px; font-size: 13px; font-weight: 600;">阶段类型</label>
          <select v-model="editForm.type" style="width:100%; padding: 10px; border: 1px solid var(--border-color); border-radius: 6px; outline: none;">
            <option value="起">起</option>
            <option value="承">承</option>
            <option value="转">转</option>
            <option value="合">合</option>
            <option value="反转">反转</option>
            <option value="高潮">高潮</option>
          </select>
        </div>

        <div class="input-group" style="margin-bottom: 16px;">
          <label style="display:block; margin-bottom: 8px; font-size: 13px; font-weight: 600;">节点标题</label>
          <input type="text" v-model="editForm.title" style="width:100%; padding: 10px; border: 1px solid var(--border-color); border-radius: 6px; outline: none; box-sizing: border-box;" placeholder="例如：觉醒的序曲" />
        </div>

        <div class="input-group" style="margin-bottom: 16px;">
          <label style="display:flex; justify-content: space-between; margin-bottom: 8px; font-size: 13px; font-weight: 600;">
            <span>张力值 (Tension)</span>
            <span style="color: var(--primary-color);">{{ editForm.tension }} / 100</span>
          </label>
          <input type="range" v-model="editForm.tension" min="0" max="100" style="width:100%; cursor: pointer;" />
        </div>

        <div class="input-group">
          <label style="display:block; margin-bottom: 8px; font-size: 13px; font-weight: 600;">情节描述</label>
          <textarea v-model="editForm.desc" rows="4" style="width: 100%; padding: 12px; border: 1px solid var(--border-color); border-radius: 8px; resize: vertical; outline: none; box-sizing: border-box; font-family: inherit; line-height: 1.5;"></textarea>
        </div>

        <div style="display: flex; justify-content: flex-end; gap: 12px; margin-top: 24px;">
          <button class="btn-secondary" @click="showEditModal = false">取消</button>
          <button class="btn-primary" @click="confirmEditNode">保存节点</button>
        </div>
      </div>
    </div>

    <!-- Add Thread Modal -->
    <div class="modal-overlay" v-if="showThreadModal" @click.self="showThreadModal = false">
      <div v-dialog class="modal-content" style="width: 400px;">
        <h3>埋设新伏笔</h3>
        <p class="modal-desc">添加一条需要追踪的悬念，系统会监控收束期限。</p>
        
        <div class="input-group" style="margin-bottom: 16px;">
          <label style="display:block; margin-bottom: 8px; font-size: 13px; font-weight: 600;">伏笔标题</label>
          <input type="text" v-model="threadForm.title" style="width:100%; padding: 10px; border: 1px solid var(--border-color); border-radius: 6px; outline: none; box-sizing: border-box;" placeholder="例如：神秘匕首的来历" />
        </div>

        <div class="input-group" style="margin-bottom: 16px;">
          <label style="display:block; margin-bottom: 8px; font-size: 13px; font-weight: 600;">伏笔描述</label>
          <textarea v-model="threadForm.desc" style="width:100%; height: 80px; padding: 10px; border: 1px solid var(--border-color); border-radius: 6px; outline: none; box-sizing: border-box; resize: vertical;"></textarea>
        </div>

        <div class="input-group">
          <label style="display:block; margin-bottom: 8px; font-size: 13px; font-weight: 600;">收束期限（章节数）</label>
          <input type="number" v-model="threadForm.deadline" style="width:100%; padding: 10px; border: 1px solid var(--border-color); border-radius: 6px; outline: none; box-sizing: border-box;" />
        </div>

        <div style="display: flex; justify-content: flex-end; gap: 12px; margin-top: 24px;">
          <button class="btn-secondary" @click="showThreadModal = false">取消</button>
          <button class="btn-primary" @click="confirmThread">保存伏笔</button>
        </div>
      </div>
    </div>

  </div>
</template>

<style scoped>
.plot-container {
  padding: 32px;
  max-width: 1000px;
  margin: 0 auto;
}

.header-actions {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: 40px;
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
  padding: 12px 24px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s;
  border: none;
  background-color: var(--accent-color);
  color: white;
  box-shadow: var(--accent-glow);
}

.btn-primary:hover:not(:disabled) {
  background-color: var(--accent-hover);
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.btn-primary:disabled {
  opacity: 0.7;
  cursor: wait;
}

.timeline-container {
  position: relative;
  padding-left: 40px;
}

.timeline-line {
  position: absolute;
  left: 20px;
  top: 0;
  bottom: 0;
  width: 4px;
  background-color: var(--border-color);
  border-radius: 2px;
}

.node-card {
  position: relative;
  background: var(--panel-bg);
  border-radius: 16px;
  padding: 24px;
  border: 1px solid var(--border-color);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.02);
  margin-bottom: 32px;
  transition: all 0.3s ease;
}

.node-card:hover {
  border-color: var(--border-color);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.04);
}

.node-card.ai-generated {
  border-color: var(--accent-border);
  box-shadow: none;
}

.node-marker {
  position: absolute;
  left: -40px;
  top: 24px;
  transform: translateX(-50%);
  width: 32px;
  height: 32px;
  background-color: var(--panel-bg);
  border: 3px solid var(--accent-color);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2;
  box-shadow: var(--shadow-md);
}

.ai-generated .node-marker {
  border-color: var(--accent-color);
  box-shadow: none;
}

.node-type {
  font-size: 14px;
  font-weight: 700;
  color: var(--accent-color);
}

.ai-generated .node-type {
  color: var(--accent-color);
}

.node-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}

.node-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
  display: flex;
  align-items: center;
  gap: 12px;
}

.ai-badge {
  font-size: 12px;
  background: var(--accent-bg);
  color: var(--accent-color);
  padding: 4px 8px;
  border-radius: 6px;
  font-weight: 600;
}

.tension-meter {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
  max-width: 100%;
  flex-wrap: wrap;
  background: var(--bg-color);
  padding: 8px 16px;
  border-radius: 20px;
}

.tension-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}

.tension-bar-bg {
  width: 100px;
  flex: 1 1 40px;
  height: 6px;
  background-color: var(--border-color);
  border-radius: 3px;
  overflow: hidden;
}

.tension-bar {
  height: 100%;
  border-radius: 3px;
  transition: width 1s ease-out;
}

.tension-bar.low { background-color: var(--accent-color); }
.tension-bar.medium { background-color: var(--accent-color); }
.tension-bar.high { background-color: var(--accent-color); }

.tension-val {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
  width: 24px;
  text-align: right;
}

.node-desc {
  font-size: 15px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin: 0 0 20px 0;
}

.node-actions {
  display: flex;
  gap: 8px;
  border-top: 1px solid var(--border-color);
  padding-top: 16px;
}

.icon-btn {
  background: transparent;
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  cursor: pointer;
  padding: 8px;
  border-radius: 6px;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.icon-btn:hover {
  background-color: var(--bg-color);
  color: var(--accent-color);
}

.split-btn {
  background: var(--panel-bg);
  color: var(--text-secondary);
  border: 1px solid var(--border-color);
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
  font-weight: 500;
  margin-right: 8px;
}

.split-btn:hover {
  background: var(--hover-bg);
  border-color: var(--text-category);
}

.add-node-area {
  display: flex;
  justify-content: center;
  padding: 20px 0;
  position: relative;
  z-index: 2;
}

.add-node-btn {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: var(--panel-bg);
  border: 2px dashed var(--border-color);
  color: var(--text-category);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: 0 4px 12px rgba(0,0,0,0.05);
}

.add-node-btn:hover {
  border-color: var(--accent-color);
  color: var(--accent-color);
  transform: scale(1.1);
}

@keyframes spin {
  100% { transform: rotate(360deg); }
}
.spinner {
  animation: spin 1s linear infinite;
}

.plot-layout {
  display: flex;
  gap: 32px;
}

.timeline-container {
  flex: 1;
}

.thread-manager-panel {
  width: 300px;
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 20px;
  height: fit-content;
  position: sticky;
  top: 24px;
}

.thread-header {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--primary-color);
  margin-bottom: 8px;
}

.thread-header h3 {
  margin: 0;
  font-size: 1.1rem;
}

.thread-desc {
  font-size: 0.8rem;
  color: var(--text-muted);
  margin: 0 0 16px 0;
  line-height: 1.4;
}

.thread-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.thread-item {
  background: var(--bg-color);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 12px;
  border-left: 3px solid var(--primary-color);
}

.thread-danger {
  border-left-color: var(--danger-color);
  background: rgba(239, 68, 68, 0.05);
}

.thread-info {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 8px;
}

.thread-title {
  font-weight: 500;
  font-size: 0.9rem;
  color: var(--text-primary);
}

.thread-status {
  font-size: 0.75rem;
  color: var(--danger-color);
  font-weight: bold;
}

.thread-meta {
  font-size: 0.8rem;
  color: var(--text-muted);
}

.add-thread-btn {
  border: 1px dashed var(--border-color);
  border-radius: 8px;
  padding: 12px;
  text-align: center;
  color: var(--text-secondary);
  font-size: 0.85rem;
  cursor: pointer;
  transition: all 0.2s;
}

.add-thread-btn:hover {
  background: var(--hover-color);
  color: var(--primary-color);
  border-color: var(--primary-color);
}
</style>
