<script setup>
import UiIcon from './UiIcon.vue'
import { readSSE } from '../sse.js'
import { apiFetch, hasModelCredentials, modelAuthHeaders } from '../api.js'
import { ref, computed, onMounted, watch, nextTick, onUnmounted } from 'vue'
import { store, activeWorkData, getAgentConfig, saveState, flushWork } from '../store.js'
import { createWorkTasks } from '../work_tasks.js'
import { parseModelJSON } from '../model_output.js'
const auxiliaryTasks = createWorkTasks(store, activeWorkData)
let advancingChapter = false

// 1. Chapter selection logic
const showError = e => alert(e.message)
const selectChapter = (chapId) => {
  store.activeChapterId = chapId
}

const activeChapterData = computed(() => {
  if (!activeWorkData.value || !activeWorkData.value.chapters) return null
  for (const vol of activeWorkData.value.chapters) {
    if (!vol.chapters) continue
    const chap = vol.chapters.find(c => c.id === store.activeChapterId)
    if (chap) return chap
  }
  return null
})

const createChapter = () => {
  // Find first volume or create one
  if (!activeWorkData.value.chapters) {
    activeWorkData.value.chapters = []
  }
  if (activeWorkData.value.chapters.length === 0) {
    activeWorkData.value.chapters.push({
      id: Date.now(),
      title: '第一卷',
      isExpanded: true,
      chapters: []
    })
  }
  const newChap = {
    id: Date.now(),
    title: '新章节',
    wordCount: 0,
    status: '草稿',
    date: new Date().toISOString().split('T')[0],
    content: ''
  }
  activeWorkData.value.chapters[0].chapters.push(newChap)
  store.activeChapterId = newChap.id
}

const moveToNextChapterOrCreate = () => {
  advancingChapter = true
  nextTick(() => { advancingChapter = false })
  if (!activeWorkData.value || !activeWorkData.value.chapters) {
    createChapter()
    return
  }
  const flatChapters = activeWorkData.value.chapters.flatMap(v => v.chapters || [])
  const currentIndex = flatChapters.findIndex(c => c.id === store.activeChapterId)
  
  if (currentIndex !== -1 && currentIndex < flatChapters.length - 1) {
    // Next chapter already exists in outline, just switch to it
    store.activeChapterId = flatChapters[currentIndex + 1].id
  } else {
    // We are at the end, create a new one
    createChapter()
  }
}

watch(() => activeWorkData.value.chapters, volumes => {
  const chapters = (volumes || []).flatMap(v => v.chapters || [])
  if (!chapters.some(c => c.id === store.activeChapterId)) store.activeChapterId = chapters[0]?.id || null
}, { immediate: true })

// 2. Toolbar logic
const wordCount = ref(0)
const isSaving = computed(() => saveState.pending > 0)
const saveTime = computed(() => saveState.error ? '保存失败，请重试' : saveState.pending ? '待保存' : '已保存到本地服务')

const handleInput = (e) => {
  if (isGenerating.value) return
  if (activeChapterData.value) {
    updateWordCount(true)
  }
  // 闭环 3：监听 @ 符号，弹出设定库
  if (e && e.data === '@') {
    const textarea = e.target
    // 简化的相对定位（实际应用中需要 getCaretCoordinates库）
    mentionX.value = 40 + (textarea.selectionStart % 30) * 10
    mentionY.value = 60 + Math.floor(textarea.selectionStart / 30) * 20
    showMentionMenu.value = true
    
    // 从 store 提取当前作品的人物和设定
    const chars = activeWorkData.value?.characters || []
    const wvs = activeWorkData.value?.worldview?.flatMap(c => c.items) || []
    mentionItems.value = [
      ...chars.map(c => ({ type: '👥 人物', name: c.name, desc: c.description })),
      ...wvs.map(w => ({ type: '🌍 设定', name: w.name, desc: w.desc }))
    ]
    if(mentionItems.value.length === 0) {
      mentionItems.value = [
        { type: '👥 人物', name: '林星辰', desc: '星火同盟的领袖，拥有预知能力' },
        { type: '🌍 设定', name: '源石', desc: '驱动一切科技的核心能量源' }
      ]
    }
  } else if (e && e.data === ' ') {
    showMentionMenu.value = false
  }
}

