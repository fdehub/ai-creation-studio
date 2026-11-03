<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'
import { store, activeWorkData, getAgentConfig, flushWork } from '../store.js'
import { apiFetch, hasModelCredentials } from '../api.js'
import { createWorkTasks } from '../work_tasks.js'
import * as comic from '../comic_production.js'
import UiIcon from './UiIcon.vue'
import ComicProductionSettings from './ComicProductionSettings.vue'
import ComicShotEditor from './ComicShotEditor.vue'
const selectedChapterId=ref(''), selectedClipId=ref(''), tab=ref('shots'), showDraft=ref(true)
const isGenerating=ref(false), isBatchGenerating=ref(false), batchProgress=ref(''), error=ref(''), notice=ref(''), currentHash=ref('')
const exportFormat=ref('text')
const tasks=createWorkTasks(store,activeWorkData)
const flatChapters=computed(()=>(activeWorkData.value.chapters || []).flatMap(volume=>volume.chapters || []))
const selectedChapter=computed(()=>flatChapters.value.find(chapter=>chapter.id===selectedChapterId.value))
const production=computed(()=>activeWorkData.value.comicProduction || {schemaVersion:1,settings:comic.comicSettings(),bible:comic.emptyBible()})
const plan=computed(()=>selectedChapter.value?(showDraft.value && selectedChapter.value.comicDraft?selectedChapter.value.comicDraft:comic.publishedComicPlan(activeWorkData.value,selectedChapter.value)):null)
const clips=computed(()=>plan.value?.clips || [])
const selectedClip=computed(()=>clips.value.find(clip=>clip.id===selectedClipId.value) || clips.value[0])
const generatedShots=computed(()=>(plan.value?.shots || []).filter(shot=>shot.clipId===selectedClip.value?.id))
const busy=computed(()=>isGenerating.value || isBatchGenerating.value)
const sourceChanged=computed(()=>!!(plan.value?.sourceHash && currentHash.value && plan.value.sourceHash!==currentHash.value))
const ruleIssues=computed(()=>comic.reviewComicPlan(plan.value,{sourceChanged:sourceChanged.value}))
const issues=computed(()=>[...ruleIssues.value,...(plan.value?.issues || [])])
const totalShotCount=computed(()=>plan.value?.shots.length || 0)
const totalDuration=computed(()=>(plan.value?.shots || []).reduce((sum,shot)=>sum+Number(shot.duration || 0),0))
const statusLabel=computed(()=>({planning:'编剧拆解',directing:'导演分镜',reviewing:'连续性质检',interrupted:'已中断，可继续',complete:'制作完成',manual:'手动草稿',imported:'原有分镜'})[plan.value?.status] || '等待制作')
let sourceCheck=0
watch(()=>activeWorkData.value.id,()=>{
  tasks.cancelAll();selectedChapterId.value='';selectedClipId.value='';error.value='';notice.value='';tab.value='shots';showDraft.value=true
  if(activeWorkData.value.id) comic.ensureComicProduction(activeWorkData.value)
},{immediate:true})
watch(()=>[selectedChapter.value?.id,selectedChapter.value?.content],async()=>{
  const version=++sourceCheck;currentHash.value=''
  if(!selectedChapter.value) return
  const hash=await comic.comicHash(selectedChapter.value.content || '')
  if(version===sourceCheck) currentHash.value=hash
})
watch(selectedChapterId,()=>{selectedClipId.value='';showDraft.value=!!selectedChapter.value?.comicDraft;error.value='';notice.value=''})
onUnmounted(()=>tasks.dispose())
function configs() {
  const result={breakdown:getAgentConfig('PlotAgent'),direct:getAgentConfig('EditorAgent'),review:getAgentConfig('LoreAgent')}
  if(Object.values(result).some(config=>!hasModelCredentials(config))) throw new Error('请在 AI 引擎策略中为情节、写作与世界观 Agent 配置模型或账号')
  return result
}
async function generateComicScript(resume=false) {
  if(busy.value) return
  const work=activeWorkData.value, chapter=selectedChapter.value
  if(!chapter?.content?.trim()) return error.value='请先选择有正文的章节'
  if(!resume && chapter.comicDraft && !confirm('重新制作会替换当前未应用草稿。已应用分镜保持不变，是否继续？')) return
  let configured
  try {configured=configs()} catch(e) {error.value=e.message;return}
  const task=tasks.begin();isGenerating.value=true;error.value='';notice.value='';tab.value='shots';showDraft.value=true
  try {
    await comic.runComicProduction({work,chapter,task,apiFetch,flushWork,configs:configured,resume,onProgress:message=>batchProgress.value=message})
    task.assertCurrent();selectedClipId.value=chapter.comicDraft.clips[0]?.id || '';notice.value='制作草稿已保存。请检查分镜和质检意见，再应用到本章。'
  } catch(e) {if(!task.cancelled) error.value=e.message}
  finally {task.finish();isGenerating.value=false;batchProgress.value=''}
}
async function generateBatchComicScript() {
  if(busy.value) return
  const work=activeWorkData.value, chapters=flatChapters.value.filter(chapter=>chapter.content?.trim())
  if(!chapters.length) return error.value='没有可制作的非空章节'
  let configured
  try{configured=configs()}catch(e){error.value=e.message;return}
  if(!confirm(`为 ${chapters.length} 章依次制作草稿？会分段多次调用模型。已有应用分镜保留，已完成且正文未变的草稿跳过。`))return
  const task=tasks.begin();isBatchGenerating.value=true;error.value='';notice.value='';let completed=0,carryBible=null
  try {
    for(let i=0;i<chapters.length;i++) {
      task.assertCurrent();const chapter=chapters[i];selectedChapterId.value=chapter.id;showDraft.value=true
      await comic.runComicProduction({work,chapter,task,apiFetch,flushWork,configs:configured,resume:true,carryBible,onProgress:message=>{showDraft.value=true;batchProgress.value=`第 ${i+1}/${chapters.length} 章 · ${message}`}})
      carryBible=chapter.comicDraft.bible;completed++
    }
    task.assertCurrent();notice.value=`已准备 ${completed} 章制作草稿，未自动覆盖已应用分镜。`
  }catch(e){if(!task.cancelled)error.value=`批量任务在完成 ${completed} 章后停止：${e.message}`}
  finally{task.finish();isBatchGenerating.value=false;batchProgress.value=''}
}
const stopBatchGeneration=()=>tasks.cancelAll()
async function applyDraft() {
  const work=activeWorkData.value,chapter=selectedChapter.value
  try{await comic.applyComicDraft(work,chapter);await flushWork(work.id);if(activeWorkData.value===work && selectedChapter.value===chapter){showDraft.value=false;notice.value='本章分镜已应用并保存，其他章节保持不变。'}}catch(e){if(activeWorkData.value===work && selectedChapter.value===chapter)error.value=e.message}
}
function syncDraftSettings(){try{comic.rebaseComicDraft(activeWorkData.value,selectedChapter.value);notice.value='已同步制作设定，请重新检查台词、时长和连续性。'}catch(e){error.value=e.message}}
function adoptDraftBible(){try{const work=activeWorkData.value;work.comicProduction.bible=comic.mergeComicBible(work.comicProduction.bible,selectedChapter.value.comicDraft.bible);comic.rebaseComicDraft(work,selectedChapter.value);notice.value='草稿人物、场景与道具已纳入全剧设定，可编辑后同步到草稿。'}catch(e){error.value=e.message}}
function unlockPublished(){if(confirm('解锁本章已应用镜头，允许之后应用新草稿？')){for(const shot of selectedChapter.value.comicShots || [])shot.locked=false;flushWork(activeWorkData.value.id).catch(e=>error.value=e.message)}}
async function editDraft() {
  const chapter=selectedChapter.value,work=activeWorkData.value
  if(!chapter)return false
  try {
    if(!chapter.comicDraft) {
      const existing=comic.publishedComicPlan(work,chapter)
      chapter.comicDraft=existing?JSON.parse(JSON.stringify(existing)):{schemaVersion:2,sourceHash:'',settings:JSON.parse(JSON.stringify(production.value.settings)),baseProduction:JSON.parse(JSON.stringify(production.value)),bible:JSON.parse(JSON.stringify(production.value.bible)),passages:[],completedBlocks:[],reviewedClips:[],beats:[],clips:[],shots:[],status:'manual',endingState:'',previousContext:'',reviewSummary:'',issues:[],reviewedSignature:'',generatedAt:''}
      chapter.comicDraft.baseProduction=JSON.parse(JSON.stringify(production.value));chapter.comicDraft.status='manual'
    }
    const draft=chapter.comicDraft,source=chapter.content || ''
    const hash=await comic.comicHash(source)
    const assertCurrent=()=>{if(chapter.content!==source || chapter.comicDraft!==draft || store.activeWorkId!==work.id || selectedChapter.value!==chapter)throw new Error('正文或作品已变化，请重新准备编辑草稿')}
    assertCurrent()
    if(draft.sourceHash && draft.sourceHash!==hash)throw new Error('正文已变化，请重新制作草稿；原有草稿与分镜仍保留')
    draft.sourceHash=hash
    if(source.trim() && !draft.passages.length) {
      await flushWork(work.id);assertCurrent()
      const prepared=await (await apiFetch(`/comic/prepare?workId=${encodeURIComponent(work.id)}&chapterId=${encodeURIComponent(chapter.id)}`)).json()
      assertCurrent()
      if(prepared.sourceHash!==hash)throw new Error('后端正文与当前内容不同，请完成保存后重试')
      draft.passages=prepared.blocks.flatMap(block=>block.passages);draft.previousContext=prepared.previousContext
    }
    showDraft.value=true
    return true
  }catch(e){if(store.activeWorkId===work.id && selectedChapter.value===chapter)error.value=e.message;return false}
}
async function addClip() {
  if(!selectedChapter.value)return error.value='请先选择章节'
  if(!await editDraft())return
  const name=prompt('片段名称','新片段')
  if(!name?.trim())return
  const clip={id:crypto.randomUUID(),title:name.trim(),sceneId:'',characterIds:[],sourceIds:[],beatIds:[],summary:''}
  plan.value.clips.push(clip);selectedClipId.value=clip.id;touch()
}
async function addShot() {
  if(!selectedChapter.value)return error.value='请先选择章节'
  if(!await editDraft())return
  if(!selectedClip.value)return addClip()
  const shot=comic.emptyComicShot(selectedClip.value.id,plan.value.settings);shot.sceneId=selectedClip.value.sceneId
  plan.value.shots.push(shot);touch()
}
function touch() {
  if(!plan.value)return
  plan.value.reviewedSignature='';plan.value.reviewedClips=[]
  plan.value.shots.forEach((shot,index)=>{shot.shot=index+1;if(shot.lines.length)shot.dialogue=shot.lines.map(line=>`${plan.value.bible.characters.find(row=>row.id===line.characterId)?.name || '旁白'}：${line.text}`).join('\n')})
  if(plan.value.shots.length)plan.value.endingState=plan.value.shots.at(-1).endState || plan.value.endingState
  if(!showDraft.value && selectedChapter.value?.comicPlan){selectedChapter.value.comicPlan.reviewedSignature='';selectedChapter.value.comicPlan.reviewedClips=[];selectedChapter.value.comicPlan.endingState=plan.value.endingState}
}
function removeShot(shot) {if(!showDraft.value || !selectedChapter.value?.comicDraft || shot.locked)return;if(confirm('删除该镜头？')){const target=selectedChapter.value.comicDraft.shots,index=target.findIndex(row=>row.id===shot.id);if(index>=0){target.splice(index,1);touch()}}}
function removeClip(){const draft=selectedChapter.value?.comicDraft,clip=selectedClip.value;if(!showDraft.value || !draft || !clip)return;if(draft.shots.some(shot=>shot.clipId===clip.id && shot.locked))return error.value='片段内有锁定镜头，请先解锁';if(confirm('删除当前片段及其镜头？已应用分镜仍保留。')){draft.clips=draft.clips.filter(row=>row.id!==clip.id);draft.shots=draft.shots.filter(row=>row.clipId!==clip.id);selectedClipId.value=draft.clips[0]?.id || '';touch()}}
function moveShot(shot,direction) {
  if(!showDraft.value || !selectedChapter.value?.comicDraft || shot.locked)return
  const target=showDraft.value?selectedChapter.value.comicDraft.shots:selectedChapter.value.comicShots
  const index=target.findIndex(row=>row.id===shot.id),other=index+direction
  if(index<0 || other<0 || other>=target.length || target[other].clipId!==shot.clipId || target[other].locked)return
  target.splice(index,1);target.splice(other,0,shot);touch()
}
async function reviewSelectedClip() {
  if(busy.value || !selectedClip.value)return
  if(!selectedChapter.value.comicDraft && !await editDraft())return
  showDraft.value=true
  const target=plan.value, clip=selectedClip.value, work=activeWorkData.value,chapter=selectedChapter.value
  let config
  try{config=configs().review}catch(e){error.value=e.message;return}
  const task=tasks.begin();isGenerating.value=true;error.value=''
  try{
    const hash=await comic.comicHash(chapter.content || '');task.assertCurrent()
    if(task.work!==work || target.sourceHash!==hash)throw new Error('正文或作品已变化，请先重新制作或核对原文引用')
    await flushWork(work.id);task.assertCurrent()
    const before=JSON.stringify(target),source=chapter.content
    const response=await apiFetch('/comic/stage',{method:'POST',signal:task.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({workId:work.id,chapterId:chapter.id,sourceHash:target.sourceHash,stage:'review',clipId:clip.id,config,production:{schemaVersion:1,settings:target.settings,bible:target.bible},plan:target})})
    const result=await response.json();task.assertCurrent()
    if(chapter.comicDraft!==target || chapter.content!==source || JSON.stringify(target)!==before)throw new Error('正文或分镜已修改，旧质检响应未应用')
    target.issues=[...target.issues.filter(issue=>issue.clipId!==clip.id),...result.issues].slice(0,100);target.reviewSummary=result.summary
    if(!target.reviewedClips.includes(clip.id))target.reviewedClips.push(clip.id)
    const checked=JSON.stringify(target),signature=target.clips.every(clip=>target.reviewedClips.includes(clip.id))?await comic.comicHash(comic.comicSignature(target)):''
    task.assertCurrent();if(chapter.content!==source || chapter.comicDraft!==target || JSON.stringify(target)!==checked)throw new Error('正文或分镜已修改，请重新质检')
    target.reviewedSignature=signature;await flushWork(work.id);task.assertCurrent();tab.value='review'
  }catch(e){if(!task.cancelled)error.value=e.message}
  finally{task.finish();isGenerating.value=false}
}
async function regenerateSelectedClip() {
  if(busy.value || !selectedClip.value)return
  try {
    if(!selectedChapter.value.comicDraft && !await editDraft())return
  }catch(e){error.value=e.message;return}
  showDraft.value=true
  const target=plan.value,clip=selectedClip.value,work=activeWorkData.value,chapter=selectedChapter.value
  if(!clip.sourceIds.length)return error.value='请先在片段信息中关联原文，或完整生成制作草稿'
  if(target.shots.some(shot=>shot.clipId===clip.id && shot.locked))return error.value='当前片段有锁定镜头，请先解锁需要重做的镜头'
  let configured
  try{configured=configs()}catch(e){error.value=e.message;return}
  if(!confirm('重做当前片段的导演分镜并进行辅助质检？其他片段及已应用分镜保留。'))return
  const task=tasks.begin();isGenerating.value=true;error.value='';showDraft.value=true
  const source=chapter.content
  let expected=JSON.stringify(target)
  const assertCurrent=()=>{task.assertCurrent();if(task.work!==work || chapter.content!==source || chapter.comicDraft!==target || JSON.stringify(target)!==expected)throw new Error('正文、草稿或作品已变化，重做结果未覆盖编辑')}
  const call=async(stage)=>{
    assertCurrent()
    const response=await apiFetch('/comic/stage',{method:'POST',signal:task.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({workId:work.id,chapterId:chapter.id,sourceHash:target.sourceHash,stage,clipId:clip.id,config:configured[stage],production:{schemaVersion:1,settings:target.settings,bible:target.bible},plan:target})})
    const result=await response.json();assertCurrent();return result
  }
  try {
    if(target.sourceHash!==await comic.comicHash(chapter.content || ''))throw new Error('正文已变化，请重新准备制作草稿')
    await flushWork(work.id);assertCurrent();batchProgress.value='重做当前片段的导演分镜…'
    const result=await call('direct')
    const byClip=new Map(target.clips.map(row=>[row.id,row.id===clip.id?result.shots:target.shots.filter(shot=>shot.clipId===row.id)]))
    target.shots=target.clips.flatMap(row=>byClip.get(row.id))
    target.shots.forEach((shot,index)=>shot.shot=index+1)
    const index=target.clips.findIndex(row=>row.id===clip.id),affected=new Set(target.clips.slice(index).map(row=>row.id))
    target.reviewedClips=target.reviewedClips.filter(id=>!affected.has(id));target.reviewedSignature='';target.status='manual'
    target.issues=target.issues.filter(issue=>!affected.has(issue.clipId))
    if(index===target.clips.length-1)target.endingState=result.endingState
    else target.issues.push({severity:'warning',code:'UPSTREAM_CHANGED',message:'前方片段已重做，请复核后续片段的起始状态与镜头连续性',shotId:'',clipId:target.clips[index+1].id})
    expected=JSON.stringify(target);await flushWork(work.id);assertCurrent();batchProgress.value='检查重做片段的连续性…'
    const review=await call('review')
    target.issues.push(...review.issues);target.issues=target.issues.slice(0,100);target.reviewSummary=review.summary;target.reviewedClips.push(clip.id)
    expected=JSON.stringify(target)
    if(target.clips.every(row=>target.reviewedClips.includes(row.id))){const signature=await comic.comicHash(comic.comicSignature(target));assertCurrent();target.reviewedSignature=signature}
    expected=JSON.stringify(target);await flushWork(work.id);notice.value='当前片段已重做并保存为草稿，其他片段未被覆盖。'
  }catch(e){if(!task.cancelled)error.value=e.message}
  finally{task.finish();isGenerating.value=false;batchProgress.value=''}
}
function exportPlan() {
  if(!plan.value?.shots.length)return error.value='还没有可以导出的分镜'
  const exported=comic.exportComicPlan(plan.value,`${activeWorkData.value.title}-${selectedChapter.value.title}`,exportFormat.value)
  const url=URL.createObjectURL(new Blob([exported.text],{type:exported.mime}));const link=document.createElement('a');link.href=url;link.download=exported.filename;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000)
}
function locateIssue(issue) {tab.value='shots';if(issue.clipId)selectedClipId.value=issue.clipId;setTimeout(()=>document.getElementById(`shot-${issue.shotId}`)?.scrollIntoView({behavior:'smooth',block:'start'}),0)}
</script>

