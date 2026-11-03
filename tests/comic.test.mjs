import test from 'node:test'
import assert from 'node:assert/strict'
import * as comic from '../src/comic_production.js'

const clone=value=>JSON.parse(JSON.stringify(value))
function fixture() {
  const chapter={id:'c',title:'chapter',content:'阿遥说：“别关灯。”',comicShots:[{desc:'old protected shot',prompt:'old prompt',dialogue:''}]}
  const work={id:7,title:'demo',characters:[],chapters:[{chapters:[chapter]}]}
  comic.ensureComicProduction(work)
  work.comicProduction.settings.shotsPerClip=1
  const actor={...comic.newComicAsset('阿遥'),id:'actor',voice:'original voice',locked:true}
  work.comicProduction.bible.characters.push(actor)
  work.comicProduction.bible.scenes.push({...comic.newComicAsset('渡口'),id:'scene'})
  const calls=[];let cancelled=false
  const task={signal:new AbortController().signal,assertCurrent(){if(cancelled)throw new Error('cancelled')}}
  const request=async(url,options)=>{
    if(url.startsWith('/comic/prepare'))return {json:async()=>({sourceHash:await comic.comicHash(chapter.content),production:clone(work.comicProduction),previousContext:'',blocks:[{id:'B001',passages:[{id:'P0001',text:chapter.content}]}]})}
    const body=JSON.parse(options.body);calls.push(body.stage)
    if(body.stage==='breakdown')return {json:async()=>({bible:body.production.bible,beats:[{id:'beat',summary:'渡口对白',sourceIds:['P0001']}],clips:[{id:'clip',title:'登船',sceneId:'scene',characterIds:['actor'],sourceIds:['P0001'],beatIds:['beat'],summary:'对白'}]})}
    if(body.stage==='direct')return {json:async()=>({shots:[{...comic.emptyComicShot('clip',work.comicProduction.settings),id:'shot',shot:1,sceneId:'scene',characterIds:['actor'],sourceIds:['P0001'],duration:15,desc:'阿遥在船头',prompt:'harbor',lines:[{characterId:'actor',text:'别关灯。',emotion:'担忧'}],startState:'船头左侧',endState:'登船'}],endingState:'登船'})}
    return {json:async()=>({summary:'辅助审阅',issues:[]})}
  }
  return {work,chapter,calls,task,request,cancel:()=>{cancelled=true},options(){return {work,chapter,task,apiFetch:request,flushWork:async()=>{},configs:{breakdown:{apiKey:'fixture'},direct:{apiKey:'fixture'},review:{apiKey:'fixture'}}}}}
}

test('full comic workflow saves a resumable draft and preserves published shots until apply',async()=>{
  const f=fixture();await comic.runComicProduction(f.options())
  assert.deepEqual(f.calls,['breakdown','direct','review'])
  assert.equal(f.chapter.comicShots[0].desc,'old protected shot')
  assert.equal(f.chapter.comicDraft.status,'complete')
  assert.equal(f.chapter.comicDraft.bible.characters[0].voice,'original voice')
  await comic.applyComicDraft(f.work,f.chapter)
  assert.equal(f.chapter.comicShots[0].desc,'阿遥在船头')
  assert.equal(f.chapter.comicDraft,undefined)
  assert.equal(f.chapter.comicPlan.endingState,'登船')
})

test('resume reuses completed planning and directing instead of paying for them again',async()=>{
  const f=fixture();let fail=true
  const apiFetch=async(url,options)=>{
    if(options?.body && JSON.parse(options.body).stage==='review' && fail)throw new Error('temporary review failure')
    return f.request(url,options)
  }
  await assert.rejects(comic.runComicProduction({...f.options(),apiFetch}),/temporary review failure/)
  assert.equal(f.chapter.comicDraft.status,'interrupted')
  assert.equal(f.chapter.comicDraft.shots.length,1)
  fail=false;await comic.runComicProduction({...f.options(),apiFetch})
  assert.deepEqual(f.calls,['breakdown','direct','review'])
  assert.equal(f.chapter.comicDraft.status,'complete')
})

test('cancelled or stale-generation results never overwrite the existing storyboard',async()=>{
  for(const stale of [false,true]) {
    const f=fixture()
    const apiFetch=async(url,options)=>{
      const result=await f.request(url,options)
      if(options?.body && JSON.parse(options.body).stage==='direct') {
        if(stale)f.chapter.content='new manuscript';else f.cancel()
      }
      return result
    }
    await assert.rejects(comic.runComicProduction({...f.options(),apiFetch}),/cancelled|章节已修改/)
    assert.equal(f.chapter.comicShots[0].desc,'old protected shot')
    assert.equal(f.chapter.comicDraft.shots.length,0)
    assert.ok(!f.calls.includes('review'))
  }
})

