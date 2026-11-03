<script setup>
import UiIcon from './UiIcon.vue'
import { apiFetch, llmFetch, hasModelCredentials, modelAuthHeaders } from '../api.js'
import { ref, computed, watch, onUnmounted } from 'vue'
import { store, activeWorkData, getAgentConfig } from '../store.js'
import { createWorkTasks } from '../work_tasks.js'
import { parseModelJSON } from '../model_output.js'
const tasks = createWorkTasks(store, activeWorkData)
const closeEditors = () => { showEditModal.value = false; showAddModal.value = false }
watch(() => store.activeWorkId, () => { tasks.cancelAll(); closeEditors() })
onUnmounted(() => tasks.dispose())

const showEditModal = ref(false)
const editingItem = ref(null)
const editingCat = ref(null)
const editForm = ref({ name: '', desc: '', type: 'Normal' })
const isEditingNew = ref(false)
const isAiPolishing = ref(false)

const editItem = (cat, item) => {
  if (item.isLocked) return
  editingCat.value = cat
  editingItem.value = item
  editForm.value = { name: item.name, desc: item.desc, type: item.type }
  isEditingNew.value = false
  showEditModal.value = true
}

const activeTab = ref('设定')
watch(activeTab, () => { tasks.cancelAll(); closeEditors() })
const categoryField = tab => ({'设定':'worldview','术语':'terms','时间线':'timeline','最高法则':'rules'})[tab]

const deleteItem = (cat, index) => {
  const item = cat.items[index]
  if (item.isLocked) {
    alert(`设定“${item.name}”已锁定，暂不支持直接删除。`)
    return
  }
  if(confirm('确定要删除此词条吗？')) {
    cat.items.splice(index, 1)
  }
}

const deleteCategory = (cat, index) => {
  if (cat.items.some(item => item.isLocked)) {
    alert(`分类“${cat.title}”包含锁定词条，暂不支持直接删除。`)
    return
  }
  if(confirm(`确定要删除大类 "${cat.title}" 吗？此操作无法恢复。`)) {
    if (activeTab.value === '设定') activeWorkData.value.worldview.splice(index, 1)
    if (activeTab.value === '术语') activeWorkData.value.terms.splice(index, 1)
    if (activeTab.value === '时间线') activeWorkData.value.timeline.splice(index, 1)
    if (activeTab.value === '最高法则') activeWorkData.value.rules = []
  }
}

const addItem = (cat) => {
  if (activeTab.value === '最高法则') { activeWorkData.value.rules ||= []; cat.items = activeWorkData.value.rules }
  editingCat.value = cat
  editingItem.value = null
  editForm.value = { name: '', desc: '', type: activeTab.value === '最高法则' ? 'Rule' : 'Normal' }
  isEditingNew.value = true
  showEditModal.value = true
}

const confirmEditItem = () => {
  if (!editForm.value.name.trim()) {
    alert("词条名称不能为空")
    return
  }
  if (isEditingNew.value) {
    editingCat.value.items.push({
      name: editForm.value.name.trim(),
      desc: editForm.value.desc.trim() || '暂无描述',
      type: editForm.value.type,
      isLocked: false
    })
  } else {
    editingItem.value.name = editForm.value.name.trim()
    editingItem.value.desc = editForm.value.desc.trim()
  }
  showEditModal.value = false
}

