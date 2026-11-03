"""Comic production uses temporary works and mock agents, never real models."""
import json
from pathlib import Path
import sqlite3
import tempfile
from contextlib import closing
import unittest
from unittest.mock import patch
from sqlalchemy import create_engine
import test_regressions as fixtures
import database
from agents import BaseAgent
from comic_schema import ComicPlan
import comic_service


class ComicAPITests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self): await fixtures.APITests.asyncSetUp(self)
    async def asyncTearDown(self): await fixtures.APITests.asyncTearDown(self)

    async def prepare(self):
        work=await fixtures.APITests.create(self, characters=[{'id':'a','name':'阿遥','description':'档案修复师'}], chapters=[{'id':'v','chapters':[
            {'id':'c','title':'渡口','content':'阿遥说：“别关灯。”\n\n陆川递来船票。'}]}])
        response=await self.client.get('/api/comic/prepare',params={'workId':work['id'],'chapterId':'c'})
        self.assertEqual(response.status_code,200)
        prepared=response.json()
        plan=ComicPlan(sourceHash=prepared['sourceHash'],settings=prepared['production']['settings'],baseProduction=prepared['production'],
                       bible=prepared['production']['bible'],passages=[p for block in prepared['blocks'] for p in block['passages']]).model_dump()
        return work,prepared,plan

    def model(self, system, message, config, **kwargs):
        context=json.loads(message)
        if '你负责剧本拆解' in system:
            ids=[p['id'] for p in context['block']['passages']]
            return {'characters':[{'name':'阿遥','voice':'清亮克制'},{'name':'陆川','voice':'沉稳低声'}],
                    'scenes':[{'name':'渡口','description':'船舷与石阶','axis':'阿遥左，陆川右','lighting':'船灯侧光'}],'props':[],
                    'beats':[{'summary':'两人在渡口交接船票','sourceIds':ids}],
                    'clips':[{'title':'末班渡船','scene':'渡口','characters':['阿遥','陆川'],'summary':'交接船票','sourceIds':ids}]}
        if '你负责当前 clip' in system:
            actor=context['clip']['characterIds'][0]
            return {'shots':[{'duration':3,'desc':'渡口两人交接船票','prompt':'harbor scene','sourceIds':context['clip']['sourceIds'],
                              'characterIds':[actor],'lines':[{'characterId':actor,'text':'别关灯。','emotion':'担忧'}] if i==0 else [],
                              'startState':'阿遥在左','endState':'陆川持船票'} for i in range(5)],'endingState':'陆川持船票，两人在船头'}
        return {'summary':'未发现明显的连续性问题，仍需人工核对','issues':[]}

    async def call(self,work,prepared,plan,stage,**ids):
        return await self.client.post('/api/comic/stage',json={'workId':work['id'],'chapterId':'c','sourceHash':prepared['sourceHash'],
            'stage':stage,'config':{'apiKey':'fixture'},'production':{'settings':plan['settings'],'bible':plan['bible']},'plan':plan,**ids})

    async def test_complete_pipeline_persists_production_without_losing_manuscript(self):
        work,prepared,plan=await self.prepare()
        with patch.object(BaseAgent,'call_llm',side_effect=self.model) as llm:
            response=await self.call(work,prepared,plan,'breakdown',blockId=prepared['blocks'][0]['id'])
            self.assertEqual(response.status_code,200,response.text)
            result=response.json();plan.update(bible=result['bible'],beats=result['beats'],clips=result['clips'])
            response=await self.call(work,prepared,plan,'direct',clipId=plan['clips'][0]['id'])
            self.assertEqual(response.status_code,200,response.text)
            plan.update(shots=response.json()['shots'],endingState=response.json()['endingState'])
            self.assertEqual(sum(shot['duration'] for shot in plan['shots']),15)
            response=await self.call(work,prepared,plan,'review',clipId=plan['clips'][0]['id'])
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(llm.call_count,3)
        plan.update(status='complete',issues=response.json()['issues'])
        work['comicProduction']={'schemaVersion':1,'settings':plan['settings'],'bible':plan['bible']}
        work['chapters'][0]['chapters'][0]['comicDraft']=plan
        saved=await self.client.put(f'/api/works/{work["id"]}',json=work)
        self.assertEqual(saved.status_code,200,saved.text)
        self.assertEqual(saved.json()['chapters'][0]['chapters'][0]['content'],work['chapters'][0]['chapters'][0]['content'])
        self.assertEqual(len(saved.json()['chapters'][0]['chapters'][0]['comicDraft']['shots']),5)
        restored=(await self.client.get(f'/api/works/{work["id"]}')).json()
        self.assertEqual(restored['comicProduction'],work['comicProduction'])

    async def test_stale_source_and_wrong_work_never_call_model(self):
        work,prepared,plan=await self.prepare()
        work['chapters'][0]['chapters'][0]['content']='edited manuscript'
        await self.client.put(f'/api/works/{work["id"]}',json=work)
        with patch.object(BaseAgent,'call_llm') as model:
            self.assertEqual((await self.call(work,prepared,plan,'breakdown',blockId='B001')).status_code,409)
            other=await fixtures.APITests.create(self,chapters=[])
            self.assertEqual((await self.call(other,prepared,plan,'breakdown',blockId='B001')).status_code,404)
            model.assert_not_called()

    async def test_invalid_reference_or_duration_never_returns_success(self):
        work,prepared,plan=await self.prepare()
        with patch.object(BaseAgent,'call_llm',side_effect=self.model):
            result=(await self.call(work,prepared,plan,'breakdown',blockId='B001')).json()
        plan.update(bible=result['bible'],clips=result['clips'],beats=result['beats'])
        for change in ({'duration':10},{'sourceIds':['unknown']},{'characterIds':['unknown']}):
            context={'clip':plan['clips'][0]}
            fake=self.model('你负责当前 clip',json.dumps(context),{})
            fake['shots'][0].update(change)
            with patch.object(BaseAgent,'call_llm',return_value=fake):
                response=await self.call(work,prepared,plan,'direct',clipId=plan['clips'][0]['id'])
            self.assertEqual(response.status_code,502)

    async def test_comic_progress_does_not_evict_manuscript_revisions(self):
        work,prepared,plan=await self.prepare()
        work['chapters'][0]['chapters'][0]['content']='a real manuscript edit'
        await self.client.put(f'/api/works/{work["id"]}',json=work)
        work['comicProduction']=prepared['production']
        for i in range(25):
            work['comicProduction']['settings']['styleNotes']=f'lighting note {i}'
            response=await self.client.put(f'/api/works/{work["id"]}',json=work)
            self.assertEqual(response.status_code,200)
        revisions=(await self.client.get(f'/api/works/{work["id"]}/revisions')).json()
        self.assertEqual(len(revisions),1)

    async def test_unfinished_or_stale_continuity_is_not_retrieved(self):
        work,prepared,plan=await self.prepare()
        chapter=work['chapters'][0]['chapters'][0]
        plan.update(status='interrupted',endingState='PRIVATE_STALE_CONTINUITY')
        chapter['comicDraft']=plan
        await self.client.put(f'/api/works/{work["id"]}',json=work)
        self.assertFalse(fixtures.main.retrieval_system.for_work(work['id']).search('PRIVATE_STALE_CONTINUITY'))
        plan['status']='complete'
        await self.client.put(f'/api/works/{work["id"]}',json=work)
        self.assertTrue(fixtures.main.retrieval_system.for_work(work['id']).search('PRIVATE_STALE_CONTINUITY'))
        chapter['content']='changed source'
        await self.client.put(f'/api/works/{work["id"]}',json=work)
        self.assertFalse(fixtures.main.retrieval_system.for_work(work['id']).search('PRIVATE_STALE_CONTINUITY'))


