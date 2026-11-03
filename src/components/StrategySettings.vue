<script setup>
import OAuthAccounts from './OAuthAccounts.vue'
import { ref, computed } from 'vue'
import { store, flushAll, saveState } from '../store.js'

const activeTab = ref('通用设置')

const tabs = [
  { id: '通用设置', name: '通用设置', icon: '⚙️' },
  { id: 'AI 引擎策略', name: 'AI 引擎策略', icon: '☁️' },
  { id: '编辑器首选项', name: '编辑器首选项', icon: '✍️' }
]

const generalSettings = computed(() => store.generalSettings)

// === AI 引擎策略相关状态 ===
const newConfig = ref({
  name: '',
  apiKey: '',
  baseUrl: '',
  modelName: ''
})

const addConfig = () => {
  if (!newConfig.value.name || !newConfig.value.apiKey) {
    alert("请至少填写配置名称和 API Key")
    return
  }
  
  store.llmConfigs.push({
    id: 'cfg_' + Date.now(),
    name: newConfig.value.name,
    apiKey: newConfig.value.apiKey,
    baseUrl: newConfig.value.baseUrl,
    modelName: newConfig.value.modelName
  })
  
  newConfig.value = { name: '', apiKey: '', baseUrl: '', modelName: '' }
}

const deleteConfig = (id) => {
  if (id === 'default') {
    alert("默认配置不可删除")
    return
  }
  store.llmConfigs = store.llmConfigs.filter(c => c.id !== id)
}

const saveChanges = async () => {
  try { await flushAll(); if (saveState.error) throw new Error(saveState.error); alert('设置与作品已保存') }
  catch (e) { alert(e.message) }
}
</script>

