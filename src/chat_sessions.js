// Conversation content is stored locally, separately from provider credentials.
let connection
async function database() {
  if (!globalThis.indexedDB) return null
  if (!connection) connection = new Promise((resolve, reject) => {
    const request = indexedDB.open('novel-chat-sessions', 1)
    request.onupgradeneeded = () => request.result.createObjectStore('sessions', { keyPath: 'id' }).createIndex('workId', 'workId')
    request.onsuccess = () => { request.result.onversionchange = () => { request.result.close(); connection = null }; resolve(request.result) }
    request.onerror = () => { connection = null; reject(request.error) }
  })
  return connection
}
const prefix = 'novel-chat-session-'
export async function listChatSessions(workId) {
  const db = await database()
  let records
  if (db) records = await new Promise((resolve, reject) => {
    const req = db.transaction('sessions').objectStore('sessions').index('workId').getAll(String(workId))
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
  else {
    records = []
    for (let i = 0; i < (globalThis.localStorage?.length || 0); i++) {
      const key = localStorage.key(i)
      if (!key?.startsWith(prefix)) continue
      const item = JSON.parse(localStorage.getItem(key))
      if (item?.workId === String(workId)) records.push(item)
    }
  }
  return records.sort((a, b) => b.updatedAt - a.updatedAt)
}
export async function saveChatSession(session) {
  const copy = JSON.parse(JSON.stringify({ ...session, workId: String(session.workId) }))
  const db = await database()
  if (!db) {
    if (!globalThis.localStorage) throw new Error('此浏览器无法保存本地对话')
    localStorage.setItem(prefix + copy.id, JSON.stringify(copy))
    return
  }
  await new Promise((resolve, reject) => {
    const tx = db.transaction('sessions', 'readwrite')
    tx.objectStore('sessions').put(copy)
    tx.oncomplete = resolve
    tx.onerror = () => reject(tx.error)
    tx.onabort = () => reject(tx.error || new Error('本地对话保存被中断'))
  })
}
