<script setup>
import { apiFetch, hasModelCredentials, modelAuthHeaders } from '../api.js'
import { ref, computed, watch, onUnmounted } from 'vue'
import { store, activeWorkData, getAgentConfig } from '../store.js'
import { createWorkTasks } from '../work_tasks.js'
import { parseComicShots } from '../model_output.js'
import UiIcon from './UiIcon.vue'
const selectedChapterId = ref('')
const isGenerating = ref(false)
const isBatchGenerating = ref(false)
const batchProgress = ref('')
const abortBatch = ref(false)
const tasks = createWorkTasks(store, activeWorkData)
watch(() => store.activeWorkId, () => { tasks.cancelAll(); abortBatch.value = true; selectedChapterId.value = '' })
onUnmounted(() => { abortBatch.value = true; tasks.dispose() })
const flatChapters = computed(() => (activeWorkData.value.chapters || []).flatMap(vol => vol.chapters || []))
const selectedChapter = computed(() => flatChapters.value.find(c => c.id === selectedChapterId.value))
const generatedShots = computed(() => selectedChapter.value?.comicShots || [])
const convertedChapterCount = computed(() => flatChapters.value.filter(c => c.comicShots?.length).length)
const totalShotCount = computed(() => flatChapters.value.reduce((n, c) => n + (c.comicShots || []).length, 0))
async function generateForChapter(chapter, task, config) {
  task.assertCurrent()
  const work = task.work
  const source = chapter.content
  const previous = JSON.stringify(chapter.comicShots || [])
  if (typeof source !== 'string' || !source.trim()) throw new Error('该章节没有正文')
  const prompt = store.prompts.comic_generate_script.replace('{content}', source)
  const response = await apiFetch('/api/proxy/chat', {
    method:'POST', signal:task.signal, headers:{'Content-Type':'application/json'},
    body:JSON.stringify({url:`${(config.baseUrl || 'https://api.openai.com/v1').replace(/\/+$/,'')}/chat/completions`,
      headers:{...modelAuthHeaders(config),'Content-Type':'application/json'},
      body:{model:config.modelName || 'gpt-3.5-turbo',messages:[{role:'user',content:prompt}],temperature:.7}})
  })
  const data = await response.json()
  const shots = parseComicShots(data.choices?.[0]?.message?.content)
  task.assertCurrent()
  if (!(work.chapters || []).some(vol=>(vol.chapters || []).includes(chapter)) || chapter.content !== source || JSON.stringify(chapter.comicShots || []) !== previous) throw new Error('章节或分镜已修改，未覆盖你的编辑')
  chapter.comicShots = shots
}
const generateComicScript = async () => {
  if (isGenerating.value || isBatchGenerating.value) return
  const chapter = selectedChapter.value
  if (!chapter?.content?.trim()) return alert('请先选择有正文的章节')
  const config = getAgentConfig('PlotAgent')
  if (!hasModelCredentials(config)) return alert('请先配置模型或连接账号')
  if (chapter.comicShots?.length && !confirm('重新生成将替换本章现有分镜，是否继续？')) return
  const task = tasks.begin()
  isGenerating.value = true
  try { await generateForChapter(chapter,task,config) }
  catch(e) { if (!task.cancelled) alert('漫剧生成失败：'+e.message) }
  finally { task.finish(); isGenerating.value = false }
}
const generateBatchComicScript = async () => {
  if (isGenerating.value || isBatchGenerating.value) return
  const chapters = flatChapters.value.filter(c=>typeof c.content==='string' && c.content.trim() && !c.comicShots?.length)
  if (!chapters.length) return alert('没有需要转换的非空章节')
  const config = getAgentConfig('PlotAgent')
  if (!hasModelCredentials(config)) return alert('请先配置模型或连接账号')
  const task = tasks.begin()
  let completed=0,failed=0
  isBatchGenerating.value=true; abortBatch.value=false
  try {
    for (let i=0;i<chapters.length;i++) {
      task.assertCurrent()
      selectedChapterId.value=chapters[i].id
      batchProgress.value=`进度：${i+1} / ${chapters.length}`
      isGenerating.value=true
      try { await generateForChapter(chapters[i],task,config); completed++ }
      catch(e) { if(task.cancelled) throw e; failed++ }
      finally { isGenerating.value=false }
    }
    task.assertCurrent()
    alert(`批量转换结束：成功 ${completed} 章，失败 ${failed} 章。空白章节未参与转换。`)
  } catch(e) { if(!task.cancelled) alert('批量转换中断：'+e.message) }
  finally { task.finish();isGenerating.value=false;isBatchGenerating.value=false;batchProgress.value='' }
}
const stopBatchGeneration = () => { abortBatch.value=true;tasks.cancelAll() }
const copyPrompt = prompt => navigator.clipboard.writeText(prompt).then(()=>alert('已复制到剪贴板')).catch(()=>alert('复制失败，请手动复制'))
</script>

