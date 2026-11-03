<script setup>
import { llmFetch, hasModelCredentials, modelAuthHeaders } from '../api.js'
import { ref, onUnmounted } from 'vue'
import { parseModelJSON } from '../model_output.js'
import CreatorOverview from './CreatorOverview.vue'
import { store, getAgentConfig, backendAPI } from '../store.js'

// Tag data
const genres = ['言情', '现实情感', '悬疑', '惊悚', '科幻', '武侠', '脑洞', '太空歌剧', '赛博朋克', '游戏', '仙侠', '历史', '玄幻', '奇幻']
const moreGenres = ['都市', '军事', '电竞', '体育', '现实', '诸天无限', '快穿']
const readers = ['男频', '女频', '全频']
const perspectives = ['第一人称', '第三人称']
const lengths = ['短篇小说', '长篇小说']

// State
const activeGenre = ref('科幻')
const activeReader = ref('女频')
const activePerspective = ref('第三人称')
const activeLength = ref('长篇小说')
const promptText = ref('')
const instructionText = ref('')
const showMoreDropdown = ref(false)

const selectGenre = (g) => activeGenre.value = g
const selectReader = (r) => activeReader.value = r
const selectPerspective = (p) => activePerspective.value = p
const selectLength = (l) => activeLength.value = l

const toggleDropdown = () => {
  showMoreDropdown.value = !showMoreDropdown.value
}

const generateStep = ref('')
let generationAbort = null
onUnmounted(() => generationAbort?.abort())

