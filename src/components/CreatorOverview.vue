<script setup>
import { computed } from 'vue'
import { store } from '../store.js'
import UiIcon from './UiIcon.vue'
import ParticleBackdrop from './ParticleBackdrop.vue'

const works = computed(() => store.works || [])
const chapters = work => (work.chapters || []).flatMap(v => v.chapters || [])
const overview = computed(() => {
  const all = works.value.flatMap(chapters)
  return [
    { label: '创作作品', value: works.value.length, unit: '部', icon: 'book' },
    { label: '累计正文字数', value: all.reduce((n, c) => n + (c.content || '').length, 0).toLocaleString('zh-CN'), unit: '字', icon: 'pen' },
    { label: '已写章节', value: all.filter(c => (c.content || '').trim()).length, unit: '章', icon: 'layers' },
    { label: '漫剧分镜', value: all.reduce((n, c) => n + (c.comicShots || []).length, 0), unit: '镜', icon: 'film' }
  ]
})
const openWork = (work, page = '写作编辑器') => {
  store.activeWorkId = work.id
  store.activeMenuItem = page
}
const openTool = page => {
  if (!works.value.length) { store.activeMenuItem = '我的作品'; return }
  if (!works.value.some(w => w.id === store.activeWorkId)) store.activeWorkId = works.value[0].id
  store.activeMenuItem = page
}
const startNovel = () => {
  document.getElementById('novel-starter')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  document.querySelector('#novel-starter textarea')?.focus({ preventScroll: true })
}
</script>

<template>
  <section class="creator-overview" aria-label="创作中心">
    <div class="creator-welcome">
      <ParticleBackdrop v-if="store.generalSettings.particleEffects !== false" />
      <div class="creator-welcome-copy"><span class="creator-eyebrow">我的创作工作台</span><h2>好故事，从这里开始</h2><p>小说创作、故事拆解、漫剧分镜，在一个工作台完成。</p></div>
      <button class="creator-main-button" @click="startNovel"><UiIcon name="plus" :size="17" />新建作品</button>
    </div>
    <section class="creator-metrics" aria-label="创作数据概览">
      <div v-for="item in overview" :key="item.label" class="creator-metric"><div class="metric-label">{{ item.label }}<UiIcon :name="item.icon" :size="17" /></div><div class="metric-number">{{ item.value }}<span>{{ item.unit }}</span></div></div>
    </section>
    <section class="creator-section" aria-label="创作入口">
      <div class="creator-section-heading"><h3>开始创作</h3><span>从文字到分镜，找到你的下一步</span></div>
      <div class="creator-entries">
        <button class="creator-entry" @click="openTool('写作编辑器')"><span class="entry-icon"><UiIcon name="pen" :size="24" /></span><span><strong>小说创作</strong><small>续写、润色，打磨你的故事</small></span><UiIcon name="arrow" :size="17" /></button>
        <button class="creator-entry" @click="openTool('漫剧工坊')"><span class="entry-icon film-entry"><UiIcon name="film" :size="24" /></span><span><strong>漫剧拆解</strong><small>章节转分镜，提取画面与台词</small></span><UiIcon name="arrow" :size="17" /></button>
        <button class="creator-entry" @click="openTool('人物工坊')"><span class="entry-icon people-entry"><UiIcon name="users" :size="24" /></span><span><strong>人物与设定</strong><small>让角色、世界和情节相互连接</small></span><UiIcon name="arrow" :size="17" /></button>
      </div>
    </section>
    <section class="creator-section creator-recent" aria-label="最近作品">
      <div class="creator-section-heading"><h3>最近作品</h3><button class="creator-text-button" @click="store.activeMenuItem = '我的作品'">全部作品<UiIcon name="arrow" :size="14" /></button></div>
      <div v-if="!works.length" class="creator-empty"><UiIcon name="book" :size="28" /><p>还没有作品，写下第一个灵感吧。</p><button class="creator-text-button" @click="startNovel">开始新故事 <UiIcon name="arrow" :size="15" /></button></div>
      <div v-for="work in works.slice(0, 3)" :key="work.id" class="creator-work-row">
        <div class="creator-book-cover" :style="{ '--cover': work.cover || 'var(--accent-color)' }"><UiIcon name="book" :size="22" /></div>
        <div class="creator-work-info"><strong>{{ work.title }}</strong><span>{{ (work.tags || []).slice(0, 3).join(' / ') || '原创小说' }}<b>·</b>{{ chapters(work).length }} 章</span></div>
        <span class="creator-work-status" :class="{ interrupted: work.status === '生成中断' }">{{ work.status || '草稿' }}</span>
        <div class="creator-work-actions"><button @click="openWork(work)">继续创作</button><button class="creator-text-button" @click="openWork(work, '漫剧工坊')">拆解分镜<UiIcon name="arrow" :size="14" /></button></div>
      </div>
    </section>
  </section>
</template>