const showMentionMenu = ref(false)
const closeMentionMenu = () => setTimeout(() => { showMentionMenu.value = false }, 200)
const mentionX = ref(0)
const mentionY = ref(0)
const mentionItems = ref([])

const insertMention = (item) => {
  console.log(`[Closed Loop] 从当前作品设定库读取并插入光标处: ${item.name}`)
  if (activeChapterData.value) {
    const textarea = document.querySelector('.content-editor')
    if (textarea) {
      const currentContent = activeChapterData.value.content || ''
      const pos = textarea.selectionStart
      const textBefore = currentContent.substring(0, pos)
      const lastAt = textBefore.lastIndexOf('@')
      if (lastAt !== -1) {
        activeChapterData.value.content = currentContent.substring(0, lastAt) + item.name + currentContent.substring(pos)
        setTimeout(() => {
          textarea.focus()
          textarea.setSelectionRange(lastAt + item.name.length, lastAt + item.name.length)
        }, 50)
      } else {
        activeChapterData.value.content += item.name
      }
    } else {
      activeChapterData.value.content += item.name
    }
  }
  showMentionMenu.value = false
  handleInput()
}

const handleFormat = () => {
  if (activeChapterData.value && activeChapterData.value.content) {
    let text = activeChapterData.value.content
    text = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n')
    const paras = text.split('\n')
    const cleanedParas = paras.map(p => p.trim()).filter(p => p.length > 0)
    activeChapterData.value.content = cleanedParas.map(p => '　　' + p).join('\n\n') + '\n\n'
    handleInput()
  }
}

const updateWordCount = (updateGlobal = false) => {
  if (activeChapterData.value) {
    const textLen = (activeChapterData.value.content || '').trim().length
    wordCount.value = textLen
    if (updateGlobal) {
      activeChapterData.value.wordCount = textLen
    }
  } else {
    wordCount.value = 0
  }
}

onMounted(() => updateWordCount(true))

