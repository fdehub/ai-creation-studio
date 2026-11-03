<script setup>
import { apiFetch, hasModelCredentials, modelAuthHeaders } from '../api.js'
import { ref, computed, watch, onUnmounted } from 'vue'
import { store, getAgentConfig, activeWorkData, flushWork } from '../store.js'
import { createWorkTasks } from '../work_tasks.js'
import { parseModelJSON } from '../model_output.js'
const tasks = createWorkTasks(store, activeWorkData)
watch(() => store.activeWorkId, () => { tasks.cancelAll(); showCharModal.value = false })
onUnmounted(() => tasks.dispose())

const isGenerating = ref(false)
const isScanning = ref(false)
const isBatchExpanding = ref(false)
const showCharModal = ref(false)
const isEditingChar = ref(false)
const editingChar = ref(null)
const charForm = ref({ name: '', faction: '主角', tags: '', description: '' })

const addCharacter = () => {
  editingChar.value = null
  isEditingChar.value = false
  charForm.value = { name: '', faction: '主角', tags: '', description: '' }
  showCharModal.value = true
}

const editCharacter = (char) => {
  editingChar.value = char
  isEditingChar.value = true
  charForm.value = { 
    name: char.name || '', 
    faction: char.faction || '主角', 
    tags: (char.tags || []).join('，'), 
    description: char.description || '' 
  }
  showCharModal.value = true
}

const confirmCharacter = () => {
  const name = (charForm.value.name || '').trim()
  if (!name) {
    alert('角色姓名不能为空')
    return
  }
  const tagsArr = (charForm.value.tags || '').split(/[,，]/).map(t => t.trim()).filter(Boolean)
  
  if (isEditingChar.value && editingChar.value) {
    editingChar.value.name = name
    editingChar.value.faction = charForm.value.faction
    editingChar.value.tags = tagsArr.length ? tagsArr : ['配角']
    editingChar.value.description = charForm.value.description
  } else {
    activeWorkData.value.characters.unshift({
      id: Date.now(),
      name,
      avatarUrl: 'linear-gradient(135deg, #a1c4fd 0%, #c2e9fb 100%)',
      faction: charForm.value.faction,
      tags: tagsArr.length ? tagsArr : ['新角色'],
      description: charForm.value.description
    })
  }
  showCharModal.value = false
}

const generateCharacter = async () => {
  if (isGenerating.value) return
  const task = tasks.begin(), work = task.work
  isGenerating.value = true
  try {
    task.assertCurrent()
    const config = getAgentConfig('LoreAgent')
    if (!hasModelCredentials(config)) {
      alert("请先在【AI引擎策略】中配置 API Key 或连接账号！")
      return
    }

    const prompt = store.prompts.character_generate
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
          'Content-Type': 'application/json',
          ...modelAuthHeaders(config)
        },
        body: {
          model: config.modelName || 'gpt-3.5-turbo',
          messages: [{ role: 'system', content: prompt }],
          temperature: 0.9
        }
      })
    })

    if (!response.ok) throw new Error(`请求失败: ${response.status}`)
    const data = await response.json()
    const content = data.choices[0].message.content
    
    const charData = parseModelJSON(content)
    task.assertCurrent()
    
    const generatedCharacter = {
      id: Date.now(),
      name: charData.name || '神秘新角色',
      avatarUrl: 'linear-gradient(135deg, #fbc2eb 0%, #a6c1ee 100%)',
      faction: charData.faction || '未知',
      tags: charData.tags || ['AI生成', '新角色'],
      description: charData.description || content,
      states: charData.states || []
    }
    
    work.characters ||= []
    work.characters.unshift(generatedCharacter)
  } catch (e) {
    if (task.cancelled) return
    console.error("Character generation failed", e)
    alert("生成角色失败！" + e.message)
  } finally {
    task.finish()
    isGenerating.value = false
  }
}

