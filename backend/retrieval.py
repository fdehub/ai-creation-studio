"""Work-scoped FTS. Old unscoped records are retained, never mixed in."""
import json
import re
import sqlite3
import threading
import hashlib
from settings import DATA_DIR


class RetrievalSystem:
    def __init__(self, db_path=None):
        self.conn = sqlite3.connect(str(db_path or DATA_DIR / "memory.db"), check_same_thread=False)
        self.lock = threading.RLock()
        self.conn.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS work_memory
            USING fts5(work_id UNINDEXED, doc_id UNINDEXED, content, type UNINDEXED)""")
        self.conn.commit()

    def for_work(self, work_id):
        return ScopedMemory(self, str(work_id))

    def search(self, query, search_type="hybrid", work_id="legacy-cli"):
        tokens = re.findall(r"\w+", query)[:5]
        if not tokens:
            return []
        match = " OR ".join('"' + t + '"' for t in tokens)
        with self.lock:
            rows = self.conn.execute(
                "SELECT content FROM work_memory WHERE work_memory MATCH ? AND work_id=? ORDER BY rank LIMIT 5",
                (match, str(work_id)),
            ).fetchall()
            # unicode61 does not segment Chinese sentences into individual words.
            # A bounded literal-substring fallback keeps Chinese queries useful
            # while retaining the same mandatory work scope.
            if not rows and any(ord(char) > 127 for char in query):
                clauses = ' OR '.join('instr(content, ?) > 0' for _ in tokens)
                rows = self.conn.execute(f'SELECT content FROM work_memory WHERE work_id=? AND ({clauses}) LIMIT 5', (str(work_id), *tokens)).fetchall()
        return [{"source": "sqlite_fts", "text": row[0]} for row in rows]

    def index_document(self, doc_id, content, metadata, work_id="legacy-cli"):
        with self.lock, self.conn:
            self.conn.execute("DELETE FROM work_memory WHERE work_id=? AND doc_id=?", (str(work_id), doc_id))
            self.conn.execute("INSERT INTO work_memory VALUES (?,?,?,?)",
                              (str(work_id), doc_id, content, metadata.get("type", "")))

    def delete_work(self, work_id):
        with self.lock, self.conn:
            self.conn.execute("DELETE FROM work_memory WHERE work_id=?", (str(work_id),))

    def sync_work(self, work):
        documents = []
        for name in ("characters", "worldview", "terms", "timeline", "rules", "plotNodes"):
            for i, item in enumerate(getattr(work, name) or []):
                documents.append((str(work.id), f"{name}:{i}", json.dumps(item, ensure_ascii=False), name))
        for volume in work.chapters or []:
            for chapter in volume.get("chapters", []):
                manuscript = {key: chapter.get(key) for key in ('id', 'title', 'summary', 'content')}
                documents.append((str(work.id), f"chapter:{chapter.get('id')}",
                                  json.dumps(manuscript, ensure_ascii=False), "chapter"))
                digest = hashlib.sha256((chapter.get('content') or '').encode('utf-8')).hexdigest()
                for field in ('comicDraft', 'comicPlan'):
                    plan = chapter.get(field) or {}
                    if plan.get('status') == 'complete' and plan.get('sourceHash') == digest and plan.get('endingState'):
                        documents.append((str(work.id), f"comic-ending:{chapter.get('id')}",
                            json.dumps({'chapter': chapter.get('title'), 'endingState': plan['endingState']}, ensure_ascii=False), 'comic-continuity'))
                        break
        production = getattr(work, 'comicProduction', None) or {}
        for kind, assets in production.get('bible', {}).items():
            for asset in assets:
                documents.append((str(work.id), f"comic-asset:{kind}:{asset['id']}", json.dumps(asset, ensure_ascii=False), 'comic-bible'))
        with self.lock, self.conn:
            self.conn.execute("DELETE FROM work_memory WHERE work_id=?", (str(work.id),))
            self.conn.executemany("INSERT INTO work_memory VALUES (?,?,?,?)", documents)

    def close(self):
        self.conn.close()


class ScopedMemory:
    def __init__(self, memory, work_id):
        self.memory, self.work_id = memory, work_id

    def search(self, query, search_type="hybrid"):
        return self.memory.search(query, search_type, self.work_id)

    def index_document(self, doc_id, content, metadata):
        # API generation only reads committed memory. Save-time indexing keeps
        # interrupted generation and deleted characters out of future prompts.
        pass
