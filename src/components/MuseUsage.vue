<script setup>
import { computed } from 'vue'
const props = defineProps({ usage: Object, loading: Boolean, error: String })
defineEmits(['refresh'])
const updated = computed(() => props.usage?.checkedAt ? new Date(props.usage.checkedAt * 1000).toLocaleString('zh-CN', { month:'numeric', day:'numeric', hour:'2-digit', minute:'2-digit' }) : '')
</script>

<template>
  <section class="muse-usage" aria-label="Muse 账户用量">
    <div class="usage-heading"><strong>账户用量</strong><button :disabled="loading" @click="$emit('refresh')">{{ loading ? '正在读取…' : '刷新额度' }}</button></div>
    <div v-if="usage?.rows?.length" class="usage-grid">
      <article v-for="(row,index) in usage.rows" :key="index" class="usage-meter">
        <div class="usage-label"><span>{{ row.kind === 'weekly' ? '每周额度 · ' + row.label : row.label }}</span><strong>{{ row.valueLabel }}</strong></div>
        <div class="usage-progress" role="progressbar" :aria-label="row.label" :aria-valuenow="row.usedPercent" aria-valuemin="0" aria-valuemax="100"><span :style="{width:row.usedPercent+'%'}"></span></div>
        <p>{{ row.description }}</p>
      </article>
    </div>
    <p v-else class="usage-empty" role="status">{{ loading ? '正在从 Muse 设置读取真实用量…' : '尚未读取额度，点击“刷新额度”获取。' }}</p>
    <p v-if="error" class="usage-error" role="alert">{{ error }}{{ usage ? ' 当前显示上次读取的结果。' : '' }}</p>
    <p v-if="updated" class="usage-footnote">来自 Muse 设置 · {{ updated }} 更新。周额度与额外余额分别计算。</p>
  </section>
</template>

<style scoped>
.muse-usage { margin:16px 0; padding:16px; border:1px solid var(--border-color); border-radius:8px; background:var(--surface-subtle); }
.usage-heading { display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:16px; }
.usage-heading strong { font-size:13px; font-weight:600; color:var(--text-primary); }
.usage-heading button { padding:6px 10px; background:var(--panel-bg); color:var(--text-secondary); border:1px solid var(--border-color); border-radius:5px; font-size:12px; white-space:nowrap; }
.usage-heading button:disabled { opacity:.5; }
.usage-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:20px; }
.usage-meter { min-width:0; }
.usage-label { display:flex; flex-direction:column; gap:8px; font-size:12px; color:var(--text-secondary); overflow-wrap:anywhere; }
.usage-label strong { color:var(--text-primary); font-size:14px; font-weight:500; }
.usage-progress { height:5px; border-radius:4px; overflow:hidden; background:var(--border-color); margin:12px 0 8px; }
.usage-progress>span { display:block; height:100%; background:var(--accent-color); }
.usage-meter p,.usage-empty,.usage-footnote { margin:0; font-size:12px; line-height:1.8; color:var(--text-secondary); }
.usage-footnote { margin-top:14px; font-size:11px; }
.usage-error { margin:10px 0 0; color:var(--danger-color); font-size:12px; line-height:1.7; }
@media(max-width:800px) { .usage-grid { grid-template-columns:1fr; gap:18px; } }
</style>