const scanPastCharacters = async () => {
  if (isScanning.value) return
  const work = activeWorkData.value
  const flatChapters = work?.chapters?.flatMap(v => v.chapters) || []
  const allText = flatChapters.map(c => c.content || '').join('\n\n')
  if (!allText.trim()) {
    alert("暂无章节内容可以扫描")
    return
  }

  const textToScan = allText.slice(-10000)
  
  const existingChars = (work.characters || []).map(c => c.name)
  const config = getAgentConfig('EditorAgent')
  if (!hasModelCredentials(config)) {
    alert("请先在【AI引擎策略】中配置 API Key")
    return
  }
  
  isScanning.value = true
  const task = tasks.begin()
  
  const prompt = `你是一个顶级网文角色提取器。
请阅读下面的小说片段，找出所有在片段中【首次出现的新角色】（包括有具体名字的角色，以及虽无具体名字但具有特定身份且对剧情有推动作用的角色，例如“皇帝”、“太后”、“神秘刺客”等）。
如果角色只有身份/称呼而没有具体名字，请直接将身份称呼作为其 name（例如 name: "皇帝"），**绝对不要自行编造姓名**。
已知当前已有的角色有：${existingChars.join('、')}。
如果片段中出现了不属于上述列表中的新角色，请推断他们的阵营（主角、反派、配角）和简单的身份背景，并严格按照以下 JSON 数组格式输出：
[
  {
    "name": "角色名字",
    "faction": "主角|反派|配角",
    "tags": ["标签1", "标签2"],
    "description": "身份背景或性格描述（50字内）"
  }
]
如果没有新角色，请输出空数组 []。
不要输出任何其他字符。`

  try {
    task.assertCurrent()
    const endpoint = config.baseUrl 
      ? config.baseUrl.replace(/\/$/, '') + '/chat/completions'
      : 'https://api.openai.com/v1/chat/completions'
      
    const response = await apiFetch('/api/proxy/chat', {
      signal: task.signal,
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: endpoint,
        headers: {
          'Content-Type': 'application/json',
          ...modelAuthHeaders(config)
        },
        body: {
          model: config.modelName || 'gpt-3.5-turbo',
          messages: [
            { role: 'system', content: prompt },
            { role: 'user', content: textToScan }
          ],
          temperature: 0.1
        }
      })
    })

    if (!response.ok) throw new Error("API 请求失败")
    const json = await response.json()
    const content = json.choices?.[0]?.message?.content || '[]'
    
    const newChars = parseModelJSON(content, 'array')
    task.assertCurrent()
    let addedCount = 0
    if (Array.isArray(newChars) && newChars.length > 0) {
      newChars.forEach(char => {
        if (!existingChars.includes(char.name) && char.name) {
          work.characters ||= []
          work.characters.unshift({
            id: Date.now() + Math.random(),
            name: char.name,
            avatarUrl: 'linear-gradient(135deg, #a1c4fd 0%, #c2e9fb 100%)',
            faction: char.faction || '配角',
            tags: char.tags || ['前传遗漏'],
            description: char.description || '',
            states: [
              { chapterRange: [1, 100], stats: '未知', equips: '未知' }
            ]
          })
          existingChars.push(char.name)
          addedCount++
        }
      })
    }
    alert(`最近 ${textToScan.length} 字扫描完成，新增 ${addedCount} 个角色。`)
  } catch (e) {
    if (task.cancelled) return
    console.error('Failed to scan characters:', e)
    alert("扫描失败: " + e.message)
  } finally {
    task.finish()
    isScanning.value = false
  }
}

const isExpanding = ref({})

const expandCharacter = async (char, silent = false) => {
  if (isExpanding.value[char.name]) return false
  const config = getAgentConfig('PlotAgent')
  if (!hasModelCredentials(config)) {
    alert("请先在【AI引擎策略】中配置 API Key 或连接账号！")
    return false
  }

  isExpanding.value[char.name] = true
  const task = tasks.begin(), work = task.work
  const source = { name:char.name, description:char.description }
  try {
    task.assertCurrent()
    if (!work.characters?.includes(char)) return false
    const prompt = store.prompts.character_expand
      .replace(/{title}/g, work.title)
      .replace(/{name}/g, char.name)
      .replace(/{faction}/g, char.faction)
      .replace(/{description}/g, char.description)

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
          'Content-Type': 'application/json',
          ...modelAuthHeaders(config)
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
    task.assertCurrent()
    if (!work.characters?.includes(char) || char.name !== source.name || char.description !== source.description) throw new Error('角色资料已修改，未覆盖你的编辑')
    if (typeof content !== 'string' || !content.trim()) throw new Error('模型未返回有效角色描述')
    char.description = content
    return true
  } catch (e) {
    if (!task.cancelled && !silent) alert(`深度挖掘失败: ${e.message}`)
    return false
  } finally {
    task.finish()
    isExpanding.value[source.name] = false
  }
}

