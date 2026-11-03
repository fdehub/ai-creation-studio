"""Isolated regression tests. Never use the project's existing databases or keys."""
import asyncio
import base64
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

TEMP = tempfile.TemporaryDirectory(prefix="novel-regression-")
os.environ["NOVEL_DATA_DIR"] = TEMP.name
os.environ["NOVEL_ACCESS_TOKEN"] = "regression-only-access-token"
os.environ["NOVEL_PROVIDER_HOSTS"] = "api.openai.com"
os.environ["NOVEL_LOCAL_PROVIDER_HOSTS"] = ""
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
import main
import security
from agents import EditorAgent, LoreAgent, PlotAgent
from database import SessionLocal
from models import Work, WorkRevision

AUTH = {"Authorization": "Bearer regression-only-access-token"}


class APITests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        with SessionLocal() as db:
            db.query(WorkRevision).delete()
            db.query(Work).delete()
            db.commit()
        main.retrieval_system.conn.execute("DELETE FROM work_memory")
        main.retrieval_system.conn.commit()
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app, client=("127.0.0.1", 1234)), base_url="http://localhost:8100", headers=AUTH)

    async def asyncTearDown(self):
        await self.client.aclose()

    async def create(self, **fields):
        response = await self.client.post("/api/works", json={"title": "regression", **fields})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    async def test_auth_cors_host_and_bootstrap(self):
        self.assertEqual((await self.client.get("/api/works", headers={"Authorization": ""})).status_code, 401)
        self.assertEqual((await self.client.get("/api/works", headers={"Origin": "https://evil.invalid"})).status_code, 403)
        self.assertEqual((await self.client.get("/api/works", headers={"Host": "evil.invalid"})).status_code, 400)
        self.assertEqual((await self.client.post("/api/session", headers={"Origin": "http://localhost:5273"})).status_code, 401)
        with patch.object(security, "EXPLICIT_TOKEN", ""):
            self.assertEqual((await self.client.post("/api/session", headers={"Origin": "http://localhost:5273"})).json()["token"], security.ACCESS_TOKEN)
            self.assertEqual((await self.client.post("/api/session", headers={"Origin": "https://evil.invalid"})).status_code, 401)
            self.assertEqual((await self.client.post("/api/session")).status_code, 401)
        preflight = await self.client.options("/api/works", headers={"Origin": "https://evil.invalid", "Access-Control-Request-Method": "GET"})
        self.assertNotIn("access-control-allow-origin", preflight.headers)

    async def test_crud_revisions_restore_and_index_deletion(self):
        original = [{"id": "v", "chapters": [{"id": "c", "content": "original manuscript", "summary": "unique_old_keyword"}]}]
        work = await self.create(chapters=original, characters=[{"id": 1, "name": "unique_character"}])
        work_id = work["id"]
        changed = {**work, "chapters": [{"id": "v", "chapters": [{"id": "c", "content": "new manuscript"}]}], "characters": []}
        self.assertEqual((await self.client.put(f"/api/works/{work_id}", json=changed)).status_code, 200)
        self.assertFalse((await self.client.get("/api/search", params={"work_id": work_id, "query": "unique_character"})).json()["results"])
        revisions = (await self.client.get(f"/api/works/{work_id}/revisions")).json()
        restored = await self.client.post(f"/api/works/{work_id}/revisions/{revisions[0]['id']}/restore")
        self.assertEqual(restored.json()["chapters"], original)
        self.assertEqual((await self.client.delete(f"/api/works/{work_id}")).status_code, 200)
        self.assertEqual((await self.client.get(f"/api/works/{work_id}")).status_code, 404)
        self.assertFalse(main.retrieval_system.search("unique_old_keyword", work_id=work_id))

    async def test_memory_does_not_cross_works(self):
        a = await self.create(characters=[{"name": "same_name", "description": "only_alpha"}])
        b = await self.create(characters=[{"name": "same_name", "description": "only_beta"}])
        self.assertTrue(main.retrieval_system.for_work(a["id"]).search("only_alpha"))
        self.assertFalse(main.retrieval_system.for_work(b["id"]).search("only_alpha"))
        self.assertTrue(main.retrieval_system.for_work(b["id"]).search("only_beta"))

    async def test_malformed_work_never_commits_or_replaces_manuscript(self):
        original = [{"chapters":[{"id":"one","content":"important manuscript"}]}]
        work = await self.create(chapters=original)
        malformed = [
            {"chapters":[{"chapters":[None]}]},
            {"chapters":[{"chapters":[{"content":{"bad":"object"}}]}]},
            {"chapters":[{"chapters":[{"id":"duplicate"},{"id":"duplicate"}]}]},
            {"worldview":[{"items":["bad"]}]},
            {"characters":[{"tags":"not-an-array"}]},
        ]
        for fields in malformed:
            with self.subTest(fields=fields):
                self.assertEqual((await self.client.post('/api/works', json={"title":"bad", **fields})).status_code,422)
                self.assertEqual((await self.client.put(f'/api/works/{work["id"]}', json={**work, **fields})).status_code,422)
                self.assertEqual((await self.client.get(f'/api/works/{work["id"]}')).json()['chapters'],original)
                if 'chapters' in fields:
                    self.assertEqual((await self.client.post('/api/agents/resume_industrial_outline', json={"title":"bad", **fields})).status_code,422)
        self.assertEqual(len((await self.client.get('/api/works')).json()),1)

    async def test_chinese_substring_search_is_scoped_to_work(self):
        a = await self.create(characters=[{"name":"主角", "description":"他在玄天宗的后山修炼"}])
        b = await self.create(characters=[{"name":"主角", "description":"他在都市生活"}])
        self.assertTrue(main.retrieval_system.for_work(a['id']).search('玄天宗'))
        self.assertFalse(main.retrieval_system.for_work(b['id']).search('玄天宗'))

    async def test_upload_survives_new_request_and_requires_auth(self):
        png = b"\x89PNG\r\n\x1a\n" + b"regression-image"
        response = await self.client.post("/api/uploads", json={"data": "data:image/png;base64," + base64.b64encode(png).decode()})
        self.assertEqual(response.status_code, 200)
        url = response.json()["url"]
        self.assertEqual((await self.client.get(url)).content, png)
        self.assertEqual((await self.client.get(url, headers={"Authorization": ""})).status_code, 401)
        self.assertEqual((await self.client.post("/api/uploads", json={"data": "data:image/png;base64,PHNjcmlwdD4="})).status_code, 400)

    async def test_proxy_preserves_error_and_filters_headers(self):
        seen = []
        def upstream(request):
            seen.append(request)
            return httpx.Response(401, json={"error": "invalid"})
        provider = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
        with patch.object(main, "provider_target", return_value=(httpx.URL("https://93.184.216.34/v1/chat/completions"), "api.openai.com", "api.openai.com")), patch.object(main.httpx, "AsyncClient", return_value=provider):
            response = await self.client.post("/api/proxy/chat", json={"url": "https://api.openai.com/v1/chat/completions", "headers": {"Cookie": "private", "Host": "evil.invalid", "Authorization": "Bearer placeholder"}, "body": {}})
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("cookie", seen[0].headers)
        self.assertEqual(seen[0].headers["host"], "api.openai.com")
        self.assertEqual(seen[0].extensions["sni_hostname"], "api.openai.com")
        self.assertTrue(provider.is_closed)
        self.assertEqual(sum(r.path == "/api/proxy/chat" for r in main.app.routes), 1)

    async def test_proxy_stream_and_network_failure(self):
        provider = httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, content=b'data: [DONE]\n\n', headers={"content-type": "text/event-stream"})))
        target = (httpx.URL("https://93.184.216.34/v1/chat/completions"), "api.openai.com", "api.openai.com")
        with patch.object(main, "provider_target", return_value=target), patch.object(main.httpx, "AsyncClient", return_value=provider):
            response = await self.client.post("/api/proxy/chat", json={"url": "https://api.openai.com/v1/chat/completions"})
        self.assertEqual(response.content, b'data: [DONE]\n\n')
        self.assertTrue(provider.is_closed)
        def fail(req):
            raise httpx.ConnectError("regression failure")
        provider = httpx.AsyncClient(transport=httpx.MockTransport(fail))
        with patch.object(main, "provider_target", return_value=target), patch.object(main.httpx, "AsyncClient", return_value=provider):
            response = await self.client.post("/api/proxy/chat", json={"url": "https://api.openai.com/v1/chat/completions"})
        self.assertEqual(response.status_code, 502)
        self.assertTrue(provider.is_closed)

    async def test_resume_counts_leaf_chapters_and_standard_sse(self):
        chapters = [{"id": "v", "chapters": [{"id": str(i), "summary": f"summary-{i}"} for i in range(20)]}]
        work = await self.create(chapters=chapters)
        captured = {}
        def outline(self, *args, **kwargs):
            captured.update(kwargs)
            yield {"step": "mock", "chapters": []}
        with patch.object(EditorAgent, "generate_long_outline", outline):
            response = await self.client.post("/api/agents/resume_industrial_outline", json={"workId": work["id"], "title": "test", "chapters": chapters})
        self.assertEqual(captured["start_chapter"], 20)
        self.assertEqual(captured["last_summary"], "summary-19")
        self.assertIn('"status": "done"', response.text)
        self.assertIn("\n\n", response.text)
        self.assertNotIn("\\n\\n", response.text)

    async def test_model_call_does_not_block_other_requests(self):
        started, release = threading.Event(), threading.Event()
        def slow(*args):
            started.set()
            release.wait(3)
            return "mock"
        with patch.object(EditorAgent, "generate_response", slow):
            task = asyncio.create_task(self.client.post("/api/agents/chat", json={"prompt": "test"}))
            for _ in range(100):
                if started.is_set(): break
                await asyncio.sleep(.01)
            self.assertTrue(started.is_set())
            try:
                healthy = await asyncio.wait_for(self.client.get("/api/health"), timeout=1)
                self.assertEqual(healthy.status_code, 200)
                self.assertFalse(task.done())
            finally:
                release.set()
            self.assertEqual((await task).status_code, 200)