<template>
  <div class="comic-studio-container">
    <header class="production-header"><div><span class="comic-eyebrow">故事改编 · 导演分镜 · 连续性管理</span><h2>漫剧制作台</h2><p>从剧情段落到镜头、台词与制作提示词，按作品保存每一步。</p></div><button class="btn-secondary" :disabled="busy || !activeWorkData.id" @click="tab=tab==='settings'?'shots':'settings'">{{ tab==='settings'?'返回分镜':'制作设定' }}</button></header>
    <div v-if="!activeWorkData.id" class="comic-empty"><UiIcon name="book" :size="36" /><h3>先创建一部作品</h3><p>准备正文后即可制作，也可手动编辑分镜。</p></div>
    <template v-else>
      <div class="comic-overview"><div><span>源章节</span><strong>{{ flatChapters.length }}<small>章</small></strong></div><div><span>当前制作片段</span><strong>{{ clips.length }}<small>段</small></strong></div><div><span>镜头 / 预估时长</span><strong>{{ totalShotCount }}<small>镜 · {{ totalDuration.toFixed(1) }} 秒</small></strong></div><div class="production-state"><span>{{ showDraft && selectedChapter?.comicDraft?'制作草稿':'已应用分镜' }}</span><b>{{ statusLabel }}</b></div></div>
      <div class="control-panel"><label>选择源章节<select v-model="selectedChapterId" :disabled="busy"><option value="">请选择章节</option><option v-for="chapter in flatChapters" :key="chapter.id" :value="chapter.id">{{ chapter.title }}{{ chapter.comicDraft?' · 有草稿':chapter.comicShots?.length?' · 有分镜':'' }}</option></select></label><button class="primary-btn" :disabled="busy || !selectedChapter?.content?.trim()" @click="generateComicScript(false)">生成制作草稿</button><button v-if="selectedChapter?.comicDraft?.status==='interrupted'" class="btn-secondary" :disabled="busy" @click="generateComicScript(true)">继续未完成任务</button><button v-if="!busy" class="btn-secondary" @click="generateBatchComicScript">批量制作</button><button v-else class="btn-secondary" @click="stopBatchGeneration">停止任务</button></div>
      <p class="production-note">编剧拆解使用情节模型，导演使用写作模型，连续性质检使用世界观模型。过程会分段多次调用；已有分镜在应用草稿前保留。取消等待不保证供应商已停止计费。</p>
      <div v-if="busy" role="status" class="progress-panel"><span class="spinner"></span>{{ batchProgress || '正在检查当前片段…' }}</div><div v-if="error" role="alert" class="comic-alert error">{{ error }}</div><div v-if="notice" role="status" class="comic-alert">{{ notice }}</div>
      <div v-if="sourceChanged" class="comic-alert error">正文已更新，当前分镜仍保留。重新制作前请核对原文与分镜。</div>
      <nav class="production-tabs" aria-label="漫剧工作区"><button :class="{active:tab==='shots'}" @click="tab='shots'">分镜制作</button><button :class="{active:tab==='settings'}" @click="tab='settings'">全剧设定</button><button :class="{active:tab==='review'}" @click="tab='review'">质检报告 <span>{{ issues.length }}</span></button></nav>
      <div v-if="tab==='settings' && selectedChapter?.comicDraft" class="comic-alert draft-assets"><span>当前章节的草稿包含人物、场景与声线提案，可纳入全剧后继续调整。</span><button class="btn-secondary" :disabled="busy" @click="adoptDraftBible">将草稿设定纳入全剧</button></div>
      <ComicProductionSettings v-if="tab==='settings'" :work="activeWorkData" :production="production" :disabled="busy" />
      <section v-else-if="tab==='review'" class="review-panel"><header><div><h3>规则检查与 AI 辅助审阅</h3><p>时长、引用、说话人等规则实时检查；语义与空间问题由模型辅助提示，不能保证成片零穿帮。</p></div><button class="btn-secondary" :disabled="busy || !plan?.shots.length" @click="reviewSelectedClip">当前片段 AI 质检</button></header><p v-if="plan?.reviewSummary" class="review-summary">{{ plan.reviewSummary }}</p><p v-if="!plan?.reviewedSignature" class="production-note">当前编辑尚未完成新的 AI 质检，原有意见可能已过期。</p><p v-if="!issues.length">规则检查暂未发现问题；仍需人工检查剧情和镜头。</p><button v-for="(issue,index) in issues" :key="index" class="review-issue" :class="issue.severity" @click="locateIssue(issue)"><b>{{ ({error:'错误',warning:'提醒',info:'建议'})[issue.severity] }}</b><span>{{ issue.message }}</span><small v-if="issue.shotId">定位镜头 →</small></button></section>
      <section v-else class="production-workspace">
        <aside class="clip-sidebar"><div class="clip-sidebar-title"><strong>制作片段</strong><button :disabled="busy || !selectedChapter" @click="addClip">＋</button></div><button v-for="(clip,index) in clips" :key="clip.id" class="clip-option" :class="{active:selectedClip?.id===clip.id}" @click="selectedClipId=clip.id"><b>{{ index+1 }} · {{ clip.title }}</b><span>{{ plan.shots.filter(shot=>shot.clipId===clip.id).length }} 镜头</span></button><p v-if="!clips.length">选择正文并生成制作草稿，或手动添加片段。</p></aside>
        <div class="shots-main"><div class="draft-toolbar"><div class="draft-choice"><button :class="{active:showDraft}" :disabled="busy || !selectedChapter?.comicDraft" @click="showDraft=true">制作草稿</button><button :class="{active:!showDraft}" :disabled="busy || !selectedChapter?.comicShots?.length" @click="showDraft=false">已应用分镜</button></div><button v-if="showDraft && selectedChapter?.comicDraft && ['complete','manual','imported'].includes(selectedChapter.comicDraft.status)" class="primary-btn" :disabled="busy || sourceChanged" @click="applyDraft">应用到本章</button><button v-if="plan && !selectedChapter?.comicDraft" class="btn-secondary" :disabled="busy" @click="editDraft">创建编辑草稿</button><button v-if="selectedChapter?.comicDraft" class="btn-secondary" :disabled="busy" @click="syncDraftSettings">同步制作设定</button><button v-if="selectedChapter?.comicShots?.some(shot=>shot.locked)" class="btn-secondary" :disabled="busy" @click="unlockPublished">解锁已应用镜头</button></div>
          <div v-if="plan" class="export-toolbar"><span>{{ plan.settings.ratio }} · {{ ({realistic:'真人写实',anime:'二维动漫','3d':'3D 国漫',custom:'自定义风格'})[plan.settings.style] }} · 每段目标 {{ plan.settings.targetDuration }} 秒</span><div><select v-model="exportFormat" aria-label="导出格式"><option value="text">制作提示词 TXT</option><option value="json">制作数据 JSON</option><option value="csv">分镜表 CSV</option><option value="srt">字幕时间轴 SRT</option></select><button class="btn-secondary" :disabled="busy || !plan.shots.length" @click="exportPlan">导出本章</button></div></div>
          <div v-if="selectedClip" class="clip-heading"><div><h3>{{ selectedClip.title }}</h3><p>{{ selectedClip.summary }}</p></div><div class="clip-tools"><button :disabled="busy" class="btn-secondary" @click="regenerateSelectedClip">重做当前片段</button><button :disabled="busy" class="btn-secondary" @click="addShot">添加镜头</button><button v-if="showDraft && selectedChapter?.comicDraft" :disabled="busy" class="btn-secondary" @click="removeClip">删除片段</button></div></div><details v-if="selectedClip && showDraft && selectedChapter?.comicDraft" class="clip-metadata"><summary>编辑片段信息与原文引用</summary><fieldset :disabled="busy" @change="touch"><label>片段名称<input v-model="selectedClip.title" maxlength="200" /></label><label>剧情范围<textarea v-model="selectedClip.summary" rows="2" maxlength="3000"></textarea></label><label>场景<select v-model="selectedClip.sceneId"><option value="">未关联</option><option v-for="scene in plan.bible.scenes" :key="scene.id" :value="scene.id">{{ scene.name }}</option></select></label><label>片段人物<select v-model="selectedClip.characterIds" multiple><option v-for="actor in plan.bible.characters" :key="actor.id" :value="actor.id">{{ actor.name }}</option></select></label><label>原文引用<select v-model="selectedClip.sourceIds" multiple><option v-for="passage in plan.passages" :key="passage.id" :value="passage.id">{{ passage.id }} · {{ passage.text.slice(0,70) }}</option></select></label></fieldset></details>
          <p v-if="plan?.status==='imported'" class="comic-alert">原有分镜完整保留。创建编辑草稿可补充时长、场景、声线与原文引用。</p>
          <ComicShotEditor v-for="shot in generatedShots" :key="shot.id" :shot="shot" :plan="plan" :disabled="busy || !showDraft || !selectedChapter?.comicDraft" @change="touch" @remove="removeShot(shot)" @move="direction=>moveShot(shot,direction)" />
          <div v-if="!generatedShots.length" class="comic-empty"><UiIcon name="film" :size="40" /><h3>{{ selectedChapter?'让故事成为镜头':'选择一个故事章节' }}</h3><p>先整理全剧设定，再生成或手动编辑分镜。每个镜头可记录时长、运镜、台词和衔接状态。</p></div>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.comic-studio-container{display:flex;flex-direction:column;gap:18px;max-width:1500px;margin:0 auto}.production-header{display:flex;justify-content:space-between;align-items:center;gap:20px}.comic-eyebrow{font-size:11px;color:var(--accent-color)}h2{margin:8px 0;font-size:24px}h3{font-size:15px;margin:0 0 8px}p{margin:0;color:var(--text-secondary);font-size:12px;line-height:1.8}.comic-overview{display:flex;gap:50px;border:1px solid var(--border-color);background:var(--panel-bg);padding:20px 24px;border-radius:8px}.comic-overview span{font-size:11px;color:var(--text-secondary);display:block}.comic-overview strong{display:block;margin-top:10px;font-size:25px;font-weight:600}.comic-overview small{font-size:11px;font-weight:400;color:var(--text-secondary);margin-left:8px}.production-state{margin-left:auto;display:flex;flex-direction:column;gap:12px}.production-state b{font-size:12px;color:var(--accent-color);font-weight:500}.control-panel{display:flex;align-items:flex-end;gap:12px;background:var(--panel-bg);padding:20px;border:1px solid var(--border-color);border-radius:8px}.control-panel label{flex:1;display:flex;flex-direction:column;gap:9px;font-size:11px;color:var(--text-secondary)}select{padding:9px;border:1px solid var(--border-color);border-radius:5px;background:var(--panel-bg);color:var(--text-primary);font:12px inherit;min-width:0}.primary-btn,.btn-secondary{border-radius:5px;padding:9px 14px;font:12px inherit;white-space:nowrap;cursor:pointer}.primary-btn{background:var(--accent-color);border:1px solid var(--accent-color);color:#fff}.btn-secondary{background:var(--panel-bg);border:1px solid var(--border-color);color:var(--text-primary)}button:disabled{opacity:.45;cursor:not-allowed}.production-note{font-size:11px;color:var(--text-category)}.production-tabs{display:flex;gap:20px;border-bottom:1px solid var(--border-color)}.production-tabs button{background:none;border:0;border-bottom:2px solid transparent;padding:10px 3px;color:var(--text-secondary);font-size:13px;cursor:pointer}.production-tabs button.active{color:var(--accent-color);border-bottom-color:var(--accent-color)}.production-tabs span{margin-left:5px;padding:2px 5px;background:var(--surface-subtle);border-radius:3px;font-size:10px}.comic-alert{border:1px solid var(--border-color);background:var(--panel-bg);padding:12px 15px;border-radius:5px;color:var(--text-secondary);font-size:12px;line-height:1.7}.comic-alert.error{border-color:var(--accent-border);background:var(--accent-bg);color:var(--text-primary)}.production-workspace{display:grid;grid-template-columns:210px minmax(0,1fr);gap:18px}.clip-sidebar{align-self:start;background:var(--panel-bg);border:1px solid var(--border-color);border-radius:7px;overflow:hidden}.clip-sidebar-title{display:flex;align-items:center;justify-content:space-between;padding:14px;font-size:12px}.clip-sidebar-title button{background:none;border:0;color:var(--accent-color);cursor:pointer;font-size:18px}.clip-option{border:0;border-top:1px solid var(--border-color);background:var(--panel-bg);width:100%;padding:14px;text-align:left;cursor:pointer;color:var(--text-primary)}.clip-option.active{background:var(--accent-bg);box-shadow:inset 3px 0 var(--accent-color)}.clip-option b{display:block;font-size:12px;font-weight:500;line-height:1.6}.clip-option span{display:block;font-size:10px;color:var(--text-secondary);margin-top:6px}.clip-sidebar>p{padding:14px}.shots-main{min-width:0}.draft-assets{display:flex;align-items:center;justify-content:space-between;gap:16px}.draft-toolbar,.export-toolbar,.clip-heading{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:16px}.draft-choice{display:flex;background:var(--surface-subtle);border:1px solid var(--border-color);border-radius:5px;padding:3px}.draft-choice button{border:0;background:none;padding:7px 12px;color:var(--text-secondary);font-size:11px;cursor:pointer}.draft-choice button.active{background:var(--panel-bg);border-radius:4px;color:var(--text-primary)}.export-toolbar{font-size:11px;color:var(--text-secondary);flex-wrap:wrap}.export-toolbar>div{display:flex;gap:8px}.clip-heading{padding:15px 0}.clip-heading p{font-size:11px}.clip-tools{display:flex;gap:8px;flex-wrap:wrap}.clip-metadata{border:1px solid var(--border-color);padding:13px;border-radius:5px;margin-bottom:16px;background:var(--panel-bg);font-size:12px;color:var(--text-secondary)}.clip-metadata fieldset{border:0;padding:15px 0 0;display:grid;gap:12px}.clip-metadata label{display:flex;flex-direction:column;gap:7px}.clip-metadata input,.clip-metadata textarea{border:1px solid var(--border-color);border-radius:4px;padding:10px;font:inherit;background:var(--panel-bg);color:var(--text-primary)}.comic-empty{text-align:center;padding:50px 20px;background:var(--panel-bg);border:1px dashed var(--border-color);border-radius:8px;color:var(--text-secondary)}.comic-empty svg{color:var(--accent-color);margin-bottom:18px}.comic-empty h3{font-size:17px;color:var(--text-primary)}.review-panel{background:var(--panel-bg);border:1px solid var(--border-color);border-radius:8px;padding:24px}.review-panel header{display:flex;justify-content:space-between;align-items:center;gap:18px;margin-bottom:18px}.review-summary{padding:14px;background:var(--surface-subtle);margin-bottom:14px}.review-issue{width:100%;background:var(--surface-subtle);border:1px solid var(--border-color);border-radius:5px;padding:13px;text-align:left;display:flex;align-items:center;gap:13px;color:var(--text-primary);margin-top:10px;cursor:pointer}.review-issue b{font-size:10px;color:var(--text-secondary);white-space:nowrap}.review-issue.error b{color:var(--accent-color)}.review-issue span{font-size:12px;line-height:1.7}.review-issue small{margin-left:auto;white-space:nowrap;font-size:10px;color:var(--text-secondary)}.progress-panel{display:flex;align-items:center;gap:10px;font-size:12px;color:var(--text-secondary);padding:10px}.spinner{width:13px;height:13px;border:2px solid var(--accent-border);border-top-color:var(--accent-color);border-radius:50%;animation:turn .8s linear infinite}@keyframes turn{to{transform:rotate(360deg)}}@media(max-width:1100px){.production-workspace{grid-template-columns:170px minmax(0,1fr)}.comic-overview{gap:28px}.control-panel{flex-wrap:wrap}.control-panel label{min-width:100%;flex-basis:100%}}@media(max-width:700px){.production-workspace{grid-template-columns:1fr}.clip-sidebar{display:flex;overflow:auto}.clip-sidebar-title{white-space:nowrap}.clip-option{min-width:150px;width:auto;border-top:0;border-left:1px solid var(--border-color)}.comic-overview{flex-wrap:wrap;gap:20px}.production-state{margin-left:0}.production-header{align-items:flex-start}.production-header h2{font-size:21px}.draft-toolbar{flex-wrap:wrap}.review-panel{padding:16px}.review-panel header{align-items:flex-start;flex-direction:column}.review-issue{align-items:flex-start}.review-issue small{display:none}.export-toolbar>div{flex-wrap:wrap}}
</style>