const batchExpandCharacters = async () => {
  if (isBatchExpanding.value) return
  const charsToExpand = (activeWorkData.value.characters || []).filter(c => !c.description || c.description.length < 100)
  if (charsToExpand.length === 0) {
    alert("当前所有角色的背景字数均已达标（>100字），暂无需要自动补全的角色。")
    return
  }
  
  if (!confirm(`找到 ${charsToExpand.length} 个背景单薄的待深挖角色。是否开始逐个排队进行 AI 深挖？（已完善的核心角色将被跳过）`)) {
    return
  }
  
  isBatchExpanding.value = true
  const task = tasks.begin()
  let successCount = 0
  try {
    for (const char of charsToExpand) {
      task.assertCurrent()
      if (await expandCharacter(char, true)) successCount++
      // 稍微停顿 500ms 避免过快请求
      await new Promise(resolve => setTimeout(resolve, 500))
    }
    task.assertCurrent()
    alert(`批量深挖结束：成功 ${successCount} 个，失败或跳过 ${charsToExpand.length - successCount} 个。`)
  } catch (e) {
    if (task.cancelled) return
    console.error("Batch expand failed", e)
    alert("批量深挖过程中遇到问题，已终止排队。")
  } finally {
    task.finish()
    isBatchExpanding.value = false
  }
}

const deleteCharacter = async (charId) => {
  if (!confirm('确定删除该角色吗？此操作不可逆！')) return
  
  // 保存角色变更后由后端重建该作品的检索索引。
  try {
    const work = activeWorkData.value
    const index = work.characters.findIndex(c => c.id === charId)
    if (index !== -1) {
      work.characters.splice(index, 1)
      await flushWork(work.id)
      alert('角色已删除，作品检索索引已同步更新。')
    }
  } catch (err) {
    alert('级联删除失败，请联系管理员！')
  }
}


const currentChapterIndex = ref(1)

const currentFilter = ref('全部')
const filterOptions = ['全部', '主角', '反派', '配角', '未知']

const filteredCharacters = computed(() => {
  const chars = activeWorkData.value?.characters || []
  if (currentFilter.value === '全部') return chars
  return chars.filter(c => c.faction === currentFilter.value)
})

const getActiveState = (char) => {
  if (!char.states || char.states.length === 0) return null
  // Find the state that encompasses the current chapter
  const active = char.states.find(s => currentChapterIndex.value >= s.chapterRange[0] && currentChapterIndex.value <= s.chapterRange[1])
  // Fallback to the latest state if out of bounds
  return active || char.states[char.states.length - 1]
}

const showRelationshipGraph = ref(false)
const zoomScale = ref(1)
const panX = ref(0)
const panY = ref(0)
const isDragging = ref(false)
const dragStartX = ref(0)
const dragStartY = ref(0)

const startDrag = (e) => {
  isDragging.value = true
  dragStartX.value = e.clientX - panX.value
  dragStartY.value = e.clientY - panY.value
}

const onDrag = (e) => {
  if (!isDragging.value) return
  panX.value = e.clientX - dragStartX.value
  panY.value = e.clientY - dragStartY.value
}

const stopDrag = () => {
  isDragging.value = false
}

const resetView = () => {
  zoomScale.value = 1
  panX.value = 0
  panY.value = 0
}

const handleWheel = (e) => {
  e.preventDefault()
  if (e.deltaY < 0) {
    zoomScale.value = Math.min(3, zoomScale.value + 0.1)
  } else {
    zoomScale.value = Math.max(0.5, zoomScale.value - 0.1)
  }
}

