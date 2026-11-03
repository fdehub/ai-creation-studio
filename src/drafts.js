let database
const fallback = new Map()
function db() {
  if (!globalThis.indexedDB) return Promise.resolve(null)
  if (!database) database = new Promise((resolve, reject) => {
    const req = indexedDB.open('novel-unsaved-drafts', 1)
    req.onupgradeneeded = () => req.result.createObjectStore('drafts', { keyPath: 'id' })
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
  return database
}
export async function saveDraft(id, revision, snapshot) {
  const connection = await db()
  if (!connection) {
    // Also supports isolated Node tests; browsers without IDB use localStorage.
    globalThis.localStorage?.setItem(`novel-draft-${id}`, JSON.stringify({ id, revision, snapshot }))
    fallback.set(id, { id, revision, snapshot })
    return
  }
  await new Promise((resolve, reject) => {
    const tx = connection.transaction('drafts', 'readwrite')
    tx.objectStore('drafts').put({ id, revision, snapshot })
    tx.oncomplete = resolve
    tx.onerror = () => reject(tx.error)
    tx.onabort = () => reject(tx.error || new Error('本地草稿写入被中止'))
  })
}
export async function removeDraft(id, revision) {
  const connection = await db()
  if (!connection) {
    const item = fallback.get(id) || JSON.parse(globalThis.localStorage?.getItem(`novel-draft-${id}`) || 'null')
    if (!revision || item?.revision === revision) {
      fallback.delete(id)
      globalThis.localStorage?.removeItem(`novel-draft-${id}`)
    }
    return
  }
  await new Promise((resolve, reject) => {
    const tx = connection.transaction('drafts', 'readwrite')
    const items = tx.objectStore('drafts')
    const req = items.get(id)
    req.onsuccess = () => { if (!revision || req.result?.revision === revision) items.delete(id) }
    tx.oncomplete = resolve
    tx.onerror = () => reject(tx.error)
  })
}
export async function loadDrafts() {
  const connection = await db()
  if (!connection) {
    for (let i = 0; i < (globalThis.localStorage?.length || 0); i++) {
      const key = localStorage.key(i)
      if (key?.startsWith('novel-draft-')) {
        const value = JSON.parse(localStorage.getItem(key))
        fallback.set(value.id, value)
      }
    }
    return [...fallback.values()]
  }
  return new Promise((resolve, reject) => {
    const req = connection.transaction('drafts').objectStore('drafts').getAll()
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}