<template>
  <div class="settings-container">
    <div class="header">
      <div>
        <!-- Removing redundant page-title h2 since it's now in the topbar -->
        <p class="page-desc">深度定制您的创作环境和 AI 底层引擎策略。</p>
      </div>
      <button class="save-btn" @click="saveChanges">保存更改</button>
    </div>

    <div class="settings-layout">
      <!-- Sidebar -->
      <aside class="settings-sidebar">
        <nav class="settings-nav">
          <button 
            v-for="tab in tabs" 
            :key="tab.id"
            class="nav-item"
            :class="{ active: activeTab === tab.id }"
            @click="activeTab = tab.id"
            :aria-pressed="activeTab === tab.id"
          >
            <span class="nav-icon">{{ tab.icon }}</span>
            <span class="nav-name">{{ tab.name }}</span>
          </button>
        </nav>
      </aside>

      <!-- Content Area -->
      <main class="settings-content">
        <h3 class="section-title">{{ activeTab }}</h3>
        
        <!-- 通用设置 -->
        <div v-if="activeTab === '通用设置'" class="settings-list">
          <div class="setting-item">
            <div class="setting-info">
              <h4>深色模式</h4>
              <p>切换整个应用的主题配色。</p>
            </div>
            <div class="setting-control">
              <select v-model="generalSettings.theme" class="ui-select">
                <option value="light">浅色模式 (Light)</option>
                <option value="dark">深色模式 (Dark)</option>
                <option value="system">跟随系统</option>
              </select>
            </div>
          </div>

          <div class="setting-item">
            <div class="setting-info">
              <h4>首页粒子特效</h4>
              <p>欢迎区的轻量粒子动效，支持鼠标互动；系统开启“减少动态效果”时自动停用。</p>
            </div>
            <div class="setting-control">
              <label class="toggle-switch">
                <input type="checkbox" v-model="generalSettings.particleEffects" aria-label="首页粒子特效">
                <span class="slider"></span>
              </label>
            </div>
          </div>

          <div class="setting-item">
            <div class="setting-info">
              <h4>自动保存到后端</h4>
              <p>开启后，系统将在后台自动保存您的创作进度。</p>
            </div>
            <div class="setting-control">
              <label class="toggle-switch">
                <input type="checkbox" v-model="generalSettings.autoSave">
                <span class="slider"></span>
              </label>
            </div>
          </div>

          <div class="setting-item">
            <div class="setting-info">
              <h4>自动保存间隔</h4>
              <p>当开启自动保存时，选择保存的时间间隔。</p>
            </div>
            <div class="setting-control">
              <select v-model="generalSettings.saveInterval" class="ui-select">
                <option value="2">停止输入 2 秒后</option>
                <option value="5">停止输入 5 秒后</option>
                <option value="10">停止输入 10 秒后</option>
              </select>
            </div>
          </div>
        </div>

        <!-- AI 引擎策略 -->
        <div v-if="activeTab === 'AI 引擎策略'" class="settings-list">
          <OAuthAccounts />
          
          <div class="ai-section">
            <h4 class="sub-title">1. Agent 智能路由 (动态绑定)</h4>
            <p class="sub-desc">为不同的智能体分配最合适的底层模型。</p>
            
            <div class="agent-routing-list">
              <div class="agent-card">
                <div class="agent-info">
                  <span class="agent-icon">✍️</span>
                  <div>
                    <div class="agent-name">Editor Agent (责任编辑)</div>
                    <div class="agent-desc">负责写作编辑器内的文本润色、长文本聊天对话。</div>
                  </div>
                </div>
                <select v-model="store.agentAssignments.EditorAgent" class="ui-select">
                  <option v-for="cfg in store.llmConfigs" :key="cfg.id" :value="cfg.id">{{ cfg.name }}</option>
                </select>
              </div>

              <div class="agent-card">
                <div class="agent-info">
                  <span class="agent-icon">📈</span>
                  <div>
                    <div class="agent-name">Plot Agent (情节推演)</div>
                    <div class="agent-desc">负责在情节引擎中推演转折点，需要极强的逻辑推理能力。</div>
                  </div>
                </div>
                <select v-model="store.agentAssignments.PlotAgent" class="ui-select">
                  <option v-for="cfg in store.llmConfigs" :key="cfg.id" :value="cfg.id">{{ cfg.name }}</option>
                </select>
              </div>

              <div class="agent-card">
                <div class="agent-info">
                  <span class="agent-icon">🌍</span>
                  <div>
                    <div class="agent-name">Lore Agent (世界观主笔)</div>
                    <div class="agent-desc">负责人物工坊、世界观设定的脑暴与脑洞扩展。</div>
                  </div>
                </div>
                <select v-model="store.agentAssignments.LoreAgent" class="ui-select">
                  <option v-for="cfg in store.llmConfigs" :key="cfg.id" :value="cfg.id">{{ cfg.name }}</option>
                </select>
              </div>
            </div>
          </div>

          <div class="ai-section" style="margin-top: 32px;">
            <h4 class="sub-title">2. 模型供应商库（API Key / 已授权账号）</h4>
            <p class="sub-desc">添加 API Key 或使用上方已连接账号。账号模式仅在浏览器保存账号引用，不保存 OAuth 令牌或 Muse 会话。</p>
            
            <div class="configs-grid">
              <div class="config-card" v-for="config in store.llmConfigs" :key="config.id">
                <div class="config-header">
                  <h5>{{ config.name }}</h5>
                  <button v-if="config.id !== 'default'" class="delete-btn" @click="deleteConfig(config.id)">删除</button>
                </div>
                <div class="config-body">
                  <p v-if="config.authType === 'account'">账号授权模型（登录和断开连接请在上方管理）</p>
                  <div class="input-group" v-if="config.authType !== 'account'">
                    <label>API Key</label>
                    <input type="password" v-model="config.apiKey" placeholder="sk-..." class="ui-input" />
                  </div>
                  <div class="input-group">
                    <label>Base URL</label>
                    <input :disabled="config.authType === 'account'" type="text" v-model="config.baseUrl" placeholder="https://api... (选填)" class="ui-input" />
                  </div>
                  <div class="input-group">
                    <label>默认模型</label>
                    <input :readonly="config.authType === 'account' && config.provider === 'muse'" type="text" v-model="config.modelName" placeholder="如 gpt-4o, deepseek-chat" class="ui-input" />
                  </div>
                </div>
              </div>
            </div>

            <div class="add-config-box">
              <h5>+ 添加新供应商</h5>
              <div class="add-grid">
                <input type="text" v-model="newConfig.name" placeholder="厂商名称 (如 DeepSeek)" class="ui-input" />
                <input type="text" v-model="newConfig.apiKey" placeholder="API Key" class="ui-input" />
                <input type="text" v-model="newConfig.baseUrl" placeholder="Base URL (选填)" class="ui-input" />
                <input type="text" v-model="newConfig.modelName" placeholder="模型名称 (选填)" class="ui-input" />
              </div>
              <button class="add-btn" @click="addConfig">保存供应商</button>
            </div>
          </div>

        </div>

        <!-- 编辑器首选项 -->
        <div v-if="activeTab === '编辑器首选项'" class="settings-list">
          <div class="settings-help"><h4>写作与保存</h4><p>正文会按通用设置里的间隔自动保存。离开页面前可通过顶部“保存作品”提交待保存内容；历史版本也在作品工具栏中。</p><h4>快速查找</h4><p>按 Ctrl / ⌘ + K 搜索当前作品的人物、设定和章节。</p><h4>与助手讨论</h4><p>先选择要引用的章节或世界观，再发送问题。Enter 发送，Shift + Enter 换行；回复可以复制，或插入指定章节。</p></div>
        </div>

      </main>
    </div>
  </div>
