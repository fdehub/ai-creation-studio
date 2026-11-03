// A task belongs to the work object that started it, even if the user switches
// away and back before a provider that ignores AbortSignal finishes responding.
export function createWorkTasks(store, activeWorkData) {
  const running = new Set()
  let disposed = false
  const cancelAll = () => { for (const controller of running) controller.abort(); running.clear() }
  return {
    cancelAll,
    dispose() { disposed = true; cancelAll() },
    begin() {
      const work = activeWorkData.value
      const controller = new AbortController()
      running.add(controller)
      return {
        work, signal: controller.signal,
        get cancelled() { return controller.signal.aborted || disposed },
        assertCurrent() {
          if (!work?.id) throw new Error('请先创建或选择作品')
          if (disposed || controller.signal.aborted || store.activeWorkId !== work.id || !store.works.includes(work)) {
            controller.abort()
            throw new Error('作品或页面已切换，本次结果未写入')
          }
        },
        finish() { running.delete(controller) }
      }
    }
  }
}
