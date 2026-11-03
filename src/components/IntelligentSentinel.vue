<script setup>
import { ref } from 'vue'
import { apiFetch } from '../api.js'
const logs = ref([{ id: 1, type: 'info', time: '-', msg: '版权与舆情监控尚未接入。本面板仅检查后端连接状态。' }])
const isScanning = ref(false)
const checkHealth = async () => {
  isScanning.value = true
  try {
    const status = await (await apiFetch('/health')).json()
    logs.value.unshift({ id: Date.now(), type: 'info', time: new Date().toLocaleTimeString(), msg: `后端连接正常；运行模式：${status.mode}；检索：${status.retrieval}。` })
  } catch (e) { logs.value.unshift({ id: Date.now(), type: 'warning', time: new Date().toLocaleTimeString(), msg: e.message }) }
  finally { isScanning.value = false }
}
</script>

<template>
  <div class="sentinel-container">
    <div class="header-actions">
      <div>
        <h2 class="page-title">智能哨兵</h2>
        <p class="page-desc">检查后端服务连接。版权和舆情监控尚未接入。</p>
      </div>
      <div class="status-badge" :class="{ scanning: isScanning }">
        <span class="pulse-dot"></span>
        {{ isScanning ? '检查中' : '监控未启用' }}
      </div>
    </div>

    <button @click="checkHealth" :disabled="isScanning">检查后端连接</button>
    <div class="sentinel-grid">
      <!-- Radar Section -->
      <div class="radar-card">
        <h3 class="card-title">版权监控（尚未接入）</h3>
        <div class="radar-visual">
          <div class="radar">
          </div>
        </div>
        <div class="radar-stats">
          <div class="stat-box">
            <span class="stat-num">—</span>
            <span class="stat-label">今日发现侵权</span>
          </div>
          <div class="stat-box">
            <span class="stat-num" style="color: var(--text-secondary);">未启用</span>
            <span class="stat-label">版权健康度</span>
          </div>
        </div>
      </div>

      <!-- Logs Section -->
      <div class="logs-card">
        <h3 class="card-title">服务检查记录</h3>
        <div class="terminal">
          <div class="terminal-header">
            <span class="btn close"></span>
            <span class="btn min"></span>
            <span class="btn max"></span>
            <span class="title">sentinel_process@ai-core ~</span>
          </div>
          <div class="terminal-body">
            <TransitionGroup name="list">
              <div v-for="log in logs" :key="log.id" class="log-line">
                <span class="log-time">[{{ log.time }}]</span>
                <span class="log-type" :class="log.type">{{ log.type.toUpperCase() }}</span>
                <span class="log-msg">{{ log.msg }}</span>
              </div>
            </TransitionGroup>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.sentinel-container {
  padding: 32px;
  max-width: 1200px;
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

.status-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  background-color: var(--surface-subtle);
  color: var(--text-secondary);
  padding: 8px 16px;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 600;
  border: 1px solid var(--border-color);
}

.pulse-dot {
  width: 8px;
  height: 8px;
  background-color: var(--text-category);
  border-radius: 50%;
  
}

.sentinel-grid {
  display: grid;
  grid-template-columns: 1fr 2fr;
  gap: 24px;
}

/* Radar Card */
.radar-card {
  background: var(--panel-bg);
  border-radius: 16px;
  padding: 24px;
  border: 1px solid var(--border-color);
  box-shadow: 0 4px 16px rgba(0,0,0,0.02);
  display: flex;
  flex-direction: column;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 24px 0;
}

.radar-visual {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 20px 0;
}

.radar {
  width: 200px;
  height: 200px;
  border-radius: 50%;
  border: 1px solid var(--border-color);
  background: var(--surface-subtle);
  position: relative;
  overflow: hidden;
}

.radar::before, .radar::after {
  content: '';
  position: absolute;
  background: var(--border-color);
}

.radar::before {
  top: 0; bottom: 0; left: 50%; width: 1px;
}

.radar::after {
  left: 0; right: 0; top: 50%; height: 1px;
}

.radar-stats {
  display: flex;
  justify-content: space-around;
  margin-top: auto;
  padding-top: 24px;
  border-top: 1px solid var(--border-color);
}

.stat-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.stat-num {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
}

.stat-label {
  font-size: 12px;
  color: var(--text-category);
}

/* Terminal */
.logs-card {
  background: var(--panel-bg);
  border-radius: 16px;
  padding: 24px;
  border: 1px solid var(--border-color);
  box-shadow: 0 4px 16px rgba(0,0,0,0.02);
  display: flex;
  flex-direction: column;
}

.terminal {
  flex: 1;
  background-color: var(--text-primary);
  border-radius: 12px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: inset 0 2px 10px rgba(0,0,0,0.2);
}

.terminal-header {
  background-color: var(--text-primary);
  padding: 10px 16px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.terminal-header .btn {
  width: 12px;
  height: 12px;
  border-radius: 50%;
}
.close { background-color: var(--text-category); }
.min { background-color: var(--text-category); }
.max { background-color: var(--text-category); }

.terminal-header .title {
  margin-left: 12px;
  color: var(--text-category);
  font-size: 13px;
  font-family: monospace;
}

.terminal-body {
  padding: 16px;
  font-family: 'Fira Code', 'Courier New', Courier, monospace;
  font-size: 13px;
  overflow-y: auto;
  flex: 1;
  max-height: 400px;
}

.log-line {
  margin-bottom: 8px;
  line-height: 1.5;
  transition: all 0.3s;
}

.list-enter-active,
.list-leave-active {
  transition: all 0.5s ease;
}
.list-enter-from {
  opacity: 0;
  transform: translateX(-10px);
}

.log-time {
  color: var(--text-secondary);
  margin-right: 12px;
}

.log-type {
  display: inline-block;
  width: 70px;
  font-weight: 600;
}
.log-type.info { color: #3b82f6; }
.log-type.success { color: var(--success-color); }
.log-type.warning { color: var(--accent-color); }

.log-msg {
  color: var(--border-color);
}

@media (max-width: 1024px) {
  .sentinel-grid {
    grid-template-columns: 1fr;
  }
}
</style>