<template>
  <div class="comic-studio-container">
    <div class="header">
      <span class="comic-eyebrow">小说改编 · 分镜创作</span>
      <h2 class="page-title">漫剧工坊</h2>
      <p class="page-desc">把小说里的故事，拆解成画面、台词与绘画提示词。</p>
    </div>

    <section class="comic-overview" aria-label="漫剧制作概览">
      <div><span>源章节</span><strong>{{ flatChapters.length }}<small>章</small></strong></div>
      <div><span>已完成拆解</span><strong>{{ convertedChapterCount }}<small>章</small></strong></div>
      <div><span>累计分镜</span><strong>{{ totalShotCount }}<small>镜</small></strong></div>
      <div class="comic-overview-icon"><UiIcon name="film" :size="44" /></div>
    </section>
    <div class="comic-workflow" aria-label="分镜创作流程"><span :class="{current: !selectedChapterId}"><b>1</b>选择小说章节</span><span class="workflow-line"></span><span :class="{current: selectedChapterId && !generatedShots.length}"><b>2</b>AI 拆解分镜</span><span class="workflow-line"></span><span :class="{current: generatedShots.length}"><b>3</b>查看分镜脚本</span></div>

    <div class="control-panel">
      <div class="input-group">
        <label>选择源章节</label>
        <select v-model="selectedChapterId" :disabled="isGenerating">
          <option value="" disabled>-- 请选择章节 --</option>
          <option v-for="ch in flatChapters" :key="ch.id" :value="ch.id">
            {{ ch.comicShots && ch.comicShots.length > 0 ? '✅ [已转换] ' : '' }}{{ ch.title }} (约 {{ ch.content ? ch.content.length : 0 }} 字)
          </option>
        </select>
      </div>
      <button v-if="!isBatchGenerating" class="primary-btn generate-btn" @click="generateComicScript" :disabled="isGenerating || !selectedChapterId">
        <svg v-if="!isGenerating" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
        <svg v-else class="spinner" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="2" x2="12" y2="6"></line><line x1="12" y1="18" x2="12" y2="22"></line><line x1="4.93" y1="4.93" x2="7.76" y2="7.76"></line><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"></line><line x1="2" y1="12" x2="6" y2="12"></line><line x1="18" y1="12" x2="22" y2="12"></line><line x1="4.93" y1="19.07" x2="7.76" y2="16.24"></line><line x1="16.24" y1="7.76" x2="19.07" y2="4.93"></line></svg>
        {{ isGenerating ? 'AI 正在拆解分镜...' : '单章生成' }}
      </button>

      <button v-if="!isBatchGenerating" class="batch-btn" @click="generateBatchComicScript" :disabled="isGenerating">
        批量转换全书
      </button>
      <button v-else class="stop-btn" @click="stopBatchGeneration">
        停止批量任务 ({{ batchProgress }})
      </button>
    </div>

    <div class="shots-list" v-if="isGenerating">
      <div v-for="i in 3" :key="'skeleton-'+i" class="shot-card skeleton-card">
        <div class="shot-header skeleton-pulse" style="width: 100px; height: 20px; border-radius: 4px;"></div>
        <div class="shot-body">
          <div class="shot-left">
            <div class="desc-box skeleton-box">
              <div class="skeleton-pulse" style="width: 60px; height: 14px; margin-bottom: 12px; border-radius: 4px;"></div>
              <div class="skeleton-pulse" style="width: 100%; height: 14px; margin-bottom: 8px; border-radius: 4px;"></div>
              <div class="skeleton-pulse" style="width: 80%; height: 14px; border-radius: 4px;"></div>
            </div>
          </div>
          <div class="shot-right">
            <div class="prompt-box skeleton-box">
              <div class="skeleton-pulse" style="width: 150px; height: 14px; margin-bottom: 12px; border-radius: 4px;"></div>
              <div class="skeleton-pulse" style="width: 100%; height: 80px; border-radius: 4px;"></div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="shots-list" v-else-if="generatedShots.length > 0">
      <div v-for="(shot, idx) in generatedShots" :key="idx" class="shot-card">
        <div class="shot-header">
          <span class="shot-number">Shot {{ shot.shot || idx + 1 }}</span>
        </div>
        <div class="shot-body">
          <div class="shot-left">
            <div class="desc-box">
              <div class="box-label">画面描述</div>
              <div class="box-content">{{ shot.desc }}</div>
            </div>
            <div class="desc-box" v-if="shot.dialogue">
              <div class="box-label">台词 / 旁白</div>
              <div class="box-content dialogue">{{ shot.dialogue }}</div>
            </div>
          </div>
          <div class="shot-right">
            <div class="prompt-box">
              <div class="box-label" style="display: flex; justify-content: space-between; align-items: center;">
                <span>英文绘画提示词 (Prompt)</span>
                <button class="copy-btn" @click="copyPrompt(shot.prompt)">复制</button>
              </div>
              <textarea class="prompt-textarea" readonly :value="shot.prompt"></textarea>
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <div v-else-if="flatChapters.length > 0" class="empty-state">
      <div class="comic-empty-icon"><UiIcon name="film" :size="35" /></div>
      <h3>让文字，成为下一个镜头</h3>
      <p>选择一个有正文的章节，生成画面描述、台词与绘画提示词。</p>
    </div>
    <div v-else class="empty-state"><div class="comic-empty-icon"><UiIcon name="book" :size="35" /></div><h3>先准备一个故事章节</h3><p>完成小说正文后，就可以在这里开始漫剧拆解。</p><button class="comic-empty-action" @click="store.activeMenuItem = '章节管理'">前往章节管理<UiIcon name="arrow" :size="15" /></button></div>
  </div>