class ComicUnitTests(unittest.TestCase):
    def test_locked_voice_and_scene_do_not_change(self):
        bible={'characters':[{'id':'a','name':'阿遥','voice':'original','description':'same','locked':True}], 'scenes':[],'props':[]}
        merged=comic_service.merge_bible(bible,{'characters':[{'name':'阿遥','voice':'different'}]})
        self.assertEqual(merged['characters'][0]['voice'],'original')

    def test_long_source_is_partitioned_without_silent_loss(self):
        text='甲'*2000+'\n\n'+'乙'*2300
        blocks=comic_service.source_blocks(text)
        self.assertEqual(''.join(p['text'] for block in blocks for p in block['passages']),'甲'*2000+'乙'*2300)
        self.assertEqual(len({p['id'] for block in blocks for p in block['passages']}),6)

    def test_schema_upgrade_preserves_existing_rows_and_keeps_backup(self):
        with tempfile.TemporaryDirectory(prefix='comic-migration-') as directory:
            data=Path(directory)
            with closing(sqlite3.connect(data/'ai_novel.db')) as conn:
                conn.execute('CREATE TABLE works (id INTEGER PRIMARY KEY, title TEXT)')
                conn.execute("INSERT INTO works VALUES (1, 'important work')")
                conn.commit()
            engine=create_engine('sqlite:///'+(data/'ai_novel.db').as_posix())
            try:
                with patch.object(database,'engine',engine),patch.object(database,'DATA_DIR',data):
                    database.upgrade_schema();database.upgrade_schema()
                with closing(sqlite3.connect(data/'ai_novel.db')) as conn:
                    self.assertEqual(conn.execute('SELECT title,comicProduction FROM works').fetchone(),('important work','{}'))
                self.assertEqual(len(list((data/'backups').glob('*.db'))),1)
            finally: engine.dispose()