const aiPolishItem = async () => {
  if (isAiPolishing.value) return
  const work = activeWorkData.value, form = editForm.value, cat = editingCat.value
  if (!work.id || !cat) return alert('请先选择作品和词条')
  isAiPolishing.value = true
  const config = getAgentConfig('LoreAgent')
  if (!hasModelCredentials(config)) {
    alert("请先在左侧菜单的【AI引擎策略】中配置您的 API Key！")
    isAiPolishing.value = false
    return
  }

  const prompt = store.prompts.worldview_polish_item
    .replace(/{title}/g, work.title)
    .replace(/{tags}/g, work.tags.join('/'))
    .replace(/{category}/g, editingCat.value.title)
    .replace(/{name}/g, editForm.value.name || '未知设定')
    .replace(/{desc}/g, editForm.value.desc || '空')

  const task = tasks.begin()
  const original = form.desc
  try {
    task.assertCurrent()
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
          messages: [{ role: 'user', content: prompt }],
          temperature: 0.85
        }
      })
    })

    if (!response.ok) throw new Error(`API 请求失败: ${response.status}`)

    const data = await response.json()
    task.assertCurrent()
    if (!showEditModal.value || editForm.value !== form || form.desc !== original) return
    const content = data.choices?.[0]?.message?.content
    if (typeof content !== 'string' || !content.trim()) throw new Error('模型未返回有效词条描述')
    form.desc = content.trim()
  } catch (error) {
    if (task.cancelled) return
    alert("AI 脑洞扩写失败：" + error.message)
  } finally {
    task.finish()
    isAiPolishing.value = false
  }
}

const currentData = computed(() => {
  if (activeTab.value === '设定') return activeWorkData.value.worldview || []
  if (activeTab.value === '术语') return activeWorkData.value.terms || []
  if (activeTab.value === '时间线') return activeWorkData.value.timeline || []
  if (activeTab.value === '最高法则') return [
    { id: 999, title: '本源法则与禁忌逻辑锁', icon: '⛔', items: activeWorkData.value.rules || [] }
  ]
  return []
})

const showAddModal = ref(false)
const newCategoryName = ref('')
const isGeneratingCategory = ref(false)

const addCategory = () => {
  if (activeTab.value === '最高法则') { addItem(currentData.value[0]); return }
  newCategoryName.value = ''
  showAddModal.value = true
}

const confirmAddCategory = () => {
  if (newCategoryName.value.trim()) {
    const work = activeWorkData.value, field = categoryField(activeTab.value)
    work[field] ||= []
    work[field].push({
      id: Date.now(),
      title: newCategoryName.value.trim(),
      icon: '✨',
      items: []
    })
    showAddModal.value = false
  }
}

const autoConstructCategory = async () => {
  if (isGeneratingCategory.value) return
  const work = activeWorkData.value, tab = activeTab.value
  if (!work.id) return alert('请先选择作品')
  isGeneratingCategory.value = true
  
  const config = getAgentConfig('LoreAgent')
  if (!hasModelCredentials(config)) {
    alert("请先在左侧菜单的【AI引擎策略】中配置您的 API Key 和 Base URL！")
    isGeneratingCategory.value = false
    return
  }

  const catNameInput = newCategoryName.value.trim() || (activeTab.value === '设定' ? '隐藏势力' : '核心资源')
  
  const systemPrompt = store.prompts.worldview_auto_construct
    .replace(/{title}/g, work.title)
    .replace(/{tags}/g, work.tags.join('/'))
    .replace(/{tab}/g, tab)
    .replace(/{category}/g, catNameInput)

  const task = tasks.begin()
  try {
    task.assertCurrent()
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
          messages: [{ role: 'user', content: systemPrompt }],
          temperature: 0.8
        }
      })
    })

    if (!response.ok) {
      throw new Error(`API 请求失败: ${response.status}`)
    }

    const data = await response.json()
    const content = data.choices[0].message.content
    const parsedItems = parseModelJSON(content, 'array')
    task.assertCurrent()

    const generatedItems = parsedItems.map(item => ({
      name: item.name || '新词条',
      desc: item.desc || '',
      type: tab === '最高法则' ? 'Rule' : 'Normal'
    }))

    const field = categoryField(tab)
    work[field] ||= []
    if (tab === '最高法则') work.rules.push(...generatedItems)
    else work[field].push({
      id: Date.now(),
      title: catNameInput,
      icon: '🔮',
      items: generatedItems
    })
    
    showAddModal.value = false
  } catch (error) {
    if (task.cancelled) return
    alert("大模型请求失败或解析出错，请检查 API 密钥、代理地址或网络环境：\n" + error.message)
  } finally {
    task.finish()
    isGeneratingCategory.value = false
  }
}

