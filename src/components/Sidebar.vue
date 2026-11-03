<script setup>
import { ref, nextTick } from 'vue'
import { store } from '../store.js'
import UiIcon from './UiIcon.vue'

const sourceGroups = [
  {
    title: '',
    items: [
      { name: '首页', icon: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path><polyline points="9 22 9 12 15 12 15 22"></polyline></svg>` },
      { name: '我的作品', icon: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>` }
    ]
  },
  {
    title: '创作工作台',
    items: [
      { name: '仪表盘', icon: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="9"></rect><rect x="14" y="3" width="7" height="5"></rect><rect x="14" y="12" width="7" height="9"></rect><rect x="3" y="16" width="7" height="5"></rect></svg>` },
      { name: '写作编辑器', icon: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19l7-7 3 3-7 7-3-3z"></path><path d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18l5-5z"></path><path d="M2 2l7.586 7.586"></path><circle cx="11" cy="11" r="2"></circle></svg>` },
      { name: '故事结构', icon: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="18" r="3"></circle><circle cx="6" cy="6" r="3"></circle><path d="M13 6h3a2 2 0 0 1 2 2v7"></path><line x1="6" y1="9" x2="6" y2="21"></line></svg>` }
    ]
  },
  {
    title: '世界观构建',
    items: [
      { name: '人物工坊', icon: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>` },
      { name: '世界观构筑', icon: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>` },
      { name: '情节引擎', icon: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>` }
    ]
  },
  {
    title: '工具与分析',
    items: [
      { name: '章节管理', icon: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path></svg>` },
      { name: '漫剧工坊', icon: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18"></rect><line x1="7" y1="2" x2="7" y2="22"></line><line x1="17" y1="2" x2="17" y2="22"></line><line x1="2" y1="12" x2="22" y2="12"></line><line x1="2" y1="7" x2="7" y2="7"></line><line x1="2" y1="17" x2="7" y2="17"></line><line x1="17" y1="17" x2="22" y2="17"></line><line x1="17" y1="7" x2="22" y2="7"></line></svg>` },
      { name: 'AI对话助手', icon: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>` },
      { name: '灵感素材库', icon: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21h6"></path><path d="M10 17h4"></path><path d="M12 2v2"></path><path d="M2 12h2"></path><path d="M20 12h2"></path><path d="M4.93 4.93l1.41 1.41"></path><path d="M17.66 17.66l1.41 1.41"></path><path d="M17.66 4.93l-1.41 1.41"></path><path d="M4.93 17.66l1.41-1.41"></path><circle cx="12" cy="12" r="5"></circle></svg>` },
      { name: '写作分析', icon: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"></line><line x1="12" y1="20" x2="12" y2="4"></line><line x1="6" y1="20" x2="6" y2="14"></line></svg>` }
    ]
  },
  {
    title: '系统',
    items: [
      { name: '智能哨兵', icon: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>` },
      { name: '提示词工程', icon: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>` },
      { name: '策略与设置', icon: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>` }
    ]
  }
]

const allItems = sourceGroups.flatMap(group => group.items)
const menuOpen = ref(false)
const navigation = ref(null)
const expandButton = ref(null)
const closeMenu = () => { menuOpen.value = false; nextTick(() => expandButton.value?.focus()) }
const trapNavigation = event => {
  if (!menuOpen.value) return
  if (event.key === 'Escape') { event.preventDefault(); closeMenu(); return }
  if (event.key !== 'Tab') return
  const buttons = [...navigation.value.querySelectorAll('button')].filter(button => button.getClientRects().length)
  const first = buttons[0], last = buttons.at(-1)
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
}
const menuGroups = [
  { title: '', names: ['首页', '我的作品'] },
  { title: '文字创作', names: ['写作编辑器', '故事结构', '章节管理', '人物工坊', '世界观构筑', '情节引擎'] },
  { title: '漫剧制作', names: ['漫剧工坊'] },
  { title: '助手与素材', names: ['AI对话助手', '灵感素材库'] },
  { title: '分析与设置', names: ['仪表盘', '写作分析', '提示词工程', '策略与设置', '智能哨兵'] }
].map(group => ({ title: group.title, items: group.names.map(name => allItems.find(item => item.name === name)) }))
const handleSelect = (itemName) => {
  store.activeMenuItem = itemName
  if (menuOpen.value) closeMenu()
}
</script>

<template>
  <button v-if="menuOpen" class="navigation-scrim" aria-label="关闭导航" tabindex="-1" @click="closeMenu"></button>
  <aside ref="navigation" class="sidebar" :class="{ 'menu-open': menuOpen }" :role="menuOpen ? 'dialog' : undefined" :aria-modal="menuOpen ? 'true' : undefined" aria-label="创作导航" @keydown="trapNavigation">
    <button class="studio-brand" @click="handleSelect('首页')" aria-label="创作中心首页">
      <span class="studio-logo"><UiIcon name="layers" :size="23" /></span>
      <span class="studio-brand-text">AI 创作平台<small>小说 · 剧本 · 漫剧</small></span>
    </button>
    <button ref="expandButton" class="navigation-expand" :aria-expanded="menuOpen" :aria-label="menuOpen ? '收起导航' : '展开导航'" @click="menuOpen = !menuOpen"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16" /></svg><span>收起导航</span></button>
    <button class="sidebar-create" @click="handleSelect('首页')" aria-label="开始创作"><UiIcon name="plus" :size="17" /><span>开始创作</span></button>
    <div class="sidebar-scroll">
      <div v-for="(group, gIndex) in menuGroups" :key="gIndex" class="menu-group">
        <div v-if="group.title" class="category-title">{{ group.title }}</div>
        <ul class="menu-list">
          <li
            v-for="(item, iIndex) in group.items"
            :key="iIndex"
          >
            <button class="menu-item" :class="{ active: store.activeMenuItem === item.name }" :aria-label="item.name" :aria-current="store.activeMenuItem === item.name ? 'page' : undefined" @click="handleSelect(item.name)">
            <span class="menu-icon" v-html="item.icon"></span>
            <span class="menu-label">{{ item.name }}</span>
            <span v-if="item.name === '漫剧工坊'" class="menu-badge">AI</span>
            </button>
          </li>
        </ul>
      </div>
    </div>
    <div class="sidebar-footer"><span class="workspace-avatar">创</span><div>我的工作空间<small>本地创作 · 自动保存</small></div></div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: 240px;
  background-color: var(--sidebar-bg);
  height: 100%;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border-color);
  box-shadow: 2px 0 16px rgba(0, 0, 0, 0.015);
  z-index: 10;
}

.sidebar-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 24px 0 32px 0;
}

.sidebar-scroll::-webkit-scrollbar {
  width: 4px;
}
.sidebar-scroll::-webkit-scrollbar-thumb {
  background-color: var(--border-color);
  border-radius: 4px;
}

.menu-group {
  margin-bottom: 8px;
}

.category-title {
  padding: 16px 20px 8px 20px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-category);
  letter-spacing: 0.5px;
}

.menu-list {
  display: flex;
  flex-direction: column;
  padding: 0 12px;
}

.menu-item {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  margin: 2px 0;
  border-radius: 8px;
  cursor: pointer;
  color: var(--text-secondary);
  font-size: 14px;
  font-weight: 500;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  overflow: hidden;
}

.menu-item:hover {
  background-color: var(--hover-bg);
  color: var(--text-primary);
}

.menu-item.active {
  background-color: var(--accent-bg);
  color: var(--text-primary);
  font-weight: 600;
}

.menu-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  height: 0;
  width: 3px;
  background-color: var(--accent-color);
  border-radius: 0 4px 4px 0;
  transition: height 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.menu-item.active::before {
  height: 60%;
}

.menu-icon {
  margin-right: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0.75;
  transition: all 0.2s ease;
}

.menu-item:hover .menu-icon,
.menu-item.active .menu-icon {
  opacity: 1;
}

.menu-item.active .menu-icon {
  color: var(--accent-color);
}

.menu-label {
  white-space: nowrap;
}
</style>
