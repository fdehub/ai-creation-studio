// Account login makes Muse selectable; assigning an Agent remains a user choice.
export function syncMuseConfigs(store, accounts) {
  let added = 0
  for (const account of accounts) {
    if (account.provider !== 'muse' || account.status !== 'connected' || !account.canGenerate) continue
    if (store.llmConfigs.some(config => config.authType === 'account' && config.accountId === account.id && config.modelName === 'muse')) continue
    store.llmConfigs.push({
      id: 'account-' + crypto.randomUUID(), name: `${account.label} · Muse 网页当前模型`,
      authType: 'account', accountId: account.id, provider: 'muse',
      apiKey: '', baseUrl: '', modelName: 'muse'
    })
    added++
  }
  return added
}