test('changing source or locked settings after generation blocks applying an obsolete draft',async()=>{
  for(const changeSource of [true,false]) {
    const f=fixture();await comic.runComicProduction(f.options())
    if(changeSource)f.chapter.content='edited source';else f.work.comicProduction.bible.characters[0].voice='user edited voice'
    await assert.rejects(comic.applyComicDraft(f.work,f.chapter),/正文或草稿已变化|制作设定/)
    assert.equal(f.chapter.comicShots[0].desc,'old protected shot')
  }
})

test('legacy shots are viewed without silently changing saved data',()=>{
  const f=fixture();const before=JSON.stringify(f.chapter)
  const plan=comic.publishedComicPlan(f.work,f.chapter)
  assert.equal(plan.status,'imported');assert.equal(plan.shots[0].prompt,'old prompt')
  assert.equal(JSON.stringify(f.chapter),before)
})

test('rebasing adopts edited global voices and remaps proposed asset references',async()=>{
  const f=fixture();await comic.runComicProduction(f.options())
  const current=f.work.comicProduction.bible.characters[0]
  current.id='canonical-actor';current.voice='user confirmed voice'
  comic.rebaseComicDraft(f.work,f.chapter)
  const draft=f.chapter.comicDraft
  assert.equal(draft.shots[0].characterIds[0],'canonical-actor')
  assert.equal(draft.shots[0].lines[0].characterId,'canonical-actor')
  assert.equal(draft.bible.characters[0].voice,'user confirmed voice')
  assert.equal(draft.reviewedSignature,'');assert.deepEqual(draft.reviewedClips,[])
  await comic.applyComicDraft(f.work,f.chapter)
  assert.equal(f.chapter.comicShots[0].lines[0].characterId,'canonical-actor')
})

test('published locks and missing clip references block destructive application',async()=>{
  const f=fixture();await comic.runComicProduction(f.options());await comic.applyComicDraft(f.work,f.chapter)
  f.chapter.comicShots[0].locked=true
  f.chapter.comicDraft=clone(comic.publishedComicPlan(f.work,f.chapter))
  f.chapter.comicDraft.baseProduction=clone(f.work.comicProduction)
  f.chapter.comicDraft.status='manual';f.chapter.comicDraft.shots[0].desc='replacement'
  await assert.rejects(comic.applyComicDraft(f.work,f.chapter),/锁定/)
  f.chapter.comicShots[0].locked=false
  f.chapter.comicDraft.shots[0].clipId='missing'
  assert.ok(comic.reviewComicPlan(f.chapter.comicDraft).some(issue=>issue.code==='UNKNOWN_CLIP'))
  await assert.rejects(comic.applyComicDraft(f.work,f.chapter),/规则/)
  f.chapter.comicDraft.clips=[];f.chapter.comicDraft.shots=[]
  await assert.rejects(comic.applyComicDraft(f.work,f.chapter),/没有可应用/)
  assert.equal(f.chapter.comicShots[0].desc,'阿遥在船头')
})

test('rule checks identify unknown actors, long dialogue and missed source references',async()=>{
  const f=fixture();await comic.runComicProduction(f.options());const plan=f.chapter.comicDraft
  plan.shots[0].characterIds=['missing'];plan.shots[0].duration=.1;plan.shots[0].sourceIds=[]
  const codes=comic.reviewComicPlan(plan).map(issue=>issue.code)
  for(const code of ['UNKNOWN_ACTOR','DIALOGUE_DURATION','SOURCE_COVERAGE','DIALOGUE_CHANGED'])assert.ok(codes.includes(code))
})

test('exports include production data, Chinese video instructions, escaped CSV and timed subtitles',async()=>{
  const f=fixture();await comic.runComicProduction(f.options());const plan=f.chapter.comicDraft
  assert.ok(comic.exportComicPlan(plan,'demo','text').text.includes('original voice'))
  assert.ok(comic.exportComicPlan(plan,'demo','srt').text.includes('00:00:00,000 --> 00:00:15,000'))
  assert.equal(JSON.parse(comic.exportComicPlan(plan,'demo','json').text).production.shots.length,1)
  plan.shots[0].desc='=HYPERLINK("bad")'
  const csv=comic.exportComicPlan(plan,'demo','csv').text
  assert.ok(csv.includes("'=HYPERLINK"));assert.ok(csv.includes('""bad""'))
})
