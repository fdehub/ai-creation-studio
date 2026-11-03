// Decode complete SSE frames, independent of TCP chunks and UTF-8 boundaries.
export async function* readSSE(response) {
  if (!response.body) throw new Error('服务器未返回数据流')
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let data = []
  const parse = () => {
    const text = data.join('\n')
    data = []
    if (!text) return undefined
    if (text === '[DONE]') return { status: 'done' }
    const event = JSON.parse(text)
    if (event.error) throw new Error(typeof event.error === 'string' ? event.error : event.error.message || '模型生成失败')
    return event
  }
  try {
    while (true) {
      const { done, value } = await reader.read()
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true })
      // SSE CRLF and CR are normalized only after a full line is available.
      let match
      const newline = done ? /\r\n|\n|\r/ : /\r\n|\n|\r(?!$)/
      while ((match = newline.exec(buffer))) {
        const line = buffer.slice(0, match.index)
        buffer = buffer.slice(match.index + match[0].length)
        if (!line) {
          const event = parse()
          if (event !== undefined) yield event
        } else if (line.startsWith('data:')) {
          data.push(line.slice(5).replace(/^ /, ''))
        }
      }
      if (done) {
        if (buffer.trim() || data.length) throw new Error('数据流未完整结束，请从已完成位置继续')
        break
      }
    }
  } finally {
    await reader.cancel().catch(() => {})
    reader.releaseLock()
  }
}

export async function consumeOutline(response, onEvent) {
  let completed = false
  for await (const event of readSSE(response)) {
    await onEvent(event)
    if (event.status === 'done') completed = true
  }
  if (!completed) throw new Error('生成流意外中断，已完成的内容已保留')
}