</template>

<style scoped>
.settings-container {
  padding: 32px 48px;
  max-width: 1200px;
  margin: 0 auto;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
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

.save-btn {
  background-color: var(--accent-color); /* Orange */
  color: white;
  border: none;
  padding: 10px 24px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.2s;
}

.save-btn:hover {
  background-color: var(--accent-hover);
}

.settings-layout {
  display: flex;
  background: var(--panel-bg);
  border-radius: 12px;
  border: 1px solid var(--border-color);
  min-height: 600px;
  overflow: hidden;
}

.settings-sidebar {
  width: 240px;
  background-color: var(--surface-subtle);
  border-right: 1px solid var(--border-color);
  padding: 24px 16px;
}

.nav-item {
  display: flex;
  width: 100%;
  border: 0;
  background: transparent;
  text-align: left;
  font: inherit;
  align-items: center;
  padding: 12px 16px;
  border-radius: 8px;
  margin-bottom: 8px;
  cursor: pointer;
  color: var(--text-secondary);
  transition: all 0.2s;
}

.nav-item:hover {
  background-color: var(--hover-bg);
}

.nav-item.active {
  background-color: var(--accent-bg);
  color: var(--accent-hover);
  font-weight: 600;
}

.nav-icon {
  margin-right: 12px;
  font-size: 16px;
}

.settings-content {
  flex: 1;
  padding: 32px 40px;
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 24px 0;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border-color);
}

.setting-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 24px 0;
  border-bottom: 1px solid var(--hover-bg);
}

.setting-info h4 {
  margin: 0 0 6px 0;
  font-size: 15px;
  font-weight: 500;
  color: var(--text-primary);
}

.setting-info p {
  margin: 0;
  font-size: 13px;
  color: var(--text-secondary);
}

.ui-select {
  padding: 8px 36px 8px 12px;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  background-color: var(--panel-bg);
  font-size: 14px;
  color: var(--text-primary);
  outline: none;
  min-width: 180px;
}

.ui-input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  font-size: 14px;
  box-sizing: border-box;
}

/* Toggle Switch */
.toggle-switch {
  position: relative;
  display: inline-block;
  width: 44px;
  height: 24px;
}
.toggle-switch input {
  opacity: 0;
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  margin: 0;
  z-index: 1;
  cursor: pointer;
}
.toggle-switch input:focus-visible + .slider { outline: 2px solid var(--accent-color); outline-offset: 3px; }
.slider {
  position: absolute;
  cursor: pointer;
  top: 0; left: 0; right: 0; bottom: 0;
  background-color: var(--border-color);
  transition: .4s;
  border-radius: 24px;
}
.slider:before {
  position: absolute;
  content: "";
  height: 18px;
  width: 18px;
  left: 3px;
  bottom: 3px;
  background-color: var(--panel-bg);
  transition: .4s;
  border-radius: 50%;
}
input:checked + .slider {
  background-color: var(--accent-color);
}
input:checked + .slider:before {
  transform: translateX(20px);
}

/* AI Engine Specific Styles */
.sub-title {
  font-size: 15px;
  font-weight: 600;
  margin: 0 0 4px 0;
  color: var(--text-primary);
}

.sub-desc {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0 0 16px 0;
}

.agent-routing-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.agent-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--surface-subtle);
  padding: 16px 20px;
  border-radius: 8px;
  border: 1px solid var(--border-color);
}

.agent-info {
  display: flex;
  align-items: center;
  gap: 16px;
}
.agent-icon { font-size: 24px; }
.agent-name { font-weight: 600; font-size: 14px; color: var(--text-primary); margin-bottom: 4px; }
.agent-desc { font-size: 12px; color: var(--text-secondary); }

.configs-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 24px;
}

.config-card {
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 16px;
  background: var(--panel-bg);
}

.config-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.config-header h5 {
  margin: 0;
  font-size: 14px;
  color: var(--text-primary);
}

.delete-btn {
  background: var(--danger-bg);
  color: var(--danger-color);
  border: none;
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
}

.input-group {
  margin-bottom: 12px;
}
.input-group label {
  display: block;
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.add-config-box {
  background: var(--surface-subtle);
  border: 1px dashed var(--border-color);
  border-radius: 8px;
  padding: 20px;
}
.add-config-box h5 {
  margin: 0 0 16px 0;
  font-size: 14px;
}

.add-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 16px;
}

.add-btn {
  width: 100%;
  background: var(--hover-bg);
  border: 1px solid var(--border-color);
  color: var(--text-primary);
  padding: 10px;
  border-radius: 6px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}
.add-btn:hover {
  background: var(--border-color);
}

.placeholder-text {
  color: var(--text-secondary);
  font-size: 14px;
  text-align: center;
  padding: 40px;
}
</style>