watch(() => store.activeChapterId, () => {
  updateWordCount(true)
  nextTick(() => {
    const activeItem = document.querySelector('.chapter-item.active')
    if (activeItem) {
      activeItem.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  })
})

const showSelectionMenu = ref(false)
const selectionX = ref(0)
const selectionY = ref(0)

const handleSelection = (e) => {
  const textarea = document.querySelector('.content-editor')
  if (textarea && activeChapterData.value) {
    store.editorSelection = { workId: store.activeWorkId, chapterId: store.activeChapterId, start: textarea.selectionStart, end: textarea.selectionEnd, content: activeChapterData.value.content || '' }
  }
  if (textarea && textarea.selectionStart !== textarea.selectionEnd) {
    if (e && e.clientX) {
      selectionX.value = e.clientX
      selectionY.value = e.clientY - 80
    } else {
      const rect = textarea.getBoundingClientRect()
      selectionX.value = rect.left + rect.width / 2 - 100
      selectionY.value = rect.top + 100 // Display near the top of the viewport where the user will be looking
    }
    showSelectionMenu.value = true
  } else {
    showSelectionMenu.value = false
  }
}

watch(() => store.pendingEditorAction, action => {
  if (!action) return
  nextTick(() => {
    if (action.workId !== store.activeWorkId || action.chapterId !== store.activeChapterId || !activeChapterData.value) { store.pendingEditorAction = null; return }
    const chapter = activeChapterData.value
    const content = chapter.content || ''
    const selected = action.selection
    if (action.mode === 'replace') {
      if (!selected || selected.content !== content) alert('原文已发生变化，替换已取消')
      else chapter.content = content.slice(0, selected.start) + action.text + content.slice(selected.end)
    } else {
      const position = selected?.content === content ? selected.end : content.length
      chapter.content = content.slice(0, position) + action.text + content.slice(position)
    }
    store.pendingEditorAction = null
    updateWordCount(true)
  })
}, { immediate: true })

watch(() => store.pendingFixRange, (newRange) => {
  if (newRange && newRange.length === 2) {
    // 使用 setTimeout 确保组件挂载、内容加载完毕且不会受到 alert/页面跳转焦点丢失的影响
    setTimeout(() => {
      const textarea = document.querySelector('.content-editor')
      if (textarea) {
        textarea.focus()
        textarea.setSelectionRange(newRange[0], newRange[1])
        const textBefore = textarea.value.substring(0, newRange[0])
        // Estimate visual lines by accounting for soft-wraps (approx 16px per char)
        const charsPerLine = Math.max(20, Math.floor(textarea.clientWidth / 16))
        let estimatedLines = 0
        textBefore.split('\n').forEach(p => {
          estimatedLines += 1 + Math.floor(p.length / charsPerLine)
        })
        textarea.scrollTop = Math.max(0, estimatedLines * 24 - 100)
        
        handleSelection()
      }
      store.pendingFixRange = null
    }, 250)
  }
}, { immediate: true })

let currentAbortController = null

const stopGenerating = (manualAbort = true) => {
  if (currentAbortController) {
    currentAbortController.abort()
    currentAbortController = null
  }
  isGenerating.value = false
  if (manualAbort) {
    isAutoPilot.value = false // Stop auto-pilot if manually aborted
  }
}

onUnmounted(() => {
  auxiliaryTasks.dispose()
  stopGenerating(true)
})

const isGenerating = ref(false)
const isAutoPilot = ref(false)
watch(() => store.activeWorkId, () => { auxiliaryTasks.cancelAll(); stopGenerating(true) })
watch(() => store.activeChapterId, () => { if (!advancingChapter) stopGenerating(true) })

const toggleAutoPilot = () => {
  isAutoPilot.value = !isAutoPilot.value
  if (isAutoPilot.value) {
    if (!isGenerating.value) {
      if (activeChapterData.value?.content?.length >= 2500) {
        handleAiAction('结章')
      } else {
        handleAiAction('续写')
      }
    }
  } else {
    stopGenerating(true)
  }
}

const extractNewCharacters = async (newText) => {
  if (!newText || newText.trim().length < 10) return
  
  const work = activeWorkData.value
  const existingChars = (work.characters || []).map(c => c.name)
  const config = getAgentConfig('EditorAgent')
  if (!hasModelCredentials(config)) return
  
  const prompt = `你是一个顶级网文角色提取器。
请阅读下面的最新小说片段，找出所有在片段中【首次出现的新角色】（包括有具体名字的角色，以及虽无具体名字但具有特定身份且对剧情有推动作用的角色，例如“皇帝”、“太后”、“神秘刺客”等）。
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

  const task = auxiliaryTasks.begin()
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
            { role: 'user', content: newText }
          ],
          temperature: 0.1
        }
      })
    })

    if (!response.ok) return
    const json = await response.json()
    const content = json.choices?.[0]?.message?.content || '[]'
    
    const newChars = parseModelJSON(content, 'array')
    task.assertCurrent()
    if (Array.isArray(newChars) && newChars.length > 0) {
      newChars.forEach(char => {
        if (!existingChars.includes(char.name) && char.name) {
          work.characters ||= []
          work.characters.unshift({
            id: Date.now() + Math.random(),
            name: char.name,
            avatarUrl: 'linear-gradient(135deg, #a1c4fd 0%, #c2e9fb 100%)',
            faction: char.faction || '配角',
            tags: char.tags || ['野生角色'],
            description: char.description || '',
            states: [
              { chapterRange: [1, 100], stats: '未知', equips: '未知' }
            ]
          })
          existingChars.push(char.name)
        }
      })
    }
  } catch (e) {
    if (!task.cancelled) console.error('Failed to extract new characters:', e)
  } finally {
    task.finish()
  }
}

const handleAiAction = async (action) => {
  if (!activeChapterData.value) return
  if (['续写', '结章', '润色', '扩写', '缩写'].includes(action)) {
    if (!activeChapterData.value) return
    
    const config = getAgentConfig('EditorAgent')
    if (isGenerating.value) {
      stopGenerating()
      return
    }

    if (!hasModelCredentials(config)) {
      alert("请先在【AI引擎策略】中配置 API Key 或连接账号！")
      return
    }

    isGenerating.value = true
    currentAbortController = new AbortController()
    const controller = currentAbortController
    const targetWork = activeWorkData.value
    
    const targetFixLabel = store.pendingFixLabel
    store.pendingFixLabel = ''
    
    let generatedText = ''
    
    const targetChapter = activeChapterData.value
    if (!targetChapter) {
      isGenerating.value = false
      return
    }
    
    const originalContent = targetChapter.content || ''
    const isReplacement = action !== '续写' && action !== '结章'
    try {
      const fullText = originalContent
      const textarea = document.querySelector('.content-editor')
      const selStart = textarea ? textarea.selectionStart : -1
      const selEnd = textarea ? textarea.selectionEnd : -1

      let context = ''
      if (action === '续写' || action === '结章') {
        const contextLength = config.contextWindow || 2000
        context = fullText.slice(-contextLength)
        
        // 如果当前章节字数太少，自动拉取上一章的结尾作为上下文，保证剧情连贯
        if (fullText.trim().length < 500) {
          const flatChapters = activeWorkData.value?.chapters?.flatMap(v => v.chapters) || []
          const currentIndex = flatChapters.findIndex(c => c.id === targetChapter.id)
          if (currentIndex > 0) {
            const prevChap = flatChapters[currentIndex - 1]
            const prevContent = prevChap.content || ''
            const prevSummary = prevChap.summary || '无'
            context = `【前情提要（上一章大纲）】\n${prevSummary}\n\n【上一章结尾部分】\n${prevContent.slice(-1500)}\n\n====================\n【本章开头内容】\n${context}`
          }
        }
      } else {
        if (!textarea || selStart === selEnd) {
          alert(`请先在正文中用鼠标框选一段需要【${action}】的文字！`)
          isGenerating.value = false
          return
        }
        context = fullText.substring(selStart, selEnd)
      }

      const baseUrl = config.baseUrl ? config.baseUrl.replace(/\/$/, '') : 'https://api.openai.com/v1'
      const endpoint = `${baseUrl}/chat/completions`
      
      const actionMap = {
        '续写': 'editor_continue',
        '结章': 'editor_conclude',
        '润色': 'editor_polish',
        '扩写': 'editor_expand',
        '缩写': 'editor_shorten'
      }
      const promptKey = actionMap[action]
      let prompt = store.prompts[promptKey] || `你是一个优秀的AI小说助手。请对文本进行${action}处理。`
      
      // 如果是在执行定向修复，注入强力指令
      if (targetFixLabel) {
        prompt += `\n\n【核心任务】：本次修改的核心目标是弥补原文本在【${targetFixLabel}】上的不足！`
        if (targetFixLabel === '悬念设置') {
          prompt += `请务必在段落的最结尾处，制造一个极其强烈的悬念、未解之谜或突发变故（必须以疑问句“？”、省略号“...”或破折号“——”作为结尾），牢牢勾住读者的胃口！`
        } else if (targetFixLabel === '剧情张力') {
          prompt += `请大幅增强情节的矛盾冲突、反差感和压迫感，让剧情更紧凑！`
        } else if (targetFixLabel === '人物塑造') {
          prompt += `请增加角色的微表情、心理活动或标志性动作，让人物更加丰满立体！`
        } else if (targetFixLabel === '场景画面') {
          prompt += `请加入丰富的五感描写（视觉、听觉、嗅觉等），让环境氛围更加逼真！`
        }
      }
      
      let userContent = ''
      if (action === '续写' || action === '结章') {
        const title = activeWorkData.value?.title || '未命名'
        const chars = activeWorkData.value?.characters?.map(c => `${c.name} (${c.faction}): ${c.description}`).join('\n') || '暂无'
        const wv = activeWorkData.value?.worldview?.flatMap(c => c.items)?.map(i => `${i.name}: ${i.desc}`).join('\n') || '暂无'
        const chapSummary = targetChapter.summary || '暂无细纲'
        const plotNodes = activeWorkData.value?.plotNodes?.map(p => `[${p.title}] - ${p.desc}`).join('\n') || '暂无主线'
        const currentWordCount = targetChapter.content?.trim().length || 0
        const targetWordCount = 2500

        let pacingRules = ''
        if (action === '续写') {
          pacingRules = `
【节奏与进度指导原则（核心机密）】
1. 如果“本章已写字数”远低于目标字数（例如小于2000字），请务必【放慢节奏，稳步推进】！用极其细腻的环境描写、人物微表情、复杂的心理博弈和对话来扩充内容，绝对不能一笔带过！此时【严禁】结束本章！
2. 【严格的完结禁令】：在“本章已写字数”未达到目标字数之前，**绝对禁止**输出“[本章完]”字样！无论剧情看似多么完整，只要字数没满，你必须继续拓展细节，或者抛出新的意外转折。
3. 如果“本章已写字数”已经达到或接近目标字数，且剧情已经推进到了大纲尾声，请自然地【收拢剧情】，留下悬念。只有在确认字数达标且剧情圆满的情况下，你才可以在末尾新起一行，输出唯一结束标记：[本章完]。`
        } else if (action === '结章') {
          pacingRules = `
【结章执行指令（最高优先级）】
1. 当前作者已下达【结章】指令，说明前期铺垫已经足够。
2. 你现在的唯一任务是：在接下来的 200 到 400 字以内，光速引爆当前场景的矛盾，抛出一个巨大的悬念、反转或突发危机！
3. 绝对不要再进行任何长篇大论的铺垫，绝对不能超过 500 字！写完悬念后，立刻在最后一行输出【本章完】并停止生成！`
        }

        userContent = `【小说书名】：《${title}》
【核心角色档案】
${chars}

【世界观设定】
${wv}

【全局终极主线大纲】（非常重要：每次续写都必须考虑如何向这个最终目标靠拢或铺垫）
${plotNodes}

【本章剧情大纲】
${chapSummary}

【当前写作进度】
本章已写字数：${currentWordCount} 字
本章目标字数：约 ${targetWordCount} 字

【角色拓展原则】
- 如果剧情需要，你可以自由创造、引入符合世界观的新角色。
- 请尽量让新角色有鲜明的性格和阵营立场。

【输出格式严格警告】
绝对不要在输出内容的开头写书名、卷名、章节编号（如“第X章”或“## 标题”），绝对不要使用 Markdown 标题语法（#）。
绝对不要在文末添加任何“ps”、“作者有话说”、“译者注”、“未完待续”、“后续待续”或戏外的互动废话，绝对不要使用破折号分割线。
请直接输出纯净的小说正文文字，保持沉浸式阅读体验！
${pacingRules}

====================
【需要紧接续写的当前上下文】
${context || '(在此开始第一段)'}`
      } else {
        userContent = `请对我提供的下面这段小说段落进行【${action}】处理。
要求：严格遵循系统提示词的角色设定。直接输出处理后的纯文本，不要带有任何多余的解释、问候或Markdown代码块标记。

【原文本】
${context}`
      }

      const response = await apiFetch('/api/proxy/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
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
              { role: 'user', content: userContent }
            ],
            max_tokens: 4096,
            stream: true
          }
        }),
        signal: currentAbortController.signal
      })

      if (!response.ok) {
        throw new Error(`API 请求失败: ${response.status} ${response.statusText}`)
      }

      let insertPos = originalContent.length
      if (controller.signal.aborted || activeWorkData.value !== targetWork || activeChapterData.value !== targetChapter) throw new DOMException('生成目标已改变', 'AbortError')
      if (!isReplacement && originalContent && !originalContent.endsWith('\n')) {
        targetChapter.content += '\n\n'
        insertPos += 2
      }
      let completed = false
      for await (const event of readSSE(response)) {
        if (controller.signal.aborted || activeWorkData.value !== targetWork || activeChapterData.value !== targetChapter) throw new DOMException('生成目标已改变', 'AbortError')
        if (event.status === 'done') { completed = true; break }
        const choice = event.choices?.[0]
        if (choice?.finish_reason) {
          if (isReplacement && choice.finish_reason !== 'stop') throw new Error('模型结果不完整，原文已保留')
          completed = choice.finish_reason === 'stop'
        }
        const chunk = choice?.delta?.content || ''
        if (!chunk) continue
        generatedText += chunk
        if (!isReplacement) {
          const text = targetChapter.content || ''
          targetChapter.content = text.substring(0, insertPos) + chunk + text.substring(insertPos)
          insertPos += chunk.length
          updateWordCount()
          nextTick(() => {
            const editor = document.querySelector('.content-editor')
            if (editor) editor.scrollTop = editor.scrollHeight
          })
        }
      }
      if (isReplacement) {
        if (controller.signal.aborted || activeWorkData.value !== targetWork || activeChapterData.value !== targetChapter) throw new DOMException('生成目标已改变', 'AbortError')
        if (!completed || !generatedText.trim()) throw new Error('模型未返回完整替换内容，原文已保留')
        if (targetChapter.content !== originalContent) throw new Error('正文已被修改，本次结果未覆盖原文')
        targetChapter.content = originalContent.substring(0, selStart) + generatedText + originalContent.substring(selEnd)
      } else if (!completed) {
        throw new Error('生成中断，已收到的正文已保留')
      }

      if ((action === '续写' || action === '结章') && generatedText.trim().length > 0) {
        // Fire and forget: do not await this, so it doesn't block the autopilot transition!
        extractNewCharacters(generatedText).catch(e => console.error(e))
      }
    } catch (e) {
      if (e.name === 'AbortError') {
        console.log('AI generation manually stopped')
      } else {
        console.error(`AI ${action}出错:`, e)
        alert(`AI ${action}失败: ${e.message}`)
      }
      isAutoPilot.value = false // Stop auto-pilot on error
    } finally {
      if (currentAbortController !== controller) return
      currentAbortController = null
      isGenerating.value = false
      updateWordCount(true) // Sync to global when finished
      
      if (isAutoPilot.value && (action === '续写' || action === '结章')) {
        let hasFinished = targetChapter.content?.includes('本章完')
        
        // 兜底机制：如果是“结章”动作，但大模型忘了写【本章完】，系统强行帮它补上
        if (!hasFinished && action === '结章' && generatedText.trim().length > 0) {
          targetChapter.content += '\n\n【本章完】'
          hasFinished = true
        }

        if (hasFinished) {
          if (targetChapter.content.length < 500) {
            alert('⚠️ 系统检测到大模型在字数极少时强行结章（可能是剧情已推进到大结局），为防止无限建空章节，自动挂机已停止。')
            isAutoPilot.value = false
            return
          }
          // Chapter finished, move to next one automatically
          setTimeout(() => {
            if (!isAutoPilot.value) return
            moveToNextChapterOrCreate()
            setTimeout(() => {
              if (isAutoPilot.value) handleAiAction('续写')
            }, 1000)
          }, 1500)
        } else {
          // Continue writing current chapter, but trigger chapter conclusion if it's long enough
          setTimeout(() => {
            if (isAutoPilot.value) {
              if (targetChapter.content.length >= 2500) {
                handleAiAction('结章')
              } else {
                handleAiAction('续写')
              }
            }
          }, 1500)
        }
      }
    }
  } else {
    alert(`【${action}】功能暂未实现`)
  }
}
</script>

<template>
  <div class="editor-container">
    
    <!-- Left Chapter Sidebar -->
    <aside class="chapter-sidebar">
      <div class="sidebar-header">
        <h2>
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path></svg>
          章节列表
        </h2>
        <button class="add-btn" @click="createChapter" aria-label="添加章节">
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
        </button>
      </div>

      <div class="chapter-list">
        <template v-if="activeWorkData.chapters && activeWorkData.chapters.length > 0">
          <div class="volume-group" v-for="vol in activeWorkData.chapters" :key="vol.id">
            <button class="volume-title" :aria-expanded="!!vol.isExpanded" @click="vol.isExpanded = !vol.isExpanded">
              <svg :class="{'rotated': vol.isExpanded}" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>
              {{ vol.title }}
            </button>
            <div class="chapters" v-show="vol.isExpanded">
              <button 
                class="chapter-item" 
                v-for="chap in vol.chapters" 
                :key="chap.id"
                :class="{ active: chap.id === store.activeChapterId }" :aria-current="chap.id === store.activeChapterId ? 'page' : undefined" :title="chap.title"
                @click="selectChapter(chap.id)"
              >
                {{ chap.title }}
              </button>
            </div>
          </div>
        </template>
        <div v-else class="empty-chapters">
          暂无章节
        </div>
      </div>
    </aside>

    <!-- Main Editor Area -->
    <main class="main-editor">
      <!-- Toolbar -->
      <header class="editor-toolbar">
        <div class="ai-tools">
          <!-- Auto-Pilot Button -->
          <button class="ai-btn" @click="toggleAutoPilot" :class="{'primary': isAutoPilot, 'outline': !isAutoPilot}" >
            <UiIcon name="settings" :size="15" /> 
            {{ isAutoPilot ? '正在挂机...' : '自动挂机写作' }}
          </button>
          
          <button class="ai-btn primary" @click="isGenerating && !isAutoPilot ? stopGenerating(true) : handleAiAction('续写')" :class="{'danger': isGenerating && !isAutoPilot}" :disabled="isAutoPilot">
            <UiIcon :name="isGenerating && !isAutoPilot ? 'stop' : 'spark'" :size="15" /> 
            {{ isGenerating && !isAutoPilot ? '停止生成' : 'AI续写' }}
          </button>
          <button class="ai-btn" @click="handleAiAction('结章')" :disabled="isGenerating">
            <UiIcon name="check" :size="15" /> 结章
          </button>
          <button class="ai-btn" @click="handleAiAction('润色')" :disabled="isGenerating">
            <UiIcon name="pen" :size="15" /> 润色
          </button>
          <button class="ai-btn" @click="handleAiAction('扩写')" :disabled="isGenerating">
            <UiIcon name="expand" :size="15" /> 扩写
          </button>
          <button class="ai-btn" @click="handleAiAction('缩写')" :disabled="isGenerating">
            <UiIcon name="shrink" :size="15" /> 缩写
          </button>
          <div class="toolbar-divider"></div>
          <button class="tool-btn" @click="handleFormat">
            <UiIcon name="align" :size="15" /> 排版
          </button>
        </div>
        
        <div class="editor-status">
          <span class="word-count" v-if="activeChapterData">字数: {{ wordCount }}</span>
          <span class="save-status" v-if="saveTime">{{ saveTime }}</span>
        </div>
      </header>

      <!-- Writing Canvas -->
      <div class="writing-canvas">
        <div class="editor-wrapper" style="position: relative; height: 100%; width: 100%;">
          <textarea 
            v-if="activeChapterData"
            class="content-editor" aria-label="章节正文"
            :readonly="isGenerating"
            v-model="activeChapterData.content" 
            @input="handleInput"
            @mouseup="handleSelection"
            @keyup="handleSelection"
            @blur="closeMentionMenu"
            placeholder="开始你的创作之旅... (输入 @ 极速呼出人物与设定库)"
          ></textarea>
          
          <!-- Floating AI Selection Menu -->
          <div 
            v-if="showSelectionMenu" 
            class="selection-popup glass-panel" 
            :style="{ left: selectionX + 'px', top: selectionY + 'px' }"
          >
            <div style="font-size: 12px; color: var(--text-secondary); margin-bottom: 8px; font-weight: bold;">
              ✨ AI {{ store.pendingFixLabel ? `已锁定短板：【${store.pendingFixLabel}】` : '智能调优' }}
            </div>
            <div style="display: flex; gap: 8px;">
              <button class="ai-btn small" @click.stop="handleAiAction('润色'); showSelectionMenu = false">※ 润色</button>
              <button class="ai-btn small" @click.stop="handleAiAction('扩写'); showSelectionMenu = false">⇲ 扩写</button>
              <button class="ai-btn small" @click.stop="handleAiAction('缩写'); showSelectionMenu = false">⇱ 缩写</button>
            </div>
          </div>
          
          <!-- @ Mention Floating Menu -->
          <div 
            v-if="showMentionMenu" 
            class="mention-menu" 
            :style="{ left: mentionX + 'px', top: mentionY + 'px' }"
          >
            <div class="mention-header">当前作品的专属设定</div>
            <div 
              class="mention-item" 
              v-for="(item, idx) in mentionItems" 
              :key="idx"
              @click.stop="insertMention(item)"
              :title="item.desc"
            >
              <span class="mention-type">{{ item.type }}</span>
              <span class="mention-name">{{ item.name }}</span>
            </div>
          </div>
        </div>
        
        <div v-if="!activeChapterData" class="empty-editor-state">
          <div class="empty-icon-box">
            <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path></svg>
          </div>
          <h3>暂无章节</h3>
          <p>点击左侧 + 按钮新建章节，开始创作</p>
        </div>
      </div>
    </main>

  </div>
</template>

<style scoped>
/* Full rewrite matching the screenshot */
.editor-container {
  display: flex;
  height: 100%;
  width: 100%;
  background-color: var(--bg-color);
  gap: 16px;
  padding: 16px;
  box-sizing: border-box;
}

/* Sidebar */
.chapter-sidebar {
  width: 240px;
  background-color: var(--panel-bg);
  border-radius: 8px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.02);
  display: flex;
  flex-direction: column;
  border: 1px solid var(--border-color);
  flex-shrink: 0;
}

.sidebar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid var(--border-color);
}

.sidebar-header h2 {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.add-btn {
  background: var(--panel-bg);
  border: 1px solid var(--border-color);
  border-radius: 4px;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--text-secondary);
  transition: all 0.2s;
}

.add-btn:hover {
  border-color: var(--accent-color);
  color: var(--accent-color);
}

.chapter-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}

.empty-chapters {
  padding: 32px 16px;
  text-align: center;
  color: var(--text-category);
  font-size: 13px;
}

.volume-group {
  margin-bottom: 8px;
}

.volume-title {
  border: 0; background: transparent; width: 100%; text-align: left;
  padding: 8px 16px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
}

.volume-title svg {
  transition: transform 0.2s;
}

.volume-title svg.rotated {
  transform: rotate(90deg);
}

.chapter-item {
  display: block; border: 0; background: transparent; width: 100%; text-align: left;
  padding: 10px 16px 10px 36px;
  font-size: 13px;
  color: var(--text-primary);
  cursor: pointer;
  transition: background 0.2s;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.chapter-item:hover {
  background-color: var(--surface-subtle);
}

.chapter-item.active {
  background-color: var(--accent-bg);
  color: var(--accent-color);
  font-weight: 500;
  border-right: 3px solid var(--accent-color);
}

/* Main Editor */
.main-editor {
  flex: 1;
  background-color: var(--panel-bg);
  border-radius: 8px;
  border: 1px solid var(--border-color);
  box-shadow: 0 2px 10px rgba(0,0,0,0.02);
  display: flex;
  flex-direction: column;
}

/* Toolbar */
.editor-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 24px;
  border-bottom: 1px solid var(--border-color);
  background: var(--panel-bg);
  border-radius: 8px 8px 0 0;
}

.ai-tools {
  display: flex;
  align-items: center;
  gap: 12px;
}

.ai-btn, .tool-btn {
  background: transparent;
  border: none;
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 6px 10px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: all 0.2s;
  font-weight: 500;
}

.ai-btn:hover, .tool-btn:hover {
  background-color: var(--hover-bg);
  color: var(--text-primary);
}

.ai-btn.primary {
  color: var(--accent-color);
}

.ai-btn.primary:hover {
  background-color: var(--accent-bg);
}

.ai-icon {
  font-size: 14px;
}

.toolbar-divider {
  width: 1px;
  height: 16px;
  background-color: var(--border-color);
  margin: 0 4px;
}

.editor-status {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
  color: var(--text-category);
}

/* Canvas */
.writing-canvas {
  flex: 1;
  display: flex;
  background-color: var(--panel-bg);
  border-radius: 0 0 8px 8px;
  position: relative;
  overflow: hidden;
}

.content-editor {
  width: 100%;
  height: 100%;
  border: none;
  resize: none;
  padding: 40px calc(max(40px, (100% - 1200px) / 2));
  font-size: 16px;
  line-height: 2;
  color: var(--text-primary);
  background-color: transparent;
  outline: none;
  box-sizing: border-box;
  font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

.mention-menu {
  position: absolute;
  background: var(--panel-bg);
  border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.15);
  border: 1px solid var(--border-color);
  width: 240px;
  z-index: 100;
  overflow: hidden;
}

.mention-header {
  padding: 8px 12px;
  font-size: 12px;
  color: var(--text-secondary);
  background: var(--bg-color);
  border-bottom: 1px solid var(--border-color);
}

.mention-item {
  padding: 10px 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  transition: background 0.2s;
}

.mention-item:hover {
  background: var(--accent-bg);
}

.mention-type {
  font-size: 12px;
  color: var(--accent-color);
  background: var(--accent-bg);
  padding: 2px 6px;
  border-radius: 4px;
}

.mention-name {
  font-size: 13px;
  color: var(--text-primary);
}

.selection-popup {
  position: fixed;
  z-index: 1000;
  padding: 12px;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.15);
  display: flex;
  flex-direction: column;
  animation: popupFade 0.2s ease-out;
}
.selection-popup .ai-btn.small {
  padding: 6px 12px;
  font-size: 13px;
}
@keyframes popupFade {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.content-editor::placeholder {
  color: var(--border-color);
}

/* Empty State */
.empty-editor-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-category);
  text-align: center;
  width: 100%;
}

.empty-icon-box {
  margin-bottom: 16px;
  opacity: 0.5;
}

.empty-editor-state h3 {
  font-size: 16px;
  font-weight: 500;
  margin: 0 0 8px 0;
  color: var(--text-primary);
}

.empty-editor-state p {
  font-size: 13px;
  margin: 0;
}
</style>