const isExpanding = ref({})

const expandItem = async (cat, item) => {
  if (isExpanding.value[item.name]) return
  const work = activeWorkData.value
  if (!work.id) return alert('请先选择作品')
  const config = getAgentConfig('LoreAgent')
  if (!hasModelCredentials(config)) {
    alert("请先在【AI引擎策略】中配置 API Key 或连接账号！")
    return
  }

  const sourceName = item.name
  isExpanding.value[sourceName] = true
  
  const prompt = store.prompts.worldview_expand_item
    .replace(/{title}/g, work.title)
    .replace(/{category}/g, cat.title)
    .replace(/{name}/g, item.name)
    .replace(/{desc}/g, item.desc)

  const task = tasks.begin()
  try {
    task.assertCurrent()
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
        messages: [{ role: 'user', content: prompt }],
        temperature: 0.8
      })
    })

    if (!response.ok) throw new Error(`API 请求失败: ${response.status}`)

    const data = await response.json()
    const content = data.choices[0].message.content
    const parsedItems = parseModelJSON(content, 'array')
    task.assertCurrent()
    if (!cat.items.includes(item)) return

    if (!item.children) {
      item.children = []
    }
    
    parsedItems.forEach(child => {
      item.children.push({
        name: child.name || '新词条',
        desc: child.desc || '',
        type: item.type,
        isLocked: false
      })
    })
  } catch (e) {
    if (task.cancelled) return
    console.error(e)
    alert(`深挖失败，请检查模型配置或网络：${e.message}`)
  } finally {
    task.finish()
    isExpanding.value[sourceName] = false
  }
}
</script>

