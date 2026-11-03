"""Authenticated single-user API with durable works and scoped generation."""
import asyncio
import anyio
from contextlib import asynccontextmanager
import base64
import binascii
import json
import logging
from typing import Literal
from datetime import datetime, timezone
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session
from starlette.middleware.trustedhost import TrustedHostMiddleware

from agents import EditorAgent, LoreAgent, PlotAgent
from account_routes import router as accounts_router, callback_router
from account_providers import complete_account_chat, chat_result, chat_stream
from muse_accounts import stop_workers
from database import Base, SessionLocal, engine, get_db, upgrade_schema
from models import Work, WorkRevision
from retrieval import RetrievalSystem
from security import authenticate, local_session, provider_target, provider_headers
from settings import ALLOWED_HOSTS, ALLOWED_ORIGINS, UPLOAD_DIR
from work_validation import validate_work_data
import comic_service

upgrade_schema()
Base.metadata.create_all(bind=engine)
retrieval_system = RetrievalSystem()
@asynccontextmanager
async def lifespan(app):
    yield
    await asyncio.to_thread(stop_workers)


app = FastAPI(title="AI Creation Studio — Single-user API", version="0.3.0", lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS,
                   allow_credentials=False, allow_methods=["GET", "POST", "PUT", "DELETE"],
                   allow_headers=["Authorization", "Content-Type"], expose_headers=["X-Novel-Session-Expired"])
api = APIRouter(prefix="/api", dependencies=[Depends(authenticate)])
log = logging.getLogger(__name__)


class ConfigModel(BaseModel):
    apiKey: str = ""
    baseUrl: str = ""
    modelName: str = ""
    authType: str = "apiKey"
    accountId: str | None = None


class AgentRequest(BaseModel):
    config: ConfigModel | None = None
    configs: dict[str, ConfigModel] = Field(default_factory=dict)
    workId: int | None = Field(default=None, gt=0)

    def cfg(self, role):
        value = self.configs.get(role) or self.config
        return value.model_dump() if value else {}


class ChatRequest(AgentRequest):
    prompt: str
    context: str = ""


class NovelGenerationRequest(AgentRequest):
    title: str
    tags: str = ""
    synopsis: str = ""
    targetChapters: int = Field(default=100, ge=1, le=2000)
    batchSize: int = Field(default=10, ge=1, le=20)
    prompt: str | None = None


class ResumeGenerationRequest(NovelGenerationRequest):
    characters: list[dict] = Field(default_factory=list)
    plotNodes: list[dict] = Field(default_factory=list)
    chapters: list[dict] = Field(default_factory=list)

    @model_validator(mode='after')
    def validate_nested(self):
        validate_work_data(self.model_dump())
        return self


class ExpandLoreRequest(AgentRequest):
    title: str
    parent_item: dict


class ExpandCharacterRequest(AgentRequest):
    title: str
    character: dict


class ExpandOutlineRequest(AgentRequest):
    title: str
    volume: dict


class WorkCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    tags: list[str] = Field(default_factory=list)
    synopsis: str = ""
    cover: str = ""
    wordCount: str = "0字"
    status: str = "草稿"
    updatedAt: str = ""
    createdAt: str = ""
    characters: list[dict] = Field(default_factory=list)
    worldview: list[dict] = Field(default_factory=list)
    terms: list[dict] = Field(default_factory=list)
    timeline: list[dict] = Field(default_factory=list)
    plotNodes: list[dict] = Field(default_factory=list)
    chapters: list[dict] = Field(default_factory=list)
    rules: list[dict] = Field(default_factory=list)
    threads: list[dict] = Field(default_factory=list)
    materials: list[dict] = Field(default_factory=list)
    activities: list[dict] = Field(default_factory=list)
    comicProduction: dict = Field(default_factory=dict)

    @model_validator(mode='after')
    def validate_nested(self):
        validate_work_data(self.model_dump())
        return self


WorkUpdate = WorkCreate


class ComicStageRequest(BaseModel):
    workId: int = Field(gt=0)
    chapterId: str | int | float
    sourceHash: str = Field(pattern=r'^[a-f0-9]{64}$')
    stage: Literal['breakdown', 'direct', 'review']
    blockId: str | None = Field(default=None, max_length=120)
    clipId: str | None = Field(default=None, max_length=120)
    config: ConfigModel
    production: dict = Field(default_factory=dict)
    plan: dict = Field(default_factory=dict)


def find_work(db, work_id):
    work = db.get(Work, work_id)
    if not work:
        raise HTTPException(404, "作品不存在")
    return work


