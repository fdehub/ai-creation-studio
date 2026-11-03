export function writingContext(work, chapterId, mode = 'chapter') {
  const chapters = (work.chapters || []).flatMap(v => v.chapters || [])
  const index = chapters.findIndex(c => c.id === chapterId)
  const chapter = chapters[mode === 'previous' ? index - 1 : index]
  let text = '', label = '不引用作品正文'
  if (mode === 'chapter' || mode === 'previous') {
    if (!chapter || !(chapter.content || '').trim()) return { available: false, text: '', label: mode === 'previous' ? '上一章不存在或尚无正文' : '所选章节尚无正文', length: 0 }
    text = `章节：${chapter.title}\n${chapter.content}`
    label = `${mode === 'previous' ? '上一章' : '章节'} · ${chapter.title}`
  } else if (mode === 'world') {
    const settings = (work.worldview || []).flatMap(category => (category.items || []).map(item => `${category.title || category.name || '设定'} / ${item.name || ''}：${item.desc || item.description || ''}`))
    const people = (work.characters || []).map(c => `${c.name}：${c.description || ''}`)
    text = [...settings, ...people].join('\n\n')
    label = '人物与世界观'
    if (!text.trim()) return { available: false, text: '', label: '此作品还没有人物或世界观设定', length: 0 }
  }
  const originalLength = text.length
  text = text.slice(0, 24000)
  return { available: true, text, label, length: text.length, truncated: text.length < originalLength }
}