<template>
  <div class="worldview-container">
    <div class="header-actions">
      <div class="header-left">
        <UiIcon name="globe" :size="23" class="page-heading-icon" />
        <h2 class="page-title">世界观构筑</h2>
      </div>
      <div class="header-right">
        <button class="top-btn" :class="activeTab === '设定' ? 'btn-setting' : 'btn-outline'" @click="activeTab = '设定'">
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16z"></path></svg>
          设定
        </button>
        <button class="top-btn" :class="activeTab === '术语' ? 'btn-setting' : 'btn-outline'" @click="activeTab = '术语'">
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20"></path></svg>
          术语
        </button>
        <button class="top-btn" :class="activeTab === '时间线' ? 'btn-setting' : 'btn-outline'" @click="activeTab = '时间线'">
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
          时间线
        </button>
        <button class="top-btn" :class="activeTab === '最高法则' ? 'btn-setting-danger' : 'btn-outline'" @click="activeTab = '最高法则'">
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>
          最高法则
        </button>
        <button class="top-btn btn-primary" @click="addCategory">
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
          新建
        </button>
      </div>
    </div>

    <div class="categories-grid">
      <div class="category-card" v-for="(cat, catIdx) in currentData" :key="cat.id" :class="{'rule-category': activeTab === '最高法则'}">
        <div class="cat-header" style="justify-content: space-between;">
          <div style="display: flex; align-items: center; gap: 12px;">
            <span class="cat-icon">{{ cat.icon }}</span>
            <h3 class="cat-title">{{ cat.title }} <span v-if="activeTab === '最高法则'" class="rule-badge">IntelligentSentinel 强制覆写</span></h3>
          </div>
          <button v-if="activeTab !== '最高法则'" class="action-btn delete-cat-btn" @click="deleteCategory(cat, catIdx)" title="删除分类" style="color: var(--danger-color);">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"></path><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
          </button>
        </div>
        
        <div class="setting-list" v-if="cat.items.length > 0">
          <div class="setting-item" v-for="(item, idx) in cat.items" :key="idx" :class="{'rule-item': item.type === 'Rule', 'locked-item': item.isLocked}">
            <div class="item-content">
              <h4 class="item-name">
                <span v-if="item.isLocked" title="此设定已被正文引用，受 Sentinel 保护" style="margin-right: 4px; cursor: help;">🔒</span>
                {{ item.name }}
              </h4>
              <p class="item-desc">{{ item.desc }}</p>
              


            </div>
            
            <!-- Derived Sub-items -->
            <div class="sub-items-list" v-if="item.children && item.children.length > 0">
              <div class="sub-item" v-for="(child, cIdx) in item.children" :key="cIdx">
                <div style="display:flex; align-items:flex-start; gap:8px;">
                  <span style="color:var(--primary-color); font-weight:bold; font-size: 14px; margin-top: -2px;">↳</span>
                  <div style="flex:1;">
                    <h5 class="sub-item-name">{{ child.name }}</h5>
                    <p class="sub-item-desc">{{ child.desc }}</p>
                  </div>
                </div>
              </div>
            </div>

            <div class="item-actions">
              <button class="action-btn text-btn" @click="expandItem(cat, item)" :disabled="isExpanding[item.name]" title="衍生深挖" v-if="activeTab !== '最高法则'">
                <span v-if="isExpanding[item.name]">⌛ 挖掘中...</span>
                <span v-else>✨ 深挖衍生词条</span>
              </button>
              <button class="action-btn" @click="editItem(cat, item)" title="编辑" :disabled="item.isLocked" :class="{'disabled-btn': item.isLocked}">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
              </button>
              <button class="action-btn" @click="deleteItem(cat, idx)" :title="item.isLocked ? '已锁定，无法删除' : '删除'" :class="{'disabled-btn': item.isLocked}">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"></path><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
              </button>
            </div>
          </div>
        </div>

        <div class="add-item-zone">
          <button class="add-item-btn" @click="addItem(cat)">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
            添加新词条
          </button>
        </div>
      </div>
    </div>
    <!-- Add Category Modal -->
    <div class="modal-overlay" v-if="showAddModal" @click.self="showAddModal = false">
      <div v-dialog class="modal-content">
        <h3>新建【{{ activeTab }}】大类</h3>
        <p class="modal-desc">为您的世界观添加新的分类，让设定更加清晰。</p>
        
        <div class="input-group">
          <input type="text" v-model="newCategoryName" placeholder="（选填）输入名称，或直接让 AI 发挥..." @keyup.enter="confirmAddCategory" ref="categoryInput" />
        </div>

        <div class="modal-actions">
          <button class="btn-outline" @click="showAddModal = false">取消</button>
          <button class="ui-button ui-button--secondary" @click="confirmAddCategory">建个空类</button>
          <button class="btn-primary" @click="autoConstructCategory" :disabled="isGeneratingCategory" style="display:flex; align-items:center; gap:6px;">
            <svg v-if="isGeneratingCategory" class="spinner" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="2" x2="12" y2="6"></line><line x1="12" y1="18" x2="12" y2="22"></line><line x1="4.93" y1="4.93" x2="7.76" y2="7.76"></line><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"></line><line x1="2" y1="12" x2="6" y2="12"></line><line x1="18" y1="12" x2="22" y2="12"></line><line x1="4.93" y1="19.07" x2="7.76" y2="16.24"></line><line x1="16.24" y1="7.76" x2="19.07" y2="4.93"></line></svg>
            <span v-else>✨</span>
            {{ isGeneratingCategory ? 'AI疯狂构筑中...' : 'AI 一键构筑大类' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Edit/Add Item Modal -->
    <div class="modal-overlay" v-if="showEditModal" @click.self="showEditModal = false">
      <div v-dialog class="modal-content" style="width: 500px;">
        <h3>{{ isEditingNew ? '添加新词条' : '编辑词条' }}</h3>
        <p class="modal-desc" v-if="isEditingNew">在【{{ editingCat?.title }}】下新增世界观设定。</p>
        <p class="modal-desc" v-else>修改当前设定的细节内容。</p>
        
        <div class="input-group" style="margin-bottom: 16px;">
          <label style="display:block; margin-bottom: 8px; font-size: 13px; font-weight: 600; color: var(--text-secondary);">词条名称</label>
          <input type="text" v-model="editForm.name" placeholder="例如：机械飞升、源石共鸣..." style="padding-right: 16px;" />
        </div>

        <div class="input-group">
          <label style="display:flex; justify-content: space-between; margin-bottom: 8px; font-size: 13px; font-weight: 600; color: var(--text-secondary);">
            详细描述
            <button class="text-btn" @click="aiPolishItem" :disabled="isAiPolishing" style="font-size: 13px; color: var(--primary-color); border:none; background:transparent; cursor:pointer; display: flex; align-items: center; gap: 4px;">
              <svg v-if="isAiPolishing" class="spinner" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="2" x2="12" y2="6"></line><line x1="12" y1="18" x2="12" y2="22"></line><line x1="4.93" y1="4.93" x2="7.76" y2="7.76"></line><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"></line><line x1="2" y1="12" x2="6" y2="12"></line><line x1="18" y1="12" x2="22" y2="12"></line><line x1="4.93" y1="19.07" x2="7.76" y2="16.24"></line><line x1="16.24" y1="7.76" x2="19.07" y2="4.93"></line></svg>
              <span v-else>✨</span>
              {{ isAiPolishing ? '推演中...' : 'AI 脑洞扩写' }}
            </button>
          </label>
          <textarea v-model="editForm.desc" rows="5" placeholder="输入设定的详细描述，或者先写个名字，然后点击右上角让 AI 帮您脑补扩写..." style="width: 100%; padding: 12px; border: 1px solid var(--border-color); border-radius: 8px; font-size: 14px; outline: none; box-sizing: border-box; resize: vertical; font-family: inherit; line-height: 1.5;"></textarea>
        </div>

        <div class="modal-actions">
          <button class="btn-outline" @click="showEditModal = false">取消</button>
          <button class="btn-primary" @click="confirmEditItem">保存词条</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.worldview-container {
  padding: 32px;
  max-width: 1400px;
  margin: 0 auto;
}

.header-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 32px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.globe-icon {
  font-size: 28px;
}

.page-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
}

.header-right {
  display: flex;
  flex-wrap: wrap;
  min-width: 0;
  align-items: center;
  gap: 12px;
}

.top-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-setting {
  background-color: var(--accent-bg);
  color: var(--accent-color);
  border: 1px solid var(--accent-border);
}
.btn-setting:hover {
  background-color: var(--accent-bg);
}

.btn-outline {
  background-color: transparent;
  color: var(--text-secondary);
  border: 1px solid transparent;
}
.btn-outline:hover {
  background-color: var(--hover-bg);
  color: var(--text-primary);
}

.action-btn:hover {
  background-color: var(--hover-bg);
  color: var(--primary-color);
}

.action-btn.disabled-btn {
  opacity: 0.5;
  cursor: not-allowed;
  color: var(--text-category);
}

.action-btn.disabled-btn:hover {
  background-color: transparent;
  color: var(--text-category);
}

.delete-cat-btn:hover {
  background-color: var(--danger-bg);
  color: var(--danger-color) !important;
}

.locked-item {
  border: 1px solid var(--border-color);
  background-color: var(--surface-subtle);
}
.locked-item .item-name {
  color: var(--text-primary);
}

.btn-primary {
  background-color: var(--accent-color);
  color: white;
  border: none;
  padding: 8px 20px;
}
.btn-primary:hover {
  background-color: var(--accent-color);
}

.categories-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 24px;
}

