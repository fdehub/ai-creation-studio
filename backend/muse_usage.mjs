// Read only the usage meters in Muse's settings cards, never conversation text.
export function normalizeUsageRows(rows) {
  const result = []
  for (const row of rows || []) {
    const label = String(row.label || '').trim().slice(0, 100)
    const description = String(row.description || '').trim().slice(0, 240)
    const valueLabel = String(row.valueLabel || '').trim().slice(0, 240)
    const percent = row.usedPercent
    if (!label || !valueLabel || typeof percent !== 'number' || !Number.isFinite(percent) || percent < 0 || percent > 100) continue
    const kind = /weekly|每周|周限额/i.test(description) ? 'weekly' : /additional|extra|额外/i.test(label) ? 'additional' : 'other'
    result.push({ kind, label, description, valueLabel, usedPercent: percent })
    if (result.length === 6) break
  }
  return result
}

export async function readMuseUsage(page) {
  await page.getByRole('button', { name: /^(Settings|设置)$/ }).first().click({ timeout: 45000 })
  await page.waitForFunction(() => !!document.querySelector('[data-slot="settings-card-item"] [role="progressbar"]') || [...document.querySelectorAll('[role="menuitem"]')].some(el => /^(Settings|设置)/.test(el.textContent.trim())), null, { timeout:10000 })
  // The gear opens a menu first; only its Settings item is an allowed action.
  const settingsItem = page.getByRole('menuitem', { name: /^(Settings|设置)(?:\s|Ctrl|⌘|$)/ }).first()
  if (await settingsItem.isVisible()) await settingsItem.click()
  const meters = page.locator('[data-slot="settings-card-item"] [role="progressbar"]')
  await meters.first().waitFor({ state: 'visible', timeout: 25000 })
  const rows = normalizeUsageRows(await meters.evaluateAll(elements => elements.filter(el => el.getClientRects().length).map(bar => {
    const texts = [...bar.parentElement.querySelectorAll('[data-slot="text"]')].map(el => (el.innerText || el.textContent || '').trim())
    const value = bar.getAttribute('aria-valuenow')
    return { label: bar.getAttribute('aria-label'), description: texts[1], valueLabel: texts.at(-1), usedPercent: value === null || value.trim() === '' ? null : Number(value) }
  })))
  if (!rows.length) throw new Error('Muse 设置页未返回可读取的用量，请稍后刷新或检查页面是否变化')
  return { source: 'muse-settings', rows }
}