<style scoped>
.creator-overview { display:flex; flex-direction:column; gap:22px; }
.creator-welcome { position:relative; isolation:isolate; display:flex; align-items:center; justify-content:space-between; gap:20px; padding:8px 0 4px; }
.creator-welcome-copy,.creator-main-button { position:relative; z-index:1; }
.creator-eyebrow { font-size:12px; color:var(--text-secondary); }
.creator-welcome h2 { margin:7px 0 8px; font-size:26px; font-weight:650; letter-spacing:.3px; }
.creator-welcome p { margin:0; color:var(--text-secondary); font-size:13px; }
.creator-main-button { display:flex; align-items:center; gap:7px; padding:11px 19px; border:0; border-radius:6px; background:var(--accent-color); color:#fff; font-size:13px; white-space:nowrap; }
.creator-main-button:hover { background:var(--accent-hover); }
.creator-metrics { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); background:var(--panel-bg); border-radius:8px; border:1px solid var(--border-color); padding:23px 0; }
.creator-metric { padding:0 25px; border-right:1px solid var(--border-color); min-width:0; }
.creator-metric:last-child { border-right:0; }
.metric-label { display:flex; align-items:center; justify-content:space-between; gap:8px; font-size:12px; color:var(--text-secondary); }
.metric-label svg { color:var(--text-category); }
.metric-number { margin-top:12px; font-size:29px; font-weight:600; font-variant-numeric:tabular-nums; line-height:1.2; }
.metric-number span { font-size:11px; color:var(--text-secondary); margin-left:6px; font-weight:400; }
.creator-section { background:var(--panel-bg); padding:21px 24px; border:1px solid var(--border-color); border-radius:8px; }
.creator-section-heading { display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:18px; }
.creator-section-heading h3 { font-size:15px; font-weight:600; margin:0; }
.creator-section-heading>span { font-size:12px; color:var(--text-category); }
.creator-entries { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px; }
.creator-entry { background:var(--surface-subtle); border:1px solid transparent; border-radius:6px; padding:19px 14px; text-align:left; display:flex; align-items:center; gap:12px; color:var(--text-primary); min-width:0; }
.creator-entry:hover { background:var(--accent-bg); border-color:var(--accent-border); }
.entry-icon { display:flex; align-items:center; justify-content:center; width:42px; height:44px; border-radius:7px; background:var(--accent-bg); color:var(--accent-color); flex-shrink:0; }
.film-entry,.people-entry { background:var(--surface-subtle); color:var(--text-secondary); }
.creator-entry>span:nth-child(2) { min-width:0; flex:1; }
.creator-entry strong { display:block; font-size:14px; font-weight:600; }
.creator-entry small { display:block; font-size:11px; color:var(--text-secondary); margin-top:5px; line-height:1.5; }
.creator-entry>svg { color:var(--text-category); }
.creator-text-button { display:inline-flex; align-items:center; justify-content:center; gap:6px; background:none; border:0; color:var(--text-secondary); font-size:12px; padding:3px 0; }
.creator-text-button:hover { color:var(--accent-color); }
.creator-work-row { display:flex; align-items:center; gap:15px; padding:15px 0; border-top:1px solid var(--border-color); }
.creator-book-cover { width:44px; height:56px; flex-shrink:0; display:flex; align-items:center; justify-content:center; color:#fff; background:var(--cover); border-radius:3px 6px 6px 3px; box-shadow:inset 3px 0 #ffffff30; }
.creator-work-info { min-width:0; flex:1; }
.creator-work-info strong { display:block; font-size:13px; font-weight:500; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.creator-work-info>span { display:block; font-size:11px; margin-top:7px; color:var(--text-category); }
.creator-work-info b { font-weight:400; margin:0 8px; }
.creator-work-status { padding:4px 8px; border-radius:4px; background:var(--surface-subtle); color:var(--text-secondary); font-size:11px; white-space:nowrap; }
.creator-work-status.interrupted { color:var(--accent-color); background:var(--accent-bg); }
.creator-work-actions { display:flex; gap:16px; margin-left:18px; }
.creator-work-actions>button:first-child { background:var(--panel-bg); border:1px solid var(--border-color); color:var(--text-primary); padding:7px 12px; border-radius:4px; font-size:12px; white-space:nowrap; }
.creator-work-actions>button:first-child:hover { border-color:var(--accent-color); color:var(--accent-color); }
.creator-empty { text-align:center; padding:24px; color:var(--text-category); font-size:13px; }
.creator-empty p { margin:10px 0; }
@media(max-width:1180px) { .creator-entries{gap:9px} .creator-entry{padding:16px 10px;gap:8px} .entry-icon{width:33px;height:38px} .creator-entry>svg{display:none} .creator-metric{padding:0 18px} .metric-number{font-size:25px} }
@media(max-width:900px) { .creator-welcome h2{font-size:23px} .creator-work-actions{gap:10px;margin-left:0} .creator-entries{grid-template-columns:1fr} .creator-entry{padding:14px 17px} .creator-entry>svg{display:block} .creator-section-heading>span{display:none} }
@media(max-width:600px) { .creator-welcome{align-items:flex-start;flex-direction:column;gap:15px} .creator-metrics{grid-template-columns:repeat(2,minmax(0,1fr));row-gap:23px} .creator-metric:nth-child(2){border-right:0} .creator-metric{padding:0 15px} .metric-number{font-size:24px} .creator-section{padding:18px 15px} .creator-work-row{gap:11px;flex-wrap:wrap} .creator-work-status{display:none} .creator-work-actions{width:100%;padding-left:55px} .creator-work-info strong{white-space:normal} }
</style>