const orbitalNodes = computed(() => {
  const chars = activeWorkData.value?.characters || []
  if (chars.length < 2) return []
  
  const main = chars[0]
  const others = chars.slice(1)
  const nodes = []
  
  nodes.push({
    ...main,
    isMain: true,
    x: 50,
    y: 50
  })
  
  const count = others.length
  others.forEach((char, index) => {
    const angle = (index / count) * Math.PI * 2 - Math.PI / 2
    nodes.push({
      ...char,
      isMain: false,
      x: Math.cos(angle),
      y: Math.sin(angle)
    })
  })
  
  return nodes
})
</script>

<template>
  <div class="workshop-container">
    <div class="header-actions">
      <div>
        <h2 class="page-title">
          人物工坊 <span class="tag-es" style="font-size: 0.5em; vertical-align: middle;">角色档案</span>
          <span class="char-count" style="font-size: 0.6em; background: rgba(0,0,0,0.05); padding: 2px 8px; border-radius: 12px; margin-left: 12px; color: var(--text-light); font-weight: normal; vertical-align: middle;">
            共 {{ activeWorkData?.characters?.length || 0 }} 个角色
          </span>
        </h2>
        <p class="page-desc">管理您的核心角色，控制动态战力时间轴，并使用 AI 激发全新的人物设定灵感。</p>
      </div>
      <div class="action-buttons">
        <button class="btn-secondary" @click="showRelationshipGraph = !showRelationshipGraph">
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3"></circle><circle cx="6" cy="12" r="3"></circle><circle cx="18" cy="19" r="3"></circle><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line></svg>
          {{ showRelationshipGraph ? '关闭图谱' : '羁绊图谱' }}
        </button>
        <button class="btn-secondary" @click="addCharacter">
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
          手动创建角色
        </button>
        <button class="btn-secondary" @click="scanPastCharacters" :disabled="isScanning">
          <svg v-if="!isScanning" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
          <svg v-else class="spinner" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="2" x2="12" y2="6"></line><line x1="12" y1="18" x2="12" y2="22"></line><line x1="4.93" y1="4.93" x2="7.76" y2="7.76"></line><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"></line><line x1="2" y1="12" x2="6" y2="12"></line><line x1="18" y1="12" x2="22" y2="12"></line><line x1="4.93" y1="19.07" x2="7.76" y2="16.24"></line><line x1="16.24" y1="7.76" x2="19.07" y2="4.93"></line></svg>
          {{ isScanning ? '扫描中...' : '扫描遗漏角色' }}
        </button>
        <button class="btn-secondary" @click="batchExpandCharacters" :disabled="isBatchExpanding || isGenerating || isScanning" style="background:var(--accent-bg); color:var(--accent-color); border:1px solid var(--accent-border);">
          <svg v-if="!isBatchExpanding" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>
          <svg v-else class="spinner" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="2" x2="12" y2="6"></line><line x1="12" y1="18" x2="12" y2="22"></line><line x1="4.93" y1="4.93" x2="7.76" y2="7.76"></line><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"></line><line x1="2" y1="12" x2="6" y2="12"></line><line x1="18" y1="12" x2="22" y2="12"></line><line x1="4.93" y1="19.07" x2="7.76" y2="16.24"></line><line x1="16.24" y1="7.76" x2="19.07" y2="4.93"></line></svg>
          {{ isBatchExpanding ? '排队深挖中...' : '一键批量深挖' }}
        </button>
        <button class="btn-primary" @click="generateCharacter" :disabled="isGenerating">
          <svg v-if="!isGenerating" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path><polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline><line x1="12" y1="22.08" x2="12" y2="12"></line></svg>
          <svg v-else class="spinner" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="2" x2="12" y2="6"></line><line x1="12" y1="18" x2="12" y2="22"></line><line x1="4.93" y1="4.93" x2="7.76" y2="7.76"></line><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"></line><line x1="2" y1="12" x2="6" y2="12"></line><line x1="18" y1="12" x2="22" y2="12"></line><line x1="4.93" y1="19.07" x2="7.76" y2="16.24"></line><line x1="16.24" y1="7.76" x2="19.07" y2="4.93"></line></svg>
          {{ isGenerating ? 'AI 正在推演...' : 'AI 灵感生成' }}
        </button>
      </div>
    </div>

    <!-- Global Timeline Slider -->
    <div class="global-timeline glass-panel">
      <div class="timeline-header">
        <h4>角色状态时间轴</h4>
        <span class="chapter-indicator">当前章节： <b>第 {{ currentChapterIndex }} 章</b></span>
      </div>
      <input type="range" v-model.number="currentChapterIndex" min="1" max="100" class="ui-range">
      <p class="timeline-desc">拖动滑块，查看角色在对应章节的能力与装备。可在角色档案中补充各阶段的状态。</p>
    </div>

    <!-- Relationship Graph (CSS Mock) -->
    <div class="relationship-graph-panel glass-panel" v-if="showRelationshipGraph">
      <div class="graph-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
        <h4 style="margin: 0;">🕸️ 社交羁绊力场图 (Relationship Graph)</h4>
        <div class="zoom-controls" style="display: flex; align-items: center; gap: 8px; background: rgba(0,0,0,0.05); padding: 4px 8px; border-radius: 8px;">
          <button @click="zoomScale = Math.max(0.5, zoomScale - 0.1)" class="more-btn" style="padding: 2px 6px;" title="缩小">➖</button>
          <span style="font-size: 12px; color: var(--text-secondary); min-width: 40px; text-align: center;">{{ Math.round(zoomScale * 100) }}%</span>
          <button @click="zoomScale = Math.min(3, zoomScale + 0.1)" class="more-btn" style="padding: 2px 6px;" title="放大">➕</button>
          <button @click="resetView" class="more-btn" style="padding: 2px 6px;" title="重置">↺</button>
        </div>
      </div>
      <div class="css-graph-mock" v-if="orbitalNodes.length >= 2" 
           :style="{ overflow: 'hidden', position: 'relative', cursor: isDragging ? 'grabbing' : 'grab' }"
           @mousedown="startDrag"
           @mousemove="onDrag"
           @mouseup="stopDrag"
           @mouseleave="stopDrag"
           @wheel.prevent="handleWheel">
        <div class="graph-zoom-wrapper" :style="{ transform: `translate(${panX}px, ${panY}px) scale(${zoomScale})`, width: '100%', height: '100%', transformOrigin: 'center center', transition: isDragging ? 'none' : 'transform 0.2s ease-out', position: 'absolute', top: 0, left: 0 }">
          <svg class="graph-edges" width="100%" height="100%" style="overflow: visible;">
          <template v-for="node in orbitalNodes" :key="'edge-'+node.id">
            <line v-if="!node.isMain"
                  x1="50%" y1="50%" 
                  :x2="`calc(50% + ${node.x * 250}px)`" :y2="`calc(50% + ${node.y * 150}px)`" 
                  :stroke="node.faction === '反派' ? 'var(--danger-color)' : 'var(--text-category)'" 
                  stroke-width="2" 
                  :stroke-dasharray="node.faction === '反派' ? '4' : '0'" 
                  class="edge-anim"></line>
          </template>
        </svg>

        <div v-for="node in orbitalNodes" :key="'node-'+node.id"
             class="graph-node"
             :class="{'main-node': node.isMain, 'enemy-node': node.faction === '反派', 'ally-node': node.faction !== '反派' && !node.isMain}"
             :style="{ left: node.isMain ? '50%' : `calc(50% + ${node.x * 250}px)`, top: node.isMain ? '50%' : `calc(50% + ${node.y * 150}px)`, transform: 'translate(-50%, -50%)', position: 'absolute', margin: 0 }">
          <div class="node-avatar" :style="{ background: node.avatarUrl || (node.faction==='反派' ? 'linear-gradient(135deg, #1f1c2c 0%, #928dab 100%)' : (node.isMain ? 'linear-gradient(135deg, #f6d365 0%, #fda085 100%)' : 'linear-gradient(135deg, #84fab0 0%, #8fd3f4 100%)')) }"></div>
          <span>{{ node.name }}</span>
        </div>

        <template v-for="node in orbitalNodes" :key="'label-'+node.id">
          <div v-if="!node.isMain"
               class="edge-label"
               :class="{'label-enemy': node.faction === '反派', 'label-ally': node.faction !== '反派'}"
               :style="{ left: `calc(50% + ${node.x * 125}px)`, top: `calc(50% + ${node.y * 75}px)`, transform: 'translate(-50%, -50%)', position: 'absolute' }">
            {{ node.faction === '反派' ? '宿敌' : '羁绊' }}
          </div>
        </template>
        </div>
      </div>
      <div v-else style="padding: 40px; text-align: center; color: var(--text-tertiary);">
        需至少拥有2名核心角色方能生成羁绊力场
      </div>
    </div>

    <!-- 角色分类过滤器 -->
    <div class="filter-tabs" style="display: flex; gap: 8px; margin-bottom: 24px;">
      <button 
        v-for="opt in filterOptions" 
        :key="opt"
        @click="currentFilter = opt"
        class="filter-btn"
        :class="{ active: currentFilter === opt }"
        style="padding: 6px 16px; border-radius: 20px; border: 1px solid var(--border-color); background: var(--panel-bg); color: var(--text-secondary); font-size: 13px; cursor: pointer; transition: all 0.2s;"
      >
        {{ opt }}
      </button>
    </div>

    <div class="characters-grid">
      <TransitionGroup name="list">
        <div class="character-card glass-panel" v-for="char in filteredCharacters" :key="char.id">
          <div class="card-header">
            <div class="avatar" :style="{ background: char.avatarUrl }"></div>
            <div class="char-info">
              <h3 class="char-name">{{ char.name }}</h3>
              <span class="char-role" :class="{
                'role-main': char.faction === '主角',
                'role-villain': char.faction === '反派',
                'role-sub': char.faction === '配角',
                'role-unknown': char.faction === '未知'
              }">{{ char.faction }}</span>
            </div>
            <div style="display:flex; gap: 4px;">
              <button class="more-btn" @click="editCharacter(char)" title="修改角色设定" style="color: var(--text-secondary); background: none; border: none; cursor: pointer; padding: 4px; border-radius: 4px;">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
              </button>
              <button class="more-btn delete-icon-btn" @click="deleteCharacter(char.id)" title="彻底删除该角色">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"></path><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path></svg>
              </button>
            </div>
          </div>
          <div class="char-tags">
            <span class="tag" v-for="tag in char.tags" :key="tag">{{ tag }}</span>
          </div>
          
          <div class="state-tracker" v-if="getActiveState(char)">
            <div class="state-row">
              <span class="state-label">当前境界:</span>
              <span class="state-val">{{ getActiveState(char).stats }}</span>
            </div>
            <div class="state-row">
              <span class="state-label">核心装备:</span>
              <span class="state-val">{{ getActiveState(char).equips }}</span>
            </div>
          </div>
          
          <p class="char-desc">{{ char.description || '暂无详细描述...' }}</p>
          <div class="card-footer">
            <button class="view-btn" @click="expandCharacter(char)" :disabled="isExpanding[char.name]">
              <span v-if="isExpanding[char.name]">⌛ AI深度推演中...</span>
              <span v-else>✨ AI 深挖背景与关系网</span>
            </button>
          </div>
        </div>
      </TransitionGroup>
    </div>

    <!-- Character Add/Edit Modal -->
    <div class="modal-overlay" v-if="showCharModal" @click.self="showCharModal = false" style="position:fixed; top:0; left:0; right:0; bottom:0; background:rgba(15,23,42,0.4); display:flex; align-items:center; justify-content:center; z-index: 1000; backdrop-filter: blur(4px);">
      <div v-dialog class="modal-content" style="background:var(--panel-bg); width: 450px; border-radius: 12px; padding: 32px; box-shadow: 0 10px 25px rgba(0,0,0,0.1);">
        <h3 style="margin: 0 0 8px 0; font-size: 18px; color: var(--text-primary);">{{ isEditingChar ? '修改角色设定' : '手动新建角色' }}</h3>
        <p style="margin: 0 0 24px 0; font-size: 14px; color: var(--text-secondary);">编辑角色基础属性卡片。</p>
        
        <div style="margin-bottom: 16px;">
          <label style="display:block; margin-bottom: 8px; font-size: 13px; font-weight: 600; color:var(--text-secondary);">角色姓名</label>
          <input type="text" v-model="charForm.name" style="width:100%; padding: 10px; border: 1px solid var(--border-color); border-radius: 6px; outline: none; box-sizing: border-box;" placeholder="例如：林星火" />
        </div>

        <div style="margin-bottom: 16px;">
          <label style="display:block; margin-bottom: 8px; font-size: 13px; font-weight: 600; color:var(--text-secondary);">阵营/身份</label>
          <select v-model="charForm.faction" style="width:100%; padding: 10px; border: 1px solid var(--border-color); border-radius: 6px; outline: none; box-sizing: border-box;">
            <option value="主角">主角 (Main)</option>
            <option value="反派">反派 (Villain)</option>
            <option value="配角">配角 (Support)</option>
            <option value="未知">未知 (Unknown)</option>
          </select>
        </div>

        <div style="margin-bottom: 16px;">
          <label style="display:block; margin-bottom: 8px; font-size: 13px; font-weight: 600; color:var(--text-secondary);">角色标签（用逗号隔开）</label>
          <input type="text" v-model="charForm.tags" style="width:100%; padding: 10px; border: 1px solid var(--border-color); border-radius: 6px; outline: none; box-sizing: border-box;" placeholder="例如：坚韧，领袖，异能觉醒" />
        </div>

        <div style="margin-bottom: 16px;">
          <label style="display:block; margin-bottom: 8px; font-size: 13px; font-weight: 600; color:var(--text-secondary);">角色详细设定/小传</label>
          <textarea v-model="charForm.description" style="width:100%; height: 100px; padding: 10px; border: 1px solid var(--border-color); border-radius: 6px; outline: none; box-sizing: border-box; resize: vertical;" placeholder="在此输入人物的外貌特征、背景故事、性格弱点等..."></textarea>
        </div>

        <div style="display: flex; justify-content: flex-end; gap: 12px; margin-top: 24px;">
          <button @click="showCharModal = false" style="padding: 8px 16px; border: 1px solid var(--border-color); border-radius: 6px; background: var(--panel-bg); cursor: pointer; color:var(--text-secondary); font-size: 14px;">取消</button>
          <button class="ui-button ui-button--primary" @click="confirmCharacter">保存角色</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.workshop-container {
  padding: 32px;
  max-width: 1400px;
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

.action-buttons {
  display: flex;
  gap: 16px;
}

.btn-primary, .btn-secondary {
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
}

.btn-primary {
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
  cursor: not-allowed;
}

.btn-secondary {
  background-color: var(--panel-bg);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
  box-shadow: 0 2px 4px rgba(0,0,0,0.02);
}

.btn-secondary:hover {
  background-color: var(--surface-subtle);
  border-color: var(--border-color);
}

.filter-btn:hover {
  background: var(--surface-subtle) !important;
  color: var(--text-primary) !important;
  border-color: var(--border-color) !important;
}
.filter-btn.active {
  background: var(--text-primary) !important;
  color: white !important;
  border-color: var(--text-primary) !important;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.15);
}