</template>

<style scoped>
.comic-eyebrow { display:block; color:var(--accent-color); font-size:11px; margin-bottom:8px; }
.comic-overview { display:flex; align-items:center; gap:55px; padding:23px 28px; background:var(--panel-bg); border:1px solid var(--border-color); border-radius:8px; margin-bottom:24px; }
.comic-overview>div>span { display:block; font-size:12px; color:var(--text-secondary); }
.comic-overview strong { display:block; margin-top:10px; font-size:27px; font-weight:600; font-variant-numeric:tabular-nums; color:var(--text-primary); }
.comic-overview small { color:var(--text-category); font-size:11px; font-weight:400; margin-left:7px; }
.comic-overview-icon { margin-left:auto; color:var(--accent-color); background:var(--accent-bg); padding:12px; border-radius:12px; }
.comic-workflow { display:flex; align-items:center; justify-content:center; gap:20px; font-size:12px; margin:28px 0; color:var(--text-category); }
.comic-workflow>span:not(.workflow-line) { display:flex; align-items:center; gap:9px; white-space:nowrap; }
.comic-workflow b { font-weight:500; display:flex; align-items:center; justify-content:center; width:24px; height:24px; background:var(--hover-bg); color:var(--text-secondary); border-radius:50%; }
.comic-workflow .current { color:var(--accent-color); }
.comic-workflow .current b { color:var(--accent-color); background:var(--accent-bg); }
.workflow-line { width:70px; height:1px; background:var(--border-color); }
.comic-empty-icon { display:inline-flex; padding:20px; border-radius:50%; background:var(--surface-subtle); color:var(--text-category); margin-bottom:20px; }
.empty-state h3 { color:var(--text-primary); font-size:16px; font-weight:500; margin:0 0 12px; }
.comic-empty-action { display:inline-flex; align-items:center; gap:8px; margin-top:18px; border:1px solid var(--accent-border); border-radius:5px; padding:8px 14px; color:var(--accent-color); background:var(--accent-bg); }
@media(max-width:800px) { .comic-overview{gap:28px;padding:20px} .comic-workflow{gap:10px;font-size:11px} .workflow-line{width:25px} }
@media(max-width:550px) { .comic-overview{gap:22px;padding:18px;justify-content:space-between} .comic-overview-icon{display:none} .comic-overview strong{font-size:23px} .comic-workflow{align-items:flex-start;gap:13px} .comic-workflow>span:not(.workflow-line){flex-direction:column;text-align:center;white-space:normal;gap:5px;flex:1} .workflow-line{display:none} }
.comic-studio-container {
  padding: 32px;
  max-width: 1200px;
  margin: 0 auto;
}

