// Production orchestration and export are independent from the Vue screen.
const clone = value => JSON.parse(JSON.stringify(value))
const uid = prefix => `${prefix}-${crypto.randomUUID()}`
export const comicSettings = () => ({style:'realistic',styleNotes:'',ratio:'9:16',targetDuration:15,shotsPerClip:5,speechRate:4,fidelity:'faithful',exportTarget:'seedance'})
export const emptyBible = () => ({characters:[],scenes:[],props:[]})
export const newComicAsset = name => ({id:uid('asset'),name,description:'',voice:'',lighting:'',axis:'',referenceUrl:'',locked:false})
export function ensureComicProduction(work) {
  if (!work.comicProduction?.schemaVersion) work.comicProduction={schemaVersion:1,settings:comicSettings(),bible:emptyBible()}
  work.comicProduction.settings ||= {}
  for(const [key,value] of Object.entries(comicSettings())) if(!(key in work.comicProduction.settings)) work.comicProduction.settings[key]=value
  work.comicProduction.bible ||= emptyBible()
  for(const key of ['characters','scenes','props']) work.comicProduction.bible[key] ||= []
  return work.comicProduction
}
export function syncComicCharacters(work) {
  const production=ensureComicProduction(work)
  for(const character of work.characters || []) if(character.name && !production.bible.characters.some(row=>row.name===character.name)) {
    production.bible.characters.push({...newComicAsset(character.name),description:character.description || ''})
  }
}
export async function comicHash(value) {
  const bytes=new TextEncoder().encode(typeof value==='string'?value:JSON.stringify(value))
  return [...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(byte=>byte.toString(16).padStart(2,'0')).join('')
}
export function comicSignature(plan) {
  return {sourceHash:plan.sourceHash,settings:plan.settings,bible:plan.bible,clips:plan.clips,shots:plan.shots,endingState:plan.endingState}
}
export function publishedComicPlan(work,chapter) {
  if (chapter.comicPlan) return {...chapter.comicPlan,shots:chapter.comicShots || []}
  if (!chapter.comicShots?.length) return null
  const production=work.comicProduction?.schemaVersion?work.comicProduction:{schemaVersion:1,settings:comicSettings(),bible:emptyBible()}
  return {schemaVersion:2,sourceHash:'',settings:{...comicSettings(),...production.settings},baseProduction:clone(production),bible:clone(production.bible),
    passages:[],completedBlocks:[],reviewedClips:[],beats:[],clips:[{id:'legacy',title:'原有分镜',sceneId:'',characterIds:[],sourceIds:[],beatIds:[],summary:''}],
    shots:chapter.comicShots.map((shot,i)=>({...emptyComicShot('legacy'),...shot,id:shot.id || `legacy-${i+1}`,shot:i+1,clipId:'legacy'})),
    status:'imported',endingState:'',previousContext:'',issues:[],reviewSummary:'',reviewedSignature:'',generatedAt:''}
}
export function emptyComicShot(clipId,settings=comicSettings()) {
  return {schemaVersion:2,id:uid('shot'),shot:1,clipId,sceneId:'',characterIds:[],sourceIds:[],duration:settings.targetDuration/settings.shotsPerClip,
    shotSize:'中景',camera:'固定',angle:'平视',composition:'',desc:'新镜头画面',dialogue:'',lines:[],prompt:'',videoPromptOverride:'',lighting:'',transition:'',sfx:'',startState:'',endState:'',locked:false}
}
export function mergeComicBible(current,incoming) {
  const result=clone(current)
  for(const kind of ['characters','scenes','props']) for(const row of incoming[kind] || []) {
    const existing=result[kind].find(asset=>asset.id===row.id || asset.name===row.name)
    if(!existing) result[kind].push(clone(row))
    else {
      if(existing.id!==row.id) throw new Error(`制作设定“${row.name}”有不同 ID，请先统一人物/场景引用`)
      if(!existing.locked) for(const key of ['description','voice','lighting','axis','referenceUrl']) if(!existing[key]) existing[key]=row[key] || ''
    }
  }
  return result
}
function checkProductionBaseline(plan,production) {
  const base=plan.baseProduction
  if(JSON.stringify(base.settings)!==JSON.stringify(production.settings)) throw new Error('制作参数已修改，请重新生成草稿')
  for(const kind of ['characters','scenes','props']) for(const asset of base.bible[kind]) {
    if(JSON.stringify(production.bible[kind].find(row=>row.id===asset.id))!==JSON.stringify(asset)) throw new Error(`制作设定“${asset.name}”已修改，请重新生成草稿`)
  }
}
export async function applyComicDraft(work,chapter) {
  const draft=chapter.comicDraft
  if(!draft || !['complete','manual','imported'].includes(draft.status)) throw new Error('请先完成制作草稿')
  if(!draft.clips.length || !draft.shots.length) throw new Error('草稿中没有可应用的片段与镜头')
  const source=chapter.content, before=JSON.stringify(draft)
  const hash=await comicHash(source)
  if(chapter.content!==source || chapter.comicDraft!==draft || JSON.stringify(draft)!==before || hash!==draft.sourceHash) throw new Error('正文或草稿已变化，未替换原分镜')
  if(reviewComicPlan(draft).some(issue=>issue.severity==='error')) throw new Error('请先修复规则检查中的错误，再应用分镜')
  const production=ensureComicProduction(work)
  checkProductionBaseline(draft,production)
  const bible=mergeComicBible(production.bible,draft.bible)
  const normalized=clone(draft)
  normalized.status='complete'
  for(const old of chapter.comicShots || []) if(old.locked) {
    const replacement=normalized.shots.find(shot=>shot.id===old.id)
    const content=shot=>Object.fromEntries(Object.entries(shot || {}).filter(([key])=>!['locked','shot'].includes(key)))
    if(!replacement || JSON.stringify(content(replacement))!==JSON.stringify(content(old))) throw new Error('存在已锁定的应用镜头，请先解锁或在草稿中完整保留该镜头')
    replacement.locked=true
  }
  normalized.bible=clone(bible)
  normalized.shots.forEach((shot,i)=>{shot.shot=i+1; if(shot.lines?.length) shot.dialogue=shot.lines.map(line=>`${bible.characters.find(row=>row.id===line.characterId)?.name || '旁白'}：${line.text}`).join('\n')})
  chapter.comicShots=normalized.shots
  chapter.comicPlan={...normalized,shots:[]}
  production.bible=bible
  delete chapter.comicDraft
}
export function rebaseComicDraft(work,chapter) {
  const draft=chapter.comicDraft
  if(!draft) throw new Error('请先创建制作草稿')
  const production=ensureComicProduction(work), bible=clone(production.bible), actorMap=new Map(),sceneMap=new Map()
  for(const kind of ['characters','scenes','props']) for(const old of draft.bible[kind]) {
    const current=bible[kind].find(row=>row.id===old.id || row.name===old.name)
    if(!current)bible[kind].push(clone(old))
    if(kind==='characters')actorMap.set(old.id,current?.id || old.id)
    if(kind==='scenes')sceneMap.set(old.id,current?.id || old.id)
  }
  for(const clip of draft.clips){clip.sceneId=sceneMap.get(clip.sceneId) || clip.sceneId;clip.characterIds=clip.characterIds.map(id=>actorMap.get(id) || id)}
  for(const shot of draft.shots){shot.sceneId=sceneMap.get(shot.sceneId) || shot.sceneId;shot.characterIds=shot.characterIds.map(id=>actorMap.get(id) || id);shot.lines.forEach(line=>line.characterId=actorMap.get(line.characterId) || line.characterId)}
  draft.bible=bible;draft.settings=clone(production.settings);draft.baseProduction=clone(production)
  draft.status='manual';draft.reviewedClips=[];draft.reviewedSignature='';draft.issues=[];draft.reviewSummary=''
}

export async function runComicProduction({work,chapter,task,apiFetch,flushWork,configs,onProgress=()=>{},resume=true,carryBible=null}) {
  task.assertCurrent()
  const source=chapter.content
  const sourceHash=await comicHash(source)
  const production=ensureComicProduction(work)
  let baseline=JSON.stringify(production)
  const assertUnedited=()=>{
    task.assertCurrent()
    if(!(work.chapters || []).some(volume=>(volume.chapters || []).includes(chapter)) || chapter.content!==source) throw new Error('章节已修改，本次生成已停止，现有分镜保留')
    if(JSON.stringify(work.comicProduction)!==baseline) throw new Error('制作设定已修改，本次生成已停止，现有分镜保留')
  }
  await flushWork(work.id)
  assertUnedited()
  const prepared=await (await apiFetch(`/comic/prepare?workId=${encodeURIComponent(work.id)}&chapterId=${encodeURIComponent(chapter.id)}`,{signal:task.signal})).json()
  assertUnedited()
  if(prepared.sourceHash!==sourceHash) throw new Error('后端正文与当前编辑不一致，请先完成保存')
  let draft=chapter.comicDraft
  if(!resume || !draft || draft.sourceHash!==sourceHash) {
    work.comicProduction=prepared.production
    baseline=JSON.stringify(work.comicProduction)
    draft={schemaVersion:2,sourceHash,settings:clone(prepared.production.settings),baseProduction:clone(prepared.production),
      bible:carryBible?mergeComicBible(prepared.production.bible,carryBible):clone(prepared.production.bible),
      passages:prepared.blocks.flatMap(block=>block.passages),completedBlocks:[],reviewedClips:[],beats:[],clips:[],shots:[],status:'planning',
      endingState:'',previousContext:prepared.previousContext,reviewSummary:'',issues:[],reviewedSignature:'',generatedAt:new Date().toISOString()}
    chapter.comicDraft=draft
    draft=chapter.comicDraft // Vue may wrap it in a proxy.
  } else checkProductionBaseline(draft,work.comicProduction)
  let expectedDraft=JSON.stringify(draft)
  const assertDraft=()=>{assertUnedited(); if(chapter.comicDraft!==draft || JSON.stringify(draft)!==expectedDraft) throw new Error('制作草稿已被编辑，本次任务已停止')}
  const save=async()=>{expectedDraft=JSON.stringify(draft);await flushWork(work.id);assertDraft()}
  const call=async(stage,ids)=>{
    assertDraft()
    const response=await apiFetch('/comic/stage',{method:'POST',signal:task.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({
      workId:work.id,chapterId:chapter.id,sourceHash,stage,...ids,config:configs[stage],
      production:{schemaVersion:1,settings:draft.settings,bible:draft.bible},plan:draft})})
    const result=await response.json();assertDraft();return result
  }
  try {
    for(const block of prepared.blocks) {
      if(draft.completedBlocks.includes(block.id)) continue
      onProgress(`编剧拆解 ${draft.completedBlocks.length+1} / ${prepared.blocks.length}`)
      const result=await call('breakdown',{blockId:block.id})
      if(draft.clips.length+result.clips.length>200) throw new Error('片段数量超过本章制作上限，请先拆分章节；已完成草稿保留')
      draft.bible=result.bible;draft.beats.push(...result.beats);draft.clips.push(...result.clips);draft.completedBlocks.push(block.id)
      await save()
    }
    draft.status='directing';await save()
    for(let i=0;i<draft.clips.length;i++) {
      const clip=draft.clips[i]
      if(draft.shots.some(shot=>shot.clipId===clip.id)) continue
      onProgress(`导演分镜 ${i+1} / ${draft.clips.length}`)
      const result=await call('direct',{clipId:clip.id})
      if(draft.shots.length+result.shots.length>500) throw new Error('镜头数量超过本章制作上限，请先拆分章节；草稿已保留')
      draft.shots.push(...result.shots);draft.endingState=result.endingState
      await save()
    }
    draft.status='reviewing';await save()
    for(let i=0;i<draft.clips.length;i++) {
      const clip=draft.clips[i]
      if(draft.reviewedClips.includes(clip.id)) continue
      onProgress(`连续性质检 ${i+1} / ${draft.clips.length}`)
      const result=await call('review',{clipId:clip.id})
      draft.issues.push(...result.issues);draft.issues=draft.issues.slice(0,100)
      draft.reviewSummary=result.summary;draft.reviewedClips.push(clip.id)
      await save()
    }
    const reviewedSignature=await comicHash(comicSignature(draft));assertDraft()
    draft.status='complete';draft.reviewedSignature=reviewedSignature
    await save()
    return draft
  } catch(error) {
    if(chapter.comicDraft===draft && JSON.stringify(draft)===expectedDraft) {draft.status='interrupted';await flushWork(work.id).catch(()=>{})}
    throw error
  }
}

export function reviewComicPlan(plan,{sourceChanged=false}={}) {
  if(!plan) return []
  const issues=[]
  const add=(severity,code,message,shotId='',clipId='')=>issues.push({severity,code,message,shotId,clipId})
  if(sourceChanged) add('error','SOURCE_CHANGED','正文已更新，请重新生成或重新核对原文引用')
  if(plan.settings.exportTarget==='seedance' && plan.settings.targetDuration>15) add('warning','TARGET_PRESET','当前选择即梦 / Seedance 制作模板，但单段超过 15 秒；请核对目标模型能力，或拆分片段/改用通用目标')
  const actors=new Map(plan.bible.characters.map(row=>[row.id,row]))
  const scenes=new Map(plan.bible.scenes.map(row=>[row.id,row]))
  const passages=new Map(plan.passages.map(row=>[row.id,row.text]))
  const cited=new Set(), ids=new Set(),clipIds=new Set()
  for(const clip of plan.clips) {
    if(clipIds.has(clip.id)) add('error','DUPLICATE_CLIP','片段 ID 重复','',clip.id)
    clipIds.add(clip.id)
    if(clip.sceneId && !scenes.has(clip.sceneId)) add('error','UNKNOWN_SCENE','片段引用了已删除的场景','',clip.id)
    for(const id of clip.characterIds) if(!actors.has(id)) add('error','UNKNOWN_ACTOR','片段引用了已删除的人物','',clip.id)
    for(const id of clip.sourceIds) if(!passages.has(id)) add('error','UNKNOWN_SOURCE','片段原文引用不存在','',clip.id)
    const shots=plan.shots.filter(shot=>shot.clipId===clip.id)
    if(!shots.length) {add('error','EMPTY_CLIP',`“${clip.title}”尚无分镜`,'',clip.id);continue}
    if(shots.length!==plan.settings.shotsPerClip && plan.status!=='imported') add('warning','SHOT_COUNT',`“${clip.title}”的镜头数与制作参数不同`,'',clip.id)
    const seconds=shots.reduce((sum,shot)=>sum+Number(shot.duration || 0),0)
    if(Math.abs(seconds-plan.settings.targetDuration)>.15) add('warning','CLIP_DURATION',`“${clip.title}”合计 ${seconds.toFixed(1)} 秒，目标 ${plan.settings.targetDuration} 秒`,'',clip.id)
  }
  for(const shot of plan.shots) {
    if(!clipIds.has(shot.clipId)) add('error','UNKNOWN_CLIP','镜头没有关联有效的制作片段',shot.id,shot.clipId)
    if(ids.has(shot.id)) add('error','DUPLICATE_SHOT','镜头 ID 重复',shot.id,shot.clipId)
    ids.add(shot.id)
    if(!Number.isFinite(Number(shot.duration)) || Number(shot.duration)<=0) add('error','DURATION','镜头时长无效',shot.id,shot.clipId)
    if(!shot.desc?.trim()) add('error','EMPTY_ACTION','缺少画面与动作描述',shot.id,shot.clipId)
    if(shot.sceneId && !scenes.has(shot.sceneId)) add('error','UNKNOWN_SCENE','镜头引用了已删除的场景',shot.id,shot.clipId)
    for(const id of shot.characterIds) if(!actors.has(id)) add('error','UNKNOWN_ACTOR','镜头引用了已删除的人物',shot.id,shot.clipId)
    for(const id of shot.sourceIds) {cited.add(id);if(!passages.has(id)) add('error','UNKNOWN_SOURCE','原文引用不存在',shot.id,shot.clipId)}
    const text=(shot.lines || []).map(line=>line.text).join('') || shot.dialogue || ''
    if([...text.replace(/[\s\p{P}]/gu,'')].length/plan.settings.speechRate>Number(shot.duration)+.5) add('warning','DIALOGUE_DURATION','按当前语速估算，台词可能无法在镜头时长内读完',shot.id,shot.clipId)
    for(const line of shot.lines || []) {
      const actor=actors.get(line.characterId)
      if(line.characterId && !actor) add('error','DIALOGUE_ACTOR','台词说话人不存在',shot.id,shot.clipId)
      else if(actor && !actor.voice.trim()) add('warning','VOICE_MISSING',`“${actor.name}”尚未设置固定声线`,shot.id,shot.clipId)
      if(plan.settings.fidelity==='faithful' && passages.size && !shot.sourceIds.some(id=>(passages.get(id) || '').replace(/\s/g,'').includes(line.text.replace(/\s/g,'')))) add('warning','DIALOGUE_CHANGED','忠实模式台词未在对应原文引用中找到，请人工确认',shot.id,shot.clipId)
    }
    if(!shot.startState || !shot.endState) add('info','CONTINUITY_MISSING','缺少起止位置、道具或情绪状态，建议补充',shot.id,shot.clipId)
  }
  const missing=[...passages.keys()].filter(id=>!cited.has(id))
  if(missing.length) add('warning','SOURCE_COVERAGE',`${missing.length} 段原文尚未关联镜头（引用覆盖不等于语义完整）`)
  if(!passages.size) add('info','UNLINKED_LEGACY','当前分镜未关联结构化原文引用，可继续编辑或重新制作')
  return issues
}

export function shotVideoPrompt(shot,plan) {
  if(shot.videoPromptOverride?.trim()) return shot.videoPromptOverride
  const scene=plan.bible.scenes.find(row=>row.id===shot.sceneId)
  const names=shot.characterIds.map(id=>plan.bible.characters.find(row=>row.id===id)).filter(Boolean)
  const spoken=(shot.lines || []).map(line=>{
    const actor=plan.bible.characters.find(row=>row.id===line.characterId)
    return `${actor?.name || '旁白'}${actor?.voice?`（${actor.voice}）`:''}${line.emotion?`，${line.emotion}`:''}：“${line.text}”`
  }).join('\n') || shot.dialogue
  return [
    `${({realistic:'真人写实',anime:'二维动漫','3d':'3D 国漫',custom:'自定义风格'})[plan.settings.style]}，${plan.settings.ratio}，镜头 ${Number(shot.duration).toFixed(1)} 秒。${plan.settings.styleNotes}`,
    scene?`场景：${scene.name}。${scene.description}`:'',
    names.length?`人物：${names.map(actor=>`${actor.name}（${actor.description}）`).join('；')}`:'',
    `镜头：${shot.shotSize}，${shot.angle}，${shot.camera}。${shot.composition || ''}`,
    `画面与动作：${shot.desc}`,`光影：${shot.lighting || scene?.lighting || '保持本场景光源连续'}`,
    scene?.axis?`空间与轴线：${scene.axis}`:'',shot.startState?`起始状态：${shot.startState}`:'',shot.endState?`结束状态：${shot.endState}`:'',
    spoken?`对白/旁白：\n${spoken}`:'',shot.sfx?`音效：${shot.sfx}`:'',shot.transition?`衔接：${shot.transition}`:''
  ].filter(Boolean).join('\n')
}
const srtTime=seconds=>{const ms=Math.round(seconds*1000);return `${String(Math.floor(ms/3600000)).padStart(2,'0')}:${String(Math.floor(ms/60000)%60).padStart(2,'0')}:${String(Math.floor(ms/1000)%60).padStart(2,'0')},${String(ms%1000).padStart(3,'0')}`}
const csvCell=value=>{let text=String(value ?? '');if(/^[=+@\-\t\r]/.test(text)) text="'"+text;return '"'+text.replaceAll('"','""')+'"'}
export function exportComicPlan(plan,title,format='text') {
  const safeTitle=('分镜-'+title).replace(/[<>:"/\\|?*\x00-\x1f]/g,'_').slice(0,100)
  if(format==='json') return {filename:safeTitle+'.json',mime:'application/json;charset=utf-8',text:JSON.stringify({title,production:plan},null,2)}
  if(format==='csv') {
    const rows=[['片段','镜头','时长秒','景别','运镜','画面','台词','中文视频提示词','英文图像提示词']]
    for(const clip of plan.clips) for(const shot of plan.shots.filter(row=>row.clipId===clip.id)) rows.push([clip.title,shot.shot,shot.duration,shot.shotSize,shot.camera,shot.desc,(shot.lines || []).map(line=>line.text).join('\n') || shot.dialogue,shotVideoPrompt(shot,plan),shot.prompt])
    return {filename:safeTitle+'.csv',mime:'text/csv;charset=utf-8',text:'\ufeff'+rows.map(row=>row.map(csvCell).join(',')).join('\r\n')}
  }
  if(format==='srt') {
    let time=0;const cues=[]
    for(const clip of plan.clips) for(const shot of plan.shots.filter(row=>row.clipId===clip.id)) {
      const lines=shot.lines?.length?shot.lines.map(line=>`${plan.bible.characters.find(row=>row.id===line.characterId)?.name || '旁白'}：${line.text}`):shot.dialogue?[shot.dialogue]:[]
      lines.forEach((line,i)=>cues.push(`${cues.length+1}\n${srtTime(time+shot.duration*i/lines.length)} --> ${srtTime(time+shot.duration*(i+1)/lines.length)}\n${line}\n`))
      time+=Number(shot.duration)
    }
    return {filename:safeTitle+'.srt',mime:'text/plain;charset=utf-8',text:cues.join('\n')}
  }
  const content=[`《${title}》制作分镜`,`${plan.settings.ratio} · ${plan.settings.style} · 目标每段 ${plan.settings.targetDuration} 秒`,
    '本文件为制作提示词，不代表已经生成视频、配音或绑定参考素材。',`上一章衔接：${plan.previousContext || '未引用'}`]
  for(const clip of plan.clips) {
    content.push(`\n【${clip.title}】${clip.summary || ''}`)
    for(const shot of plan.shots.filter(row=>row.clipId===clip.id)) content.push(`\nCut ${shot.shot}（${shot.duration} 秒）\n${plan.settings.exportTarget==='midjourney'?`${shot.prompt}\n--ar ${plan.settings.ratio}`:shotVideoPrompt(shot,plan)}`)
  }
  content.push(`\n结束状态：${plan.endingState || '未记录'}`)
  return {filename:safeTitle+'.txt',mime:'text/plain;charset=utf-8',text:content.join('\n\n')}
}