.characters-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 24px;
}

.character-card {
  background: var(--panel-bg);
  border-radius: 16px;
  padding: 24px;
  border: 1px solid var(--border-color);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.02);
  transition: all 0.3s ease;
  display: flex;
  flex-direction: column;
}

.character-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 24px rgba(0, 0, 0, 0.06);
  border-color: var(--border-color);
}

.card-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
}

.avatar {
  width: 64px;
  height: 64px;
  border-radius: 16px;
  box-shadow: 0 4px 10px rgba(0,0,0,0.1);
}

.char-info {
  flex: 1;
}

.char-name {
  font-size: 18px;
  font-weight: 700;
  margin: 0 0 6px 0;
  color: var(--text-primary);
}

.char-role {
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 20px;
  font-weight: 600;
}

.role-main { background-color:var(--accent-bg); color:var(--accent-color); }
.role-villain,.role-sub { background-color:var(--surface-subtle); color:var(--text-secondary); }
.role-unknown { background-color: var(--hover-bg); color: var(--text-secondary); }

.more-btn {
  background: transparent;
  border: none;
  color: var(--text-category);
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  transition: background 0.2s;
}

.more-btn:hover {
  background: var(--hover-bg);
  color: var(--text-primary);
}

.char-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}

.tag {
  font-size: 12px;
  background-color: var(--bg-color);
  color: var(--text-secondary);
  padding: 4px 10px;
  border-radius: 6px;
  border: 1px solid var(--border-color);
}