def find_comic_chapter(work, chapter_id):
    for volume in work.chapters or []:
        for chapter in volume.get('chapters', []):
            if str(chapter.get('id')) == str(chapter_id): return chapter
    raise HTTPException(404, '本作品中不存在该章节')


@api.get('/comic/prepare')
def prepare_comic(workId: int, chapterId: str, db: Session = Depends(get_db)):
    work = find_work(db, workId)
    return comic_service.prepare(work, find_comic_chapter(work, chapterId))


@api.post('/comic/stage')
def generate_comic_stage(req: ComicStageRequest, db: Session = Depends(get_db)):
    work = find_work(db, req.workId)
    chapter = find_comic_chapter(work, req.chapterId)
    retrieval_system.sync_work(work)
    try:
        return comic_service.stage(work, chapter, req, retrieval_system.for_work(work.id))
    except (ValueError, TypeError, KeyError, AttributeError):
        raise HTTPException(502, '当前制作阶段的模型结构、引用或时长无效；已完成草稿保留，可重试本阶段')


def snapshot(db, work):
    payload = {c.name: getattr(work, c.name) for c in Work.__table__.columns if c.name != "id"}
    db.add(WorkRevision(work_id=work.id, created_at=datetime.now(timezone.utc).isoformat(), data=payload))
    db.flush()
    old = db.query(WorkRevision).filter_by(work_id=work.id).order_by(WorkRevision.id.desc()).offset(20).all()
    for revision in old:
        db.delete(revision)


def manuscript_signature(chapters):
    return [{key: volume.get(key) for key in ('id', 'title', 'summary')} | {'chapters': [
        {key: chapter.get(key) for key in ('id', 'title', 'summary', 'content')}
        for chapter in volume.get('chapters', [])]} for volume in chapters or []]


def agents_for(req):
    # An omitted work ID has an isolated, empty scope, never another book's data.
    scope = f"draft:{uuid4()}" if req.workId is None else str(req.workId)
    memory = retrieval_system.for_work(scope)
    if req.workId is not None:
        with SessionLocal() as db:
            retrieval_system.sync_work(find_work(db, req.workId))
    return EditorAgent(memory), PlotAgent(memory), LoreAgent(memory)


@app.get("/")
def read_root():
    return {"status": "ok", "mode": "single-user"}


@app.post("/api/session")
def bootstrap_session(request: Request):
    return JSONResponse(local_session(request), headers={"Cache-Control": "no-store"})


@api.get("/works")
def get_works(db: Session = Depends(get_db)):
    return db.query(Work).order_by(Work.id.desc()).all()


@api.get("/works/{work_id}")
def get_work(work_id: int, db: Session = Depends(get_db)):
    return find_work(db, work_id)


@api.post("/works")
def create_work(work: WorkCreate, db: Session = Depends(get_db)):
    saved = Work(**work.model_dump())
    db.add(saved)
    db.commit()
    db.refresh(saved)
    retrieval_system.sync_work(saved)
    return saved


@api.put("/works/{work_id}")
def update_work(work_id: int, work: WorkUpdate, db: Session = Depends(get_db)):
    saved = find_work(db, work_id)
    changes = work.model_dump(exclude_unset=True)
    if "chapters" in changes and manuscript_signature(changes["chapters"]) != manuscript_signature(saved.chapters):
        snapshot(db, saved)
    for key, value in changes.items():
        setattr(saved, key, value)
    db.commit()
    db.refresh(saved)
    retrieval_system.sync_work(saved)
    return saved


@api.delete("/works/{work_id}")
def delete_work(work_id: int, db: Session = Depends(get_db)):
    saved = find_work(db, work_id)
    db.delete(saved)
    db.query(WorkRevision).filter_by(work_id=work_id).delete()
    db.commit()
    retrieval_system.delete_work(work_id)
    return {"ok": True}


@api.get("/works/{work_id}/revisions")
def revisions(work_id: int, db: Session = Depends(get_db)):
    find_work(db, work_id)
    rows = db.query(WorkRevision).filter_by(work_id=work_id).order_by(WorkRevision.id.desc()).all()
    return [{"id": row.id, "createdAt": row.created_at} for row in rows]


@api.post("/works/{work_id}/revisions/{revision_id}/restore")
def restore(work_id: int, revision_id: int, db: Session = Depends(get_db)):
    saved = find_work(db, work_id)
    revision = db.query(WorkRevision).filter_by(work_id=work_id, id=revision_id).first()
    if not revision:
        raise HTTPException(404, "备份不存在")
    payload = dict(revision.data)
    validate_work_data(payload)
    snapshot(db, saved)
    for key, value in payload.items():
        setattr(saved, key, value)
    db.commit()
    db.refresh(saved)
    retrieval_system.sync_work(saved)
    return saved


