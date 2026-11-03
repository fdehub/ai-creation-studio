export function parseModelJSON(content, kind = 'object') {
  if (typeof content !== 'string') throw new Error('模型未返回有效文本')
  let text = content.trim()
  const fenced = text.match(/```(?:json)?\s*([\s\S]*?)\s*```/i)
  if (fenced) text = fenced[1]
  let value
  try { value = JSON.parse(text) } catch { throw new Error('模型返回的 JSON 格式无效') }
  const object = item => item !== null && typeof item === 'object' && !Array.isArray(item)
  if (kind === 'array' ? !Array.isArray(value) || value.some(item => !object(item)) : !object(value)) throw new Error('模型返回的数据结构无效')
  const validate = (items, depth = 0) => {
    if (depth > 12 || !Array.isArray(items) || items.some(item=>!object(item))) throw new Error('模型返回的数据层级或结构无效')
    for (const item of items) {
    for (const key of ['name','title','desc','description','summary','content','faction','type','dialogue','prompt']) if (key in item && typeof item[key] !== 'string') throw new Error(`模型字段 ${key} 应为文本`)
    if ('tags' in item && (!Array.isArray(item.tags) || item.tags.some(tag=>typeof tag!=='string'))) throw new Error('模型标签格式无效')
    if ('chapterRange' in item && (!Array.isArray(item.chapterRange) || item.chapterRange.length!==2 || item.chapterRange.some(n=>!Number.isFinite(n)))) throw new Error('模型角色章节范围无效')
    for (const key of ['states','items','children','chapters']) if (key in item) validate(item[key], depth+1)
    }
  }
  validate(kind === 'array' ? value : [value])
  return value
}

export function parseComicShots(content) {
  const shots = parseModelJSON(content, 'array')
  if (!shots.length || shots.length > 500 || shots.some(shot => typeof shot.desc !== 'string' || !shot.desc.trim() || typeof shot.prompt !== 'string' || !shot.prompt.trim() || ('dialogue' in shot && typeof shot.dialogue !== 'string'))) throw new Error('模型分镜缺少有效画面或绘画提示词，原分镜已保留')
  return shots
}