.header {
  margin-bottom: 32px;
}

.page-title {
  font-size: 24px;
  font-weight: 700;
  margin: 0 0 8px 0;
  color: var(--text-color);
}

.page-desc {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 0;
}

.control-panel {
  display: flex;
  align-items: flex-end;
  gap: 16px;
  margin-bottom: 32px;
  background: var(--bg-color);
  padding: 24px;
  border-radius: 12px;
  border: 1px solid var(--border-color);
}

.input-group {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.input-group label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-color);
}

.input-group select {
  padding: 10px 12px;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  outline: none;
  font-size: 14px;
  background: var(--bg-color);
  color: var(--text-color);
}

.generate-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 40px;
  padding: 0 20px;
}

.batch-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 40px;
  padding: 0 20px;
  background: var(--panel-bg);
  color: var(--text-secondary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.batch-btn:hover {
  opacity: 0.9;
  transform: translateY(-1px);
}

.batch-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}

.stop-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 40px;
  padding: 0 20px;
  background: var(--danger-bg);
  color: var(--danger-color);
  border: 1px solid var(--danger-border);
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.stop-btn:hover {
  background: var(--hover-bg);
}

.shots-list {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.shot-card {
  background: var(--bg-color);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  overflow: hidden;
}

.shot-header {
  background: var(--sidebar-bg);
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-color);
  font-weight: 600;
  color: var(--primary-color);
}

.shot-body {
  display: flex;
  padding: 16px;
  gap: 24px;
}

.shot-left {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.shot-right {
  flex: 1;
}

.desc-box {
  background: rgba(0,0,0,0.02);
  border-radius: 8px;
  padding: 12px;
}

.box-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-category);
  margin-bottom: 8px;
  text-transform: uppercase;
}

.box-content {
  font-size: 14px;
  line-height: 1.6;
}

.dialogue {
  font-style: italic;
  color: var(--primary-color);
}

.prompt-box {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.prompt-textarea {
  flex: 1;
  width: 100%;
  min-height: 120px;
  padding: 12px;
  border: 1px dashed var(--border-color);
  border-radius: 8px;
  resize: vertical;
  background: var(--surface-subtle);
  font-family: 'Consolas', monospace;
  font-size: 13px;
  line-height: 1.5;
  color: var(--text-primary);
  outline: none;
  box-sizing: border-box;
}

.copy-btn {
  background: none;
  border: 1px solid var(--primary-color);
  color: var(--primary-color);
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
}

.copy-btn:hover {
  background: var(--primary-color);
  color: white;
}

.empty-state {
  text-align: center;
  padding: 64px 0;
  color: var(--text-category);
}

.empty-state .icon {
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.5;
}

.spinner {
  animation: spin 2s linear infinite;
}
@keyframes spin {
  100% { transform: rotate(360deg); }
}

/* Skeleton Loading Styles */
.skeleton-card {
  border-color: rgba(0,0,0,0.05);
  box-shadow: 0 4px 12px rgba(0,0,0,0.02);
}

.skeleton-box {
  background: transparent;
  border: 1px solid rgba(0,0,0,0.03);
}

.skeleton-pulse {
  background: linear-gradient(90deg, #f0f2f5 25%, #e6e8eb 50%, #f0f2f5 75%);
  background-size: 200% 100%;
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
</style>