class ImageUpload(BaseModel):
    data: str = Field(max_length=14_000_000)


@api.post("/uploads")
def upload_image(req: ImageUpload):
    try:
        prefix, encoded = req.data.split(",", 1)
        content = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        raise HTTPException(400, "图片编码无效")
    suffix = None
    if prefix == "data:image/png;base64" and content.startswith(b"\x89PNG\r\n\x1a\n"):
        suffix = ".png"
    elif prefix == "data:image/jpeg;base64" and content.startswith(b"\xff\xd8\xff"):
        suffix = ".jpg"
    elif prefix == "data:image/webp;base64" and content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        suffix = ".webp"
    if not suffix or not content or len(content) > 10 * 1024 * 1024:
        raise HTTPException(400, "仅支持不超过 10 MB 的 PNG/JPEG/WebP 图片")
    name = uuid4().hex + suffix
    (UPLOAD_DIR / name).write_bytes(content)
    return {"url": f"/api/uploads/{name}"}


@api.get("/uploads/{name}")
def get_image(name: str):
    import re
    if not re.fullmatch(r"[a-f0-9]{32}\.(png|jpg|webp)", name):
        raise HTTPException(404, "图片不存在")
    path = UPLOAD_DIR / name
    if not path.is_file():
        raise HTTPException(404, "图片不存在")
    return FileResponse(path, headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=3600"})


@api.get("/health")
def health():
    return {"status": "ok", "mode": "single-user", "retrieval": "SQLite FTS", "copyrightMonitoring": False}


class ProxyRequest(BaseModel):
    url: str = Field(default="", max_length=2048)
    accountId: str | None = Field(default=None, max_length=64)
    headers: dict[str, str] = Field(default_factory=dict)
    body: dict = Field(default_factory=dict)


@api.post("/proxy/chat")
async def proxy_chat(req: ProxyRequest):
    account_id = req.accountId or next((v for k, v in req.headers.items() if k.lower() == 'x-novel-account'), None)
    if account_id:
        messages, model = req.body.get('messages', []), req.body.get('model', '')
        if not req.body.get('stream'):
            text = await asyncio.to_thread(complete_account_chat, account_id, messages, model)
            return JSONResponse(chat_result(text, model))
        generator = chat_stream(account_id, messages, model)
        sentinel = object()
        async def next_account_event():
            task = asyncio.create_task(asyncio.to_thread(next, generator, sentinel))
            try:
                return await asyncio.shield(task)
            except asyncio.CancelledError:
                # Wait for the in-flight read before closing a synchronous generator.
                # This is bounded by the upstream/worker timeouts and never races next().
                with anyio.CancelScope(shield=True):
                    try: await task
                    finally: await asyncio.to_thread(generator.close)
                raise
        first = await next_account_event()
        async def account_events():
            try:
                if first is not sentinel: yield first
                while True:
                    event = await next_account_event()
                    if event is sentinel: break
                    yield event
            except HTTPException as exc:
                yield sse({'error': {'message': str(exc.detail)}})
            except Exception:
                yield sse({'error': {'message': '账号模型生成中断，请检查连接后重试'}})
            finally:
                with anyio.CancelScope(shield=True):
                    await asyncio.to_thread(generator.close)
        return StreamingResponse(account_events(), media_type='text/event-stream',
                                 headers={'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no'})
    target, authority, host = await asyncio.to_thread(provider_target, req.url)
    headers = provider_headers(req.headers, authority)
    client = httpx.AsyncClient(trust_env=False, follow_redirects=False, timeout=120)
    try:
        request = client.build_request("POST", target, headers=headers,
                                       json=req.body, extensions={"sni_hostname": host})
        response = await client.send(request, stream=True)
    except httpx.RequestError:
        await client.aclose()
        raise HTTPException(502, "无法连接模型服务")
    if not response.is_success:
        status = response.status_code if response.status_code >= 400 else 502
        await response.aclose()
        await client.aclose()
        return JSONResponse({"detail": f"模型服务返回 HTTP {response.status_code}"}, status_code=status)

    async def stream():
        try:
            async for chunk in response.aiter_bytes():
                yield chunk
        finally:
            await response.aclose()
            await client.aclose()
    return StreamingResponse(stream(), media_type=response.headers.get("content-type", "application/json"),
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@api.post("/agents/chat")
def chat_with_agent(req: ChatRequest):
    editor, _, _ = agents_for(req)
    return {"response": editor.generate_response(req.prompt, req.context, req.cfg("EditorAgent"))}


@api.post("/agents/generate-novel")
def generate_novel(req: NovelGenerationRequest):
    editor, plot, lore = agents_for(req)
    world = lore.generate_lore(req.title, req.tags, req.synopsis, req.cfg("LoreAgent"))
    validate_work_data(world)
    data = plot.generate_plot(req.title, req.synopsis, world, req.cfg("PlotAgent"))
    validate_work_data(data)
    outline = editor.generate_outline(req.title, data.get("characters", []), data.get("plotNodes", []), req.cfg("EditorAgent"))
    return {"worldview": world, "plot": data, "outline": outline}


def sse(data):
    return "data: " + json.dumps(data, ensure_ascii=False) + "\n\n"


async def outline_events(generator):
    def safe_next():
        return next(generator, None)
    while True:
        update = await asyncio.to_thread(safe_next)
        if update is None:
            break
        yield sse(update)


def event_response(generator):
    return StreamingResponse(generator, media_type="text/event-stream",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@api.post("/agents/generate_industrial_outline")
async def generate_industrial_outline(req: NovelGenerationRequest):
    editor, plot, lore = await asyncio.to_thread(agents_for, req)
    async def stream():
        try:
            yield sse({"step": "正在构建世界观..."})
            world = await asyncio.to_thread(lore.generate_lore, req.title, req.tags, req.synopsis, req.cfg("LoreAgent"))
            validate_work_data(world)
            yield sse({"step": "正在构建角色与主线...", **{k: world.get(k, []) for k in ("worldview", "terms", "timeline", "rules")}})
            data = await asyncio.to_thread(plot.generate_plot, req.title, req.synopsis, world, req.cfg("PlotAgent"))
            validate_work_data(data)
            yield sse({"step": "正在推演章节...", "characters": data.get("characters", []), "plotNodes": data.get("plotNodes", [])})
            gen = editor.generate_long_outline(req.title, req.synopsis, data.get("characters", []), data.get("plotNodes", []), req.cfg("EditorAgent"), target_chapters=req.targetChapters, batch_size=req.batchSize, custom_prompt=req.prompt)
            async for event in outline_events(gen):
                yield event
            yield sse({"status": "done", "worldview": world, "plot": data})
        except Exception:
            log.exception("Outline generation failed")
            yield sse({"error": "生成中断，请检查模型配置并重试；已保存的章节可以继续推演。"})
    return event_response(stream())


@api.post("/agents/resume_industrial_outline")
async def resume_industrial_outline(req: ResumeGenerationRequest):
    editor, _, _ = await asyncio.to_thread(agents_for, req)
    existing = [ch for volume in req.chapters for ch in volume.get("chapters", [])]
    async def stream():
        try:
            yield sse({"step": f"正在从第 {len(existing) + 1} 章恢复推演..."})
            gen = editor.generate_long_outline(req.title, req.synopsis, req.characters, req.plotNodes, req.cfg("EditorAgent"),
                target_chapters=req.targetChapters, batch_size=req.batchSize, start_chapter=len(existing),
                custom_prompt=req.prompt, last_summary=(existing[-1].get("summary") or existing[-1].get("content", "")[-2000:]) if existing else "")
            async for event in outline_events(gen):
                yield event
            yield sse({"status": "done"})
        except Exception:
            log.exception("Outline resume failed")
            yield sse({"error": "续传中断，请检查模型配置；已完成章节已保留。"})
    return event_response(stream())


@api.post("/agents/expand-lore")
def expand_lore(req: ExpandLoreRequest):
    return agents_for(req)[2].expand_lore(req.title, req.parent_item, req.cfg("LoreAgent"))


@api.post("/agents/expand-character")
def expand_character(req: ExpandCharacterRequest):
    return agents_for(req)[1].expand_character(req.title, req.character, req.cfg("PlotAgent"))


@api.post("/agents/expand-outline")
def expand_outline(req: ExpandOutlineRequest):
    return agents_for(req)[0].expand_outline(req.title, req.volume, req.cfg("EditorAgent"))


@api.get("/search")
def search_content(query: str, work_id: int, db: Session = Depends(get_db)):
    retrieval_system.sync_work(find_work(db, work_id))
    return {"results": retrieval_system.for_work(work_id).search(query)}


@app.exception_handler(ValueError)
async def invalid_generation(request, exc):
    return JSONResponse({"detail": "模型响应无效，请检查配置后重试"}, status_code=502)


app.include_router(accounts_router)
app.include_router(callback_router)
app.include_router(api)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8100, reload=True)