.char-desc {
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin: 0 0 24px 0;
  flex: 1;
}

.card-footer {
  border-top: 1px solid var(--border-color);
  padding-top: 16px;
}

.view-btn {
  width: 100%;
  background: transparent;
  border: none;
  color: var(--accent-color);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  padding: 8px;
  border-radius: 6px;
  transition: background 0.2s;
}

.view-btn:hover:not(:disabled) {
  background: var(--accent-bg);
}

.view-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

@keyframes spin {
  100% { transform: rotate(360deg); }
}
.spinner {
  animation: spin 1s linear infinite;
}
.tag-es {
  background: var(--accent-color);
  color: white;
  padding: 2px 6px;
  border-radius: 4px;
}

.global-timeline {
  margin-bottom: 32px;
  padding: 20px;
  border-radius: 12px;
}

.timeline-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.timeline-header h4 {
  margin: 0;
  color: var(--text-primary);
  font-size: 1rem;
}

.chapter-indicator {
  font-size: 0.9rem;
  color: var(--primary-color);
  background: var(--surface-subtle);
  padding: 4px 10px;
  border-radius: 20px;
  border: 1px solid var(--border-color);
}

.ui-range {
  width: 100%;
  margin-bottom: 12px;
  accent-color: var(--primary-color);
}