const callLLM = async (prompt, config) => {
  const signal = generationAbort?.signal
  if (signal?.aborted) throw new DOMException('已停止等待', 'AbortError')
  const baseUrl = config.baseUrl ? config.baseUrl.replace(/\/+$/, '') : 'https://api.openai.com/v1'
  const response = await llmFetch(`${baseUrl}/chat/completions`, {
    signal,
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...modelAuthHeaders(config)
    },
    body: JSON.stringify({
      model: config.modelName || 'gpt-3.5-turbo',
      messages: [{ role: 'system', content: prompt }],
      temperature: 0.9
    })
  })
  if (!response.ok) throw new Error(`请求失败: ${response.status}`)
  const data = await response.json()
  const content = data.choices[0].message.content
  if (signal?.aborted) throw new DOMException('已停止等待', 'AbortError')
  if (typeof content !== 'string' || !content.trim()) throw new Error('模型没有返回有效内容')
  try {
    const jsonMatch = content.match(/```json\n([\s\S]*?)\n```/)
    const rawJson = jsonMatch ? jsonMatch[1] : content
    const parsed = JSON.parse(rawJson)
    return parseModelJSON(rawJson, Array.isArray(parsed) ? 'array' : 'object')
  } catch(e) {
    if (/^[\[{]|^```/.test(content.trim()) || /^(null|true|false|\d+)\s*$/.test(content.trim())) throw new Error('模型返回的数据结构无效')
    return content // return raw string if not json
  }
}

const handleGenerate = async () => {
  if (generateStep.value) return
  
  const config = getAgentConfig('EditorAgent')
  if (!hasModelCredentials(config)) {
    alert("请先在【AI引擎策略】中配置 API Key 或连接账号！")
    return
  }

  const defaultIdea = "一个普通外卖员发现自己拥有超能力，从此卷入一场外太空阴谋..."
  const baseUserPrompt = promptText.value.trim() || defaultIdea
  const userInstruction = instructionText.value.trim()
  
  const userPrompt = userInstruction 
    ? `${baseUserPrompt}\n【全局文风与特殊指令】：${userInstruction}`
    : baseUserPrompt

  generationAbort = new AbortController()
  try {
    // 1. Book Generate
    generateStep.value = '正在构思书名与简介...'
    const bookPrompt = store.prompts.book_generate
      .replace(/{genre}/g, activeGenre.value)
      .replace(/{audience}/g, activeReader.value)
      .replace(/{perspective}/g, activePerspective.value)
      .replace(/{length}/g, activeLength.value)
      .replace(/{prompt}/g, userPrompt)

    let bookData = await callLLM(bookPrompt, config)
    if (typeof bookData === 'string') {
      bookData = { title: '新灵感项目', tags: [activeGenre.value], desc: bookData }
    }
    if (Array.isArray(bookData)) throw new Error('模型书籍信息应为对象')
    const safeTitle = bookData.title || '新灵感项目'
    const baseTags = bookData.tags && bookData.tags.length > 0 ? bookData.tags.join(',') : activeGenre.value
    const safeTags = userInstruction 
      ? `${baseTags} | 【特殊指令】：${userInstruction}` 
      : baseTags

    // 2. Character Generate (x2)
    generateStep.value = '正在设定核心人物...'
    const charPrompt = store.prompts.character_generate
      .replace(/{title}/g, safeTitle)
      .replace(/{tags}/g, safeTags)
    
    let char1 = await callLLM(charPrompt, config)
    let char2 = await callLLM(charPrompt, config)
    const characters = []
    let charId = 1
    if (char1 && !Array.isArray(char1) && typeof char1 === 'object') {
      char1.id = charId++; char1.avatarUrl = 'linear-gradient(135deg, #f6d365 0%, #fda085 100%)'; char1.states = [];
      characters.push(char1)
    }
    if (char2 && !Array.isArray(char2) && typeof char2 === 'object') {
      char2.id = charId++; char2.avatarUrl = 'linear-gradient(135deg, #84fab0 0%, #8fd3f4 100%)'; char2.states = [];
      characters.push(char2)
    }

    // 3. Worldview Generate
    generateStep.value = '正在构建世界观...'
    const worldviewPrompt = store.prompts.worldview_auto_construct
      .replace(/{title}/g, safeTitle)
      .replace(/{tags}/g, safeTags)
      .replace(/{tab}/g, '核心设定')
      .replace(/{category}/g, '力量体系/核心法则')
    
    let worldviewData = await callLLM(worldviewPrompt, config)
    let worldview = []
    if (Array.isArray(worldviewData)) {
      worldview = [{
        id: 1,
        title: '力量体系/核心法则',
        icon: '⚡',
        items: worldviewData
      }]
    }

    // 4. Plot Generate
    generateStep.value = '正在推演开局情节...'
    const plotPrompt = store.prompts.plot_generate_twist
      .replace(/{title}/g, safeTitle)
      .replace(/{tags}/g, safeTags)
    
    let plotData = await callLLM(plotPrompt, config)
    let plotNodes = []
    if (plotData && !Array.isArray(plotData) && typeof plotData === 'object') {
      plotData.id = 1
      plotNodes = [plotData]
    }

    // 5. Outline/Chapters Generate
    generateStep.value = '正在裂变前三章细纲...'
    const outlinePrompt = store.prompts.outline_expand
      .replace(/{title}/g, safeTitle)
      .replace(/{volumeTitle}/g, '第一卷：起源')
      .replace(/{volumeDesc}/g, bookData.desc || '开局介绍。')
    
    let chaptersData = await callLLM(outlinePrompt, config)
    let chapters = []
    if (Array.isArray(chaptersData)) {
      chapters = [{
        id: 'vol-1',
        title: '第一卷：起源',
        summary: bookData.desc,
        isExpanded: true,
        chapters: chaptersData.map((c, i) => ({
          id: `chap-${i}`,
          title: c.chapterNum ? `${c.chapterNum} ${c.title}` : c.title,
          summary: c.summary
        }))
      }]
    }

    generateStep.value = '正在装配作品...'
    const gradients = [
      'linear-gradient(135deg, #a18cd1 0%, #fbc2eb 100%)',
      'linear-gradient(135deg, #84fab0 0%, #8fd3f4 100%)',
      'linear-gradient(135deg, #ff9a9e 0%, #fecfef 100%)',
      'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
    ]
    const cover = gradients[Math.floor(Math.random() * gradients.length)]

    const work = {
      id: Date.now(),
      title: safeTitle,
      tags: bookData.tags || [activeGenre.value],
      wordCount: '0',
      synopsis: bookData.desc || userPrompt,
      updatedAt: '刚刚',
      cover: cover,
      status: '草稿',
      characters: characters,
      worldview: worldview,
      plotNodes: plotNodes,
      chapters: chapters,
      terms: [],
      timeline: [],
      materials: [],
      activities: [{ id: 1, time: '刚刚', msg: '由首页 AI 深度裂变的新书架构。' }]
    }
    
    const savedWork = await backendAPI.createWork(work)
    if (generationAbort.signal.aborted) return
    store.activeWorkId = savedWork.id
    store.activeMenuItem = '我的作品'
  } catch (e) {
    if (e.name === 'AbortError') return
    console.error("Generate failed", e)
    alert("生成失败！" + e.message)
  } finally {
    generateStep.value = ''
  }
}
</script>

<template>
  <div class="home-container">
    <CreatorOverview />
    <div class="header-section"><div><h2 class="main-title">用一个灵感，开启一部新作</h2><p class="starter-desc">选择题材与叙事方式，AI 帮你构思故事、人物和世界。</p></div><span class="starter-label">AI 辅助创作</span></div>
    <!-- Input Panel -->
    <div class="generator-panel" id="novel-starter">
      <!-- Row 1: Genres -->
      <div class="filter-row">
        <span class="filter-label">小说题材</span>
        <div class="tag-group">
          <button 
            v-for="g in genres" :key="g"
            class="tag-btn"
            :class="{ active: activeGenre === g }"
            @click="selectGenre(g)"
          >{{ g }}</button>
          
          <div class="more-dropdown-container">
            <button class="tag-btn more-btn" @click="toggleDropdown">
              更多
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>
            </button>
            <div class="dropdown-menu" v-if="showMoreDropdown">
              <button 
                v-for="mg in moreGenres" :key="mg"
                class="dropdown-item"
                :class="{ active: activeGenre === mg }"
                @click="selectGenre(mg); showMoreDropdown = false"
              >{{ mg }}</button>
            </div>
          </div>
        </div>
      </div>

      <!-- Row 2: Other filters -->
      <div class="filter-row secondary-filters">
        <div class="filter-group">
          <span class="filter-label">目标读者</span>
          <div class="tag-group">
            <button v-for="r in readers" :key="r" class="tag-btn" :class="{ active: activeReader === r }" @click="selectReader(r)">{{ r }}</button>
          </div>
        </div>
        
        <div class="filter-group">
          <span class="filter-label">作品视角</span>
          <div class="tag-group">
            <button v-for="p in perspectives" :key="p" class="tag-btn" :class="{ active: activePerspective === p }" @click="selectPerspective(p)">{{ p }}</button>
          </div>
        </div>
        
        <div class="filter-group">
          <span class="filter-label">篇幅长短</span>
          <div class="tag-group">
            <button v-for="l in lengths" :key="l" class="tag-btn" :class="{ active: activeLength === l }" @click="selectLength(l)">{{ l }}</button>
          </div>
        </div>
      </div>

      <div class="divider"></div>

      <!-- Textarea -->
      <div class="input-area">
        <textarea 
          v-model="promptText"
          placeholder="一个普通外卖员发现自己拥有超能力，从此卷入一场外太空阴谋..."
          rows="3"
        ></textarea>
        
        <textarea 
          v-model="instructionText"
          placeholder="全局文风与特殊指令 (可选)，例如：文风偏暗黑，主角杀伐果断，反派智商极高，节奏要快..."
          rows="2"
          style="margin-top: 12px; background: rgba(255,152,0,0.03); border-color: rgba(255,152,0,0.2);"
        ></textarea>
      </div>

      <!-- Action Footer -->
      <div class="panel-footer">
        <div class="model-selector-wrapper">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#666" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          <select class="model-selector" v-model="store.agentAssignments.EditorAgent">
            <option v-for="cfg in store.llmConfigs" :key="cfg.id" :value="cfg.id">{{ cfg.name }}</option>
          </select>
        </div>
        <button class="generate-btn" @click="handleGenerate" :disabled="!!generateStep">
          <svg v-if="!generateStep" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14M5 12h14"/></svg>
          <svg v-else class="spinner" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="2" x2="12" y2="6"></line><line x1="12" y1="18" x2="12" y2="22"></line><line x1="4.93" y1="4.93" x2="7.76" y2="7.76"></line><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"></line><line x1="2" y1="12" x2="6" y2="12"></line><line x1="18" y1="12" x2="22" y2="12"></line><line x1="4.93" y1="19.07" x2="7.76" y2="16.24"></line><line x1="16.24" y1="7.76" x2="19.07" y2="4.93"></line></svg>
          {{ generateStep || '开始生成' }}
        </button>
      </div>
    </div>


  </div>
</template>

<style scoped>
.home-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px 40px;
  min-height: 100%;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* Header */
.header-section {
  text-align: center;
  padding: 10px 0;
}

.main-title {
  font-size: 32px;
  font-weight: 800;
  color: var(--text-primary);
  margin: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.highlight {
  color: var(--accent-color);
}

/* Generator Panel */
.generator-panel {
  background: var(--panel-bg);
  border: 2px solid var(--accent-color);
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 10px 30px var(--accent-bg);
}

.filter-row {
  display: flex;
  align-items: flex-start;
  margin-bottom: 16px;
  gap: 16px;
}

.secondary-filters {
  gap: 32px;
}

.filter-group {
  display: flex;
  align-items: flex-start;
  gap: 16px;
}

.filter-label {
  font-size: 14px;
  color: var(--text-secondary);
  white-space: nowrap;
  padding-top: 6px;
  min-width: 60px;
}

.tag-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  flex: 1;
}

.tag-btn {
  background: var(--surface-subtle);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.tag-btn:hover {
  background: var(--hover-bg);
}

.tag-btn.active {
  background: var(--accent-bg);
  color: var(--accent-color);
  border-color: var(--accent-color);
}

.more-dropdown-container {
  position: relative;
}

.more-btn {
  display: flex;
  align-items: center;
  gap: 4px;
}

.dropdown-menu {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 4px;
  background: var(--panel-bg);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 8px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  display: flex;
  flex-direction: column;
  gap: 4px;
  z-index: 100;
  min-width: 100px;
}

.dropdown-item {
  background: transparent;
  border: none;
  padding: 6px 12px;
  text-align: left;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
  color: var(--text-secondary);
}

.dropdown-item:hover {
  background: var(--hover-bg);
}
.dropdown-item.active {
  color: var(--accent-color);
  background: var(--accent-bg);
}

.divider {
  height: 1px;
  background: var(--border-color);
  margin: 20px 0;
}

.input-area textarea {
  width: 100%;
  border: none;
  resize: none;
  outline: none;
  font-size: 15px;
  color: var(--text-primary);
  line-height: 1.6;
}

.input-area textarea::placeholder {
  color: var(--text-category);
}

.panel-footer {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 16px;
  margin-top: 16px;
}

.model-selector-wrapper {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  background: var(--panel-bg);
}

.model-selector-wrapper:hover {
  background: var(--surface-subtle);
}

.model-selector {
  border: none;
  background: transparent;
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
  outline: none;
}

.generate-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  background: var(--accent-color);
  color: #fff;
  border: none;
  padding: 8px 24px;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  box-shadow: var(--accent-glow);
  transition: all 0.2s;
}

.generate-btn:hover {
  background: var(--accent-hover); /* Darker amber */
  transform: translateY(-1px);
}

.spinner { animation:spin 1s linear infinite; }
@keyframes spin { to { transform:rotate(360deg); } }
</style>