.category-card {
  background: var(--panel-bg);
  border-radius: 12px;
  border: 1px solid var(--border-color);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.02);
  padding: 24px;
  display: flex;
  flex-direction: column;
}

.cat-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px dashed var(--border-color);
}

.cat-icon {
  font-size: 20px;
}

.cat-title {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
  color: var(--text-primary);
}

.setting-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.setting-item {
  background-color: var(--hover-bg);
  border-radius: 8px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
  justify-content: space-between;
  align-items: flex-start;
  transition: all 0.2s;
  border: 1px solid transparent;
}

.add-item-zone {
  margin-top: 16px;
  display: flex;
  justify-content: center;
}

.add-item-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  background-color: transparent;
  color: var(--text-secondary);
  border: 1px dashed var(--border-color);
  padding: 10px 24px;
  border-radius: 8px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
  width: 100%;
  justify-content: center;
}

.add-item-btn:hover {
  background-color: var(--hover-color);
  color: var(--primary-color);
  border-color: var(--primary-color);
}

.setting-item:hover {
  border-color: var(--border-color);
}

.item-content {
  flex: 1;
  min-width: 0;
  overflow-wrap: anywhere;
}

.item-actions { display: flex; flex-wrap: wrap; gap: 4px; align-self: flex-end; }

.item-name {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 8px 0;
}