.timeline-desc {
  font-size: 0.85rem;
  color: var(--text-muted);
  margin: 0;
}

.relationship-graph-panel {
  margin-bottom: 32px;
  padding: 20px;
  border-radius: 12px;
  min-height: 450px;
  display: flex;
  flex-direction: column;
}

.graph-header h4 {
  margin: 0 0 16px 0;
  color: var(--text-primary);
  font-size: 1rem;
}

.css-graph-mock {
  flex: 1;
  position: relative;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
  overflow: hidden;
}

.graph-node {
  position: absolute;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  z-index: 2;
  transform: translate(-50%, -50%);
}

.node-avatar {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  border: 2px solid var(--border-color);
  box-shadow: 0 0 15px rgba(255,255,255,0.1);
}

.graph-node span {
  font-size: 0.8rem;
  color: #fff;
  background: rgba(0,0,0,0.6);
  padding: 2px 6px;
  border-radius: 4px;
}

.main-node { top: 50%; left: 50%; }
.enemy-node { top: 20%; left: 20%; }
.ally-node { top: 20%; left: 80%; }

.graph-edges {
  position: absolute;
  top: 0; left: 0;
  z-index: 1;
}

.edge-anim {
  animation: dash 30s linear infinite;
}

@keyframes dash {
  to {
    stroke-dashoffset: -1000;
  }
}

.edge-label {
  position: absolute;
  font-size: 0.7rem;
  padding: 2px 6px;
  border-radius: 4px;
  z-index: 2;
  font-weight: bold;
}

.label-enemy {
  top: 35%; left: 35%;
  transform: translate(-50%, -50%);
  background: var(--danger-bg);
  color: var(--danger-color);
  border: 1px solid var(--danger-border);
}

.label-ally {
  top: 35%; left: 65%;
  transform: translate(-50%, -50%);
  background: var(--surface-subtle);
  color: var(--text-secondary);
  border: 1px solid var(--border-color);
}

.state-tracker {
  background: var(--surface-subtle);
  border-radius: 6px;
  padding: 10px;
  margin-bottom: 16px;
  border-left: 3px solid var(--primary-color);
}

.state-row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
  font-size: 0.85rem;
}

.state-row:last-child {
  margin-bottom: 0;
}

.state-label {
  color: var(--text-muted);
}

.state-val {
  color: var(--primary-color);
  font-weight: 500;
}
</style>
