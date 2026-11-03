<script setup>
import { ref, watch, onUnmounted } from 'vue'
import { apiFetch } from '../api.js'
const props = defineProps({ url: String, title: String })
const source = ref('')
const error = ref('')
let version = 0
let objectUrl = ''
watch(() => props.url, async url => {
  const request = ++version
  if (objectUrl) URL.revokeObjectURL(objectUrl)
  objectUrl = ''; source.value = ''; error.value = ''
  if (!url) return
  if (!url.startsWith('/api/uploads/')) {
    if (/^https?:\/\//.test(url)) source.value = url
    else error.value = '请重新上传旧版临时图片'
    return
  }
  try {
    const blob = await (await apiFetch(url)).blob()
    if (version !== request) return
    objectUrl = URL.createObjectURL(blob)
    source.value = objectUrl
  } catch { if (version === request) error.value = '图片加载失败' }
}, { immediate: true })
onUnmounted(() => { version++; if (objectUrl) URL.revokeObjectURL(objectUrl) })
</script>
<template>
  <div class="material-picture"><img v-if="source" :src="source" :alt="title || '素材图片'" /><span v-else>{{ error || '加载中…' }}</span></div>
</template>
<style scoped>
.material-picture { width: 100%; height: 160px; background: var(--hover-bg); display: grid; place-items: center; color: var(--text-secondary); }
img { width: 100%; height: 100%; object-fit: cover; }
</style>
