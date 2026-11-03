<script setup>
import { computed } from 'vue'
import MaterialImage from './MaterialImage.vue'
import { newComicAsset, syncComicCharacters } from '../comic_production.js'
const props=defineProps({work:Object,production:Object,disabled:Boolean})
const images=computed(()=>(props.work.materials || []).filter(row=>row.type==='image' && /^\/api\/uploads\//.test(row.url || '')))
const groups=[{key:'characters',title:'人物与声线',hint:'保留外观特征与核心声线，语气可以随情绪变化。'},{key:'scenes',title:'场景与空间',hint:'记录空间锚点、主光方向与轴线，角色可按剧情合理移动。'},{key:'props',title:'道具与状态',hint:'记录关键物件的外观、持有者和状态。'}]
function add(kind) {props.production.bible[kind].push(newComicAsset(`新${kind==='characters'?'人物':kind==='scenes'?'场景':'道具'} ${props.production.bible[kind].length+1}`))}
function remove(kind,row) {if(confirm(`删除制作设定“${row.name}”？已生成分镜的快照仍保留。`)) props.production.bible[kind].splice(props.production.bible[kind].indexOf(row),1)}
</script>
<template>
  <section class="production-settings" aria-label="全剧制作设定">
    <div class="settings-heading"><div><h3>全剧制作设定</h3><p>用于后续生成；已应用分镜保留生成时的设定快照。</p></div><button class="btn-secondary" :disabled="disabled" @click="syncComicCharacters(work)">同步小说人物</button></div>
    <fieldset :disabled="disabled" class="settings-grid">
      <label>视觉风格<select v-model="production.settings.style"><option value="realistic">真人写实</option><option value="anime">二维动漫</option><option value="3d">3D 国漫</option><option value="custom">自定义风格</option></select></label>
      <label>画幅<select v-model="production.settings.ratio"><option>9:16</option><option>16:9</option><option>1:1</option></select></label>
      <label>每片段目标时长（秒）<input v-model.number="production.settings.targetDuration" type="number" min="3" max="120" /></label>
      <label>每片段镜头数<input v-model.number="production.settings.shotsPerClip" type="number" min="1" max="12" /></label>
      <label>台词语速估算（字/秒）<input v-model.number="production.settings.speechRate" type="number" min="1" max="10" step="0.5" /></label>
      <label>改编原则<select v-model="production.settings.fidelity"><option value="faithful">忠实拆解（台词引用原文）</option><option value="adapted">允许改编（保留核心因果）</option></select></label>
      <label>文本导出目标<select v-model="production.settings.exportTarget"><option value="seedance">即梦 / Seedance 制作提示词</option><option value="generic">通用中文视频提示词</option><option value="midjourney">英文图像提示词</option></select></label>
      <label class="full">风格补充<textarea v-model="production.settings.styleNotes" rows="2" placeholder="例如：低饱和蓝灰色、自然侧光、保留皮肤纹理；不要填未经确认的接口参数。" maxlength="3000"></textarea></label>
    </fieldset>
    <p class="settings-note">“15 秒 / 5 镜头”是一种制作预设，可按内容调整。文本导出不代表已调用视频或配音服务。</p>
    <section v-for="group in groups" :key="group.key" class="asset-group">
      <div class="settings-heading"><div><h3>{{ group.title }}</h3><p>{{ group.hint }}</p></div><button class="btn-secondary" :disabled="disabled" @click="add(group.key)">添加</button></div>
      <p v-if="!production.bible[group.key].length" class="settings-note">尚无设定。可手动添加，或由编剧拆解阶段提出建议。</p>
      <details v-for="row in production.bible[group.key]" :key="row.id" class="asset-item">
        <summary>{{ row.name }} <span>{{ row.locked ? '已锁定' : '可编辑' }}</span></summary>
        <div class="asset-tools"><button :disabled="disabled" @click="row.locked=!row.locked">{{ row.locked?'解锁编辑':'锁定设定' }}</button><button :disabled="disabled || row.locked" @click="remove(group.key,row)">删除</button></div>
        <fieldset :disabled="disabled || row.locked" class="asset-fields">
          <label>名称<input v-model="row.name" maxlength="120" /></label>
          <label>外观 / 空间 / 状态描述<textarea v-model="row.description" rows="3" maxlength="5000"></textarea></label>
          <label v-if="group.key==='characters'">固定声线描述<textarea v-model="row.voice" rows="2" maxlength="1200" placeholder="例如：清亮偏低、克制，情绪变化不改变核心声线；实际音色需后续服务绑定。"></textarea></label>
          <template v-if="group.key==='scenes'"><label>光影方案<input v-model="row.lighting" maxlength="1500" /></label><label>空间与轴线<input v-model="row.axis" maxlength="1500" placeholder="人物相对方位、视线与主镜头位置"></label></template>
          <label>参考素材<select v-model="row.referenceUrl"><option value="">不关联图片</option><option v-for="image in images" :key="image.id || image.url" :value="image.url">{{ image.title || '素材图片' }}</option></select></label>
        </fieldset>
        <MaterialImage v-if="row.referenceUrl" :url="row.referenceUrl" :title="row.name" />
        <p v-if="row.referenceUrl" class="settings-note">关联图片供制作参考和后续素材绑定，当前文本 Agent 不会自动识别图片。</p>
      </details>
    </section>
  </section>
</template>
<style scoped>
.production-settings{background:var(--panel-bg);border:1px solid var(--border-color);border-radius:8px;padding:24px}.settings-heading{display:flex;justify-content:space-between;align-items:center;gap:16px;margin-bottom:18px}h3{font-size:15px;margin:0 0 6px}p{margin:0;color:var(--text-secondary);font-size:12px;line-height:1.7}.settings-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}.settings-grid,.asset-fields{border:0;padding:0;margin:0}label{display:flex;flex-direction:column;gap:8px;font-size:12px;color:var(--text-secondary)}input,select,textarea{box-sizing:border-box;border:1px solid var(--border-color);border-radius:5px;padding:10px;background:var(--panel-bg);color:var(--text-primary);font:inherit;min-width:0;width:100%}.full{grid-column:1/-1}.settings-note{margin-top:13px}.asset-group{border-top:1px solid var(--border-color);margin-top:24px;padding-top:24px}.asset-item{border:1px solid var(--border-color);border-radius:6px;padding:14px;margin-top:10px}.asset-item summary{cursor:pointer;font-size:13px}.asset-item summary span{float:right;color:var(--text-secondary);font-size:11px}.asset-tools{display:flex;justify-content:flex-end;gap:12px;margin:14px 0}.asset-tools button{border:0;background:none;color:var(--accent-color);font-size:12px;cursor:pointer}.asset-fields{display:grid;gap:14px}.btn-secondary{border:1px solid var(--border-color);padding:8px 13px;border-radius:5px;background:var(--panel-bg);color:var(--text-primary);white-space:nowrap}button:disabled{opacity:.5;cursor:not-allowed}fieldset:disabled{opacity:.65}@media(max-width:850px){.settings-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:550px){.settings-grid{grid-template-columns:1fr}.production-settings{padding:16px}.settings-heading{align-items:flex-start}}
</style>