class UnitTests(unittest.TestCase):
    def test_invalid_structured_model_results_fail_before_indexing(self):
        memory = main.retrieval_system.for_work('invalid-model-fixture')
        cases = [(LoreAgent(memory), 'generate_lore', ('title','','',{}), None),
                 (PlotAgent(memory), 'generate_plot', ('title','',{},{}), []),
                 (EditorAgent(memory), 'generate_outline', ('title',[],[],{}), {'chapters':[{'chapters':[None]}]}),
                 (LoreAgent(memory), 'expand_lore', ('title',{},{}), {'items':[None]}),
                 (PlotAgent(memory), 'expand_character', ('title',{},{}), {'expanded_desc':None}),
                 (EditorAgent(memory), 'expand_outline', ('title',{},{}), {'chapters':[None]})]
        for agent, method, args, result in cases:
            with self.subTest(method=method), patch.object(agent, 'call_llm', return_value=result):
                with self.assertRaises(ValueError): getattr(agent,method)(*args)

    def test_provider_validation_and_ip_pinning(self):
        for url in ["http://127.0.0.1:80/v1/chat/completions", "https://evil.invalid/v1/chat/completions", "https://api.openai.com:444/v1/chat/completions", "https://user:password@api.openai.com/v1/chat/completions"]:
            with self.assertRaises(main.HTTPException): security.provider_target(url)
        with patch.object(security.socket, "getaddrinfo", return_value=[(2, 1, 6, "", ("127.0.0.1", 443))]):
            with self.assertRaises(main.HTTPException): security.provider_target("https://api.openai.com/v1/chat/completions")
        with patch.object(security.socket, "getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 443))]):
            target, host, sni = security.provider_target("https://api.openai.com/v1/chat/completions")
            self.assertEqual(target.host, "93.184.216.34")
            self.assertEqual(host, "api.openai.com")
            self.assertEqual(sni, "api.openai.com")

    def test_outline_unique_ids_resume_context_and_failed_batch(self):
        agent = EditorAgent(main.retrieval_system.for_work("unit"))
        with patch.object(agent, "call_llm", return_value=[{"title": "next", "summary": "valid"}]) as model:
            updates = list(agent.generate_long_outline("test", "", [], [], {}, target_chapters=21, start_chapter=20, batch_size=1, last_summary="prior"))
            chapter = updates[-1]["chapters"][0]["chapters"][0]
            self.assertEqual(chapter["chapterNum"], 21)
            self.assertNotEqual(chapter["id"], "chap-1")
            self.assertIn("prior", model.call_args.args[0])
        with patch.object(agent, "call_llm", return_value=[]):
            with self.assertRaises(ValueError): list(agent.generate_long_outline("test", "", [], [], {}, target_chapters=1))


def tearDownModule():
    main.retrieval_system.close()
    main.engine.dispose()
    TEMP.cleanup()


if __name__ == "__main__":
    unittest.main()
