let sequence = 0
const states = new WeakMap()
export const dialog = {
  mounted(el) {
    const previous = document.activeElement
    const heading = el.querySelector('h2,h3,h4')
    el.setAttribute('role', 'dialog'); el.setAttribute('aria-modal', 'true')
    if (heading) { if (!heading.id) heading.id = `dialog-title-${++sequence}`; el.setAttribute('aria-labelledby', heading.id) }
    else if (!el.hasAttribute('aria-label')) el.setAttribute('aria-label', '编辑窗口')
    const focusable = () => [...el.querySelectorAll('button:not([disabled]),a[href],input:not([disabled]),textarea:not([disabled]),select:not([disabled]),[tabindex="0"]')].filter(n => n.getClientRects().length)
    const onKey = event => {
      if ([...document.querySelectorAll('[role="dialog"][aria-modal="true"]')].at(-1) !== el) return
      if (event.key === 'Escape') {
        const cancel = [...el.querySelectorAll('button')].find(b => /^(取消|关闭)$/.test(b.textContent.trim()) || b.getAttribute('aria-label') === '关闭')
        if (cancel) { event.preventDefault(); event.stopPropagation(); cancel.click() }
        else el.closest('.modal-overlay,.spotlight-overlay')?.click()
      } else if (event.key === 'Tab') {
        const items = focusable(), first = items[0], last = items.at(-1)
        if (!first) { event.preventDefault(); return }
        if (event.shiftKey && (document.activeElement === first || !el.contains(document.activeElement))) { event.preventDefault(); last.focus() }
        if (!event.shiftKey && (document.activeElement === last || !el.contains(document.activeElement))) { event.preventDefault(); first.focus() }
      }
    }
    states.set(el, { previous, onKey }); el.addEventListener('keydown', onKey)
    queueMicrotask(() => { if (el.isConnected) { const target = el.querySelector('[autofocus]') || focusable()[0]; if (target) target.focus(); else { el.tabIndex = -1; el.focus() } } })
  },
  unmounted(el) { const state = states.get(el); if (state) { el.removeEventListener('keydown', state.onKey); if (state.previous?.isConnected) state.previous.focus(); states.delete(el) } }
}