.item-desc {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
  margin-bottom: 12px;
}

.sub-items-list {
  margin-top: 12px;
  margin-bottom: 12px;
  padding-top: 12px;
  padding-left: 8px;
  border-top: 1px dashed var(--border-color);
}

.sub-item {
  margin-bottom: 12px;
}

.sub-item:last-child {
  margin-bottom: 0;
}

.sub-item-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 4px 0;
}

.sub-item-desc {
  font-size: 12px;
  color: var(--text-secondary);
  margin: 0;
  line-height: 1.5;
}

.setting-item:hover .item-actions {
  opacity: 1;
}

.action-btn {
  background: transparent;
  border: none;
  color: var(--text-category);
  padding: 6px;
  cursor: pointer;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.action-btn.text-btn {
  color: var(--accent-color);
  font-size: 13px;
  font-weight: 600;
  padding: 6px 12px;
  background-color: var(--accent-bg);
}

.action-btn:hover {
  color: var(--text-secondary);
  background-color: var(--border-color);
}

.action-btn.text-btn:hover {
  color: var(--accent-hover);
  background-color: var(--accent-bg);
}

.btn-setting-danger {
  background-color: var(--danger-bg);
  color: var(--danger-color);
  border: 1px solid var(--danger-border);
}

.btn-setting-danger:hover {
  background-color: var(--danger-bg);
}

.rule-category {
  border: 1px solid rgba(239, 68, 68, 0.3);
  background: rgba(239, 68, 68, 0.02);
}

.rule-badge {
  font-size: 0.65rem;
  background: var(--danger-color);
  color: white;
  padding: 2px 6px;
  border-radius: 4px;
  margin-left: 8px;
  vertical-align: middle;
}

.rule-item {
  border-left: 4px solid var(--danger-color) !important;
  background: rgba(239, 68, 68, 0.05);
}

.rule-item .item-name {
  color: var(--danger-color);
}

.modal-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.4);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10000;
}

.modal-content {
  background: var(--panel-bg);
  padding: 32px;
  border-radius: 16px;
  width: 400px;
  box-shadow: 0 20px 40px rgba(0,0,0,0.1);
}

.modal-content h3 {
  margin: 0 0 8px 0;
  font-size: 18px;
  color: var(--text-primary);
}

.modal-desc {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0 0 24px 0;
}

.input-group {
  position: relative;
  margin-bottom: 24px;
}

.input-group input {
  width: 100%;
  padding: 12px 16px;
  padding-right: 50px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  font-size: 14px;
  outline: none;
  transition: all 0.2s;
  box-sizing: border-box;
}

.input-group input:focus,
.input-group textarea:focus {
  border-color: var(--primary-color);
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.1);
}

.text-btn:hover:not(:disabled) {
  opacity: 0.8;
  text-decoration: underline;
}

.ai-assist-btn {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  background: transparent;
  border: none;
  color: var(--primary-color);
  cursor: pointer;
  padding: 6px;
  border-radius: 4px;
  transition: all 0.2s;
}

.ai-assist-btn:hover:not(:disabled) {
  background: var(--hover-color);
}

.ai-assist-btn:disabled {
  opacity: 0.5;
  cursor: wait;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.spinner {
  animation: spin 1s linear infinite;
}
@keyframes spin {
  100% { transform: rotate(360deg); }
}
</style>
