import test from 'node:test'
import assert from 'node:assert/strict'
import { syncMuseConfigs } from '../src/account_models.js'

const connected = {id:'muse-fixture',provider:'muse',status:'connected',canGenerate:true,label:'Muse fixture',secret:'never-copy-this'}
test('connected Muse becomes selectable without changing Agent assignments or copying account secrets',()=>{
  const store={llmConfigs:[{id:'default',name:'Default'}],agentAssignments:{EditorAgent:'default',PlotAgent:'custom',LoreAgent:'default'}}
  const assignments={...store.agentAssignments}
  assert.equal(syncMuseConfigs(store,[connected]),1)
  assert.deepEqual(store.agentAssignments,assignments)
  const config=store.llmConfigs[1]
  assert.equal(config.modelName,'muse');assert.equal(config.accountId,connected.id)
  assert.equal(config.apiKey,'');assert.equal(config.secret,undefined)
  const id=config.id
  assert.equal(syncMuseConfigs(store,[connected]),0)
  assert.equal(store.llmConfigs[1].id,id)
})

test('pending, disconnected, unauthorized and other providers are not registered as Muse models',()=>{
  const store={llmConfigs:[]}
  const accounts=[{...connected,status:'pending'},{...connected,status:'disconnected'}, {...connected,canGenerate:false},{...connected,provider:'chatgpt'}]
  assert.equal(syncMuseConfigs(store,accounts),0)
  assert.deepEqual(store.llmConfigs,[])
})
