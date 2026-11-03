import os
import json
import re
import httpx
from security import post_provider
from retrieval import RetrievalSystem
from work_validation import validate_work_data

def extract_json(text: str) -> dict | list:
    json_str = text
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
    if json_match:
        json_str = json_match.group(1).strip()
    else:
        # Check for both object {} and array []
        first_brace = text.find('{')
        first_bracket = text.find('[')
        
        is_array = False
        if first_bracket != -1 and (first_brace == -1 or first_bracket < first_brace):
            is_array = True
            
        if is_array:
            first_idx = first_bracket
            last_idx = text.rfind(']')
        else:
            first_idx = first_brace
            last_idx = text.rfind('}')
            
        if first_idx != -1 and last_idx != -1 and last_idx > first_idx:
            json_str = text[first_idx:last_idx+1]
    
    try:
        return json.loads(json_str, strict=False)
    except Exception as e:
        print("JSON parse error:", e)
        raise ValueError("JSON_PARSE_ERROR")

class BaseAgent:
    def __init__(self, retrieval_system: RetrievalSystem, role: str):
        self.retrieval = retrieval_system
        self.role = role

    def call_llm(self, system_prompt: str, user_message: str, config: dict, is_json: bool = False) -> str | dict:
        if config.get('authType') == 'account':
            from account_providers import complete_account_chat
            content = complete_account_chat(config.get('accountId'), [
                {'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': user_message}], config.get('modelName') or '')
            return extract_json(content) if is_json else content
        api_key = config.get("apiKey")
        if not api_key:
            raise ValueError(f"请先在【AI引擎策略】中配置您的 API Key！")
        
        base_url = config.get("baseUrl")
        if base_url:
            base_url = base_url.rstrip("/")
        else:
            base_url = "https://api.openai.com/v1"
            
        model_name = config.get("modelName") or "gpt-3.5-turbo"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            "temperature": 0.8,
            "max_tokens": 4096
        }
        
        import time
        max_retries = 4
        for attempt in range(max_retries):
            try:
                resp = post_provider(f"{base_url}/chat/completions", headers, payload, timeout=120)
                if not resp.is_success:
                    if resp.status_code in [500, 502, 503, 504, 429] and attempt < max_retries - 1:
                        print(f"API Error {resp.status_code}. Retrying in {2 ** attempt}s...")
                        time.sleep(2 ** attempt)
                        continue
                    raise ValueError(f"模型服务返回 HTTP {resp.status_code}")
                    
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                
                if is_json:
                    try:
                        return extract_json(content)
                    except ValueError as e:
                        if str(e) == "JSON_PARSE_ERROR" and attempt < max_retries - 1:
                            print(f"JSON truncated or invalid. Retrying {attempt+1}/{max_retries}...")
                            time.sleep(2 ** attempt)
                            continue
                        raise ValueError("大模型返回的数据被截断或格式错误（这通常是因为模型单次输出字数达到了上限）。请重试或在提示词中要求模型简短输出。")
                return content
            except httpx.RequestError as e:
                if attempt < max_retries - 1:
                    print(f"模型连接失败，{2 ** attempt}s 后重试...")
                    time.sleep(2 ** attempt)
                    continue
                raise ValueError("网络或模型服务连接失败") from e

class LoreAgent(BaseAgent):
    def __init__(self, retrieval_system):
        super().__init__(retrieval_system, "LoreAgent")

    def generate_lore(self, title: str, tags: str, synopsis: str, config: dict) -> dict:
        system_prompt = """你是一个顶级网文世界观架构师(LoreAgent)。严格输出JSON，不要多余解释。格式：
{
  "worldview": [ { "id": 1, "title": "分类", "icon": "🗺️", "items": [{ "name": "条目", "desc": "描述" }] } ],
  "terms": [ { "id": 1, "title": "分类", "icon": "📖", "items": [{ "name": "术语", "desc": "描述" }] } ],
  "timeline": [ { "id": 1, "title": "纪元", "icon": "⏳", "items": [{ "name": "事件", "desc": "描述" }] } ],
  "rules": [ { "id": 1, "name": "法则名称", "desc": "法则描述", "type": "Rule", "isLocked": true } ]
}
要求：生成2个世界观分类（每个1-2条），2个核心术语，2个历史纪元，以及2条决定小说基调的最高法则。语言精炼。"""
        user_message = f"书名：《{title}》\n标签：{tags}\n简介：{synopsis}"
        
        data = self.call_llm(system_prompt, user_message, config, is_json=True)
        
        # Fallbacks for Chinese keys
        if not isinstance(data, dict): raise ValueError('世界观资料应为对象')
        if "worldview" not in data and "世界观" in data: data["worldview"] = data["世界观"]
        if "terms" not in data and "核心术语" in data: data["terms"] = data["核心术语"]
        if "terms" not in data and "术语" in data: data["terms"] = data["术语"]
        if "timeline" not in data and "历史纪元" in data: data["timeline"] = data["历史纪元"]
        if "timeline" not in data and "纪元" in data: data["timeline"] = data["纪元"]
        if "rules" not in data and "最高法则" in data: data["rules"] = data["最高法则"]
        if "rules" not in data and "法则" in data: data["rules"] = data["法则"]
        
        validate_work_data(data)
        # Save to RAG
        for wv in data.get("worldview", []):
            for item in wv.get("items", []):
                content = f"世界观 - {wv.get('title', '')} - {item.get('name', '')}: {item.get('desc', '')}"
                self.retrieval.index_document(f"wv_{item.get('name', '')}", content, {"type": "worldview"})
                
        return data

    def expand_lore(self, title: str, parent_item: dict, config: dict) -> dict:
        system_prompt = """你是一个顶级网文世界观架构师(LoreAgent)。用户想深挖某个世界观设定的细节，请为其生成相关的衍生词条（如势力、功法、地理等）。
严格输出JSON，格式：
{
  "items": [ { "name": "新衍生词条名", "desc": "100字以上的详细描述" } ]
}
要求：生成3-5个子词条，语言必须充满网文爽感和史诗感。"""
        user_message = f"书名：《{title}》\n需要深挖的母词条：{json.dumps(parent_item, ensure_ascii=False)}"
        
        data = self.call_llm(system_prompt, user_message, config, is_json=True)
        if not isinstance(data, dict): raise ValueError('衍生词条应为对象')
        validate_work_data({'worldview': [{'items': data.get('items', [])}]})
        # Save to RAG
        for item in data.get("items", []):
            content = f"世界观衍生 - 母词条[{parent_item.get('name')}] -> {item.get('name', '')}: {item.get('desc', '')}"
            self.retrieval.index_document(f"wv_exp_{item.get('name', '')}", content, {"type": "worldview"})
            
        return data

class PlotAgent(BaseAgent):
    def __init__(self, retrieval_system):
        super().__init__(retrieval_system, "PlotAgent")

    def generate_plot(self, title: str, synopsis: str, lore: dict, config: dict) -> dict:
        system_prompt = """你是一个顶级网文剧情主编(PlotAgent)。参考提供的世界观，严格输出JSON，不要多余解释。格式：
{
  "characters": [ { "id": 1, "name": "名字", "avatarUrl": "linear-gradient(135deg, #f6d365 0%, #fda085 100%)", "faction": "主角/反派/配角", "tags": ["标签1", "标签2"], "description": "描述" } ],
  "plotNodes": [ { "id": 1, "type": "起/承/转/合", "title": "节点", "tension": 20, "desc": "梗概", "isAi": true } ]
}
注意：必须严格使用英文键名（characters 和 plotNodes），绝对不能翻译成中文键名！
要求：为了支撑长篇小说，必须生成 5-10 名核心角色，并生成 10-15 个核心剧情宏观节点（起承转合），语言精炼。"""
        user_message = f"书名：《{title}》\n简介：{synopsis}\n世界观设定：{json.dumps(lore, ensure_ascii=False)}"
        
        data = self.call_llm(system_prompt, user_message, config, is_json=True)
        
        # Fallback for Chinese keys
        if not isinstance(data, dict): raise ValueError('人物与剧情资料应为对象')
        if "characters" not in data and "角色" in data:
            data["characters"] = data["角色"]
        if "plotNodes" not in data and "剧情节点" in data:
            data["plotNodes"] = data["剧情节点"]
        if "plotNodes" not in data and "剧情" in data:
            data["plotNodes"] = data["剧情"]
            
        validate_work_data(data)
        # Save to RAG
        for char in data.get("characters", []):
            content = f"角色 - {char.get('name', '')} ({char.get('faction', '')}): {char.get('description', '')}"
            self.retrieval.index_document(f"char_{char.get('name', '')}", content, {"type": "character"})
            
        return data

    def expand_character(self, title: str, character: dict, config: dict) -> dict:
        system_prompt = """你是一个顶级网文剧情主编(PlotAgent)。用户需要深挖某个角色的背景。
严格输出JSON，格式：
{
  "expanded_desc": "300字以上的角色深度解析，包含身世背景、金手指/功法缺陷、近期核心目的、性格软肋，以及和主角的关系。"
}"""
        user_message = f"书名：《{title}》\n需要深挖的角色：{json.dumps(character, ensure_ascii=False)}"
        
        data = self.call_llm(system_prompt, user_message, config, is_json=True)
        if not isinstance(data, dict) or not isinstance(data.get('expanded_desc'), str) or not data['expanded_desc'].strip():
            raise ValueError('角色深度档案缺少有效描述')
        # Save to RAG
        content = f"角色深度档案 - {character.get('name')}: {data.get('expanded_desc')}"
        self.retrieval.index_document(f"char_exp_{character.get('name')}", content, {"type": "character"})
            
        return data

class EditorAgent(BaseAgent):
    def __init__(self, retrieval_system):
        super().__init__(retrieval_system, "EditorAgent")

    def generate_outline(self, title: str, characters: list, plot_nodes: list, config: dict) -> dict:
        # Retrieve committed, work-scoped context from SQLite FTS.
        rag_context = self.retrieval.search(f"{title} 核心世界观与设定", search_type="rag")
        rag_text = "\n".join([r['text'] for r in rag_context]) if rag_context else "无额外记忆片段。"
        
        system_prompt = """你是一个顶级网文主笔编辑(EditorAgent)。参考角色、剧情和检索到的历史记忆，严格输出JSON，不要多余解释。格式：
{
  "chapters": [
    {
      "id": 1, "title": "第一卷：卷名", "isExpanded": true,
      "chapters": [ { "id": 11, "title": "第一章：章名", "wordCount": 0, "status": "大纲", "date": "-", "content": "剧情摘要" } ]
    }
  ]
}
要求：生成1卷大纲，包含2-3章。语言精炼。"""
        user_message = f"书名：《{title}》\n核心角色：{json.dumps(characters, ensure_ascii=False)}\n剧情主线：{json.dumps(plot_nodes, ensure_ascii=False)}\n\n[Memory Keeper 检索到的历史记忆]:\n{rag_text}"
        
        data = self.call_llm(system_prompt, user_message, config, is_json=True)
        
        validate_work_data(data)
        # Save chapters to RAG
        for vol in data.get("chapters", []):
            for ch in vol.get("chapters", []):
                content = f"章节大纲 - {ch.get('title', '')}: {ch.get('content', '')}"
                self.retrieval.index_document(f"chap_{ch.get('id', '')}", content, {"type": "chapter"})
                
        return data

    def expand_outline(self, title: str, volume: dict, config: dict) -> dict:
        rag_context = self.retrieval.search(f"{title} {volume.get('title')} 核心设定", search_type="rag")
        rag_text = "\n".join([r['text'] for r in rag_context]) if rag_context else "无额外记忆片段。"
        
        system_prompt = """你是一个顶级网文主笔编辑(EditorAgent)。用户需要为宏观的大纲卷宗生成具体的章节细纲。
参考检索到的历史记忆，严格输出JSON，格式：
{
  "chapters": [ { "id": 999, "title": "第X章：章名", "wordCount": 2000, "status": "细纲", "date": "-", "content": "至少100字的详细场景节拍（Beat）" } ]
}
要求：为该卷依次推进剧情，生成全新的1-2个章节细纲，必须包含明确的爽点和悬念。"""
        user_message = f"书名：《{title}》\n卷名与摘要：{json.dumps(volume, ensure_ascii=False)}\n\n[Memory Keeper 检索结果]:\n{rag_text}"
        
        data = self.call_llm(system_prompt, user_message, config, is_json=True)
        if not isinstance(data, dict): raise ValueError('章节细纲应为对象')
        validate_work_data({'chapters': [{'chapters': data.get('chapters', [])}]})
        # Save to RAG
        for ch in data.get("chapters", []):
            content = f"章节细纲 - {ch.get('title', '')}: {ch.get('content', '')}"
            self.retrieval.index_document(f"chap_exp_{ch.get('title', '')}", content, {"type": "chapter"})
            
        return data

    def generate_long_outline(self, title, synopsis, characters, plot_nodes, config,
                              target_chapters=100, batch_size=10, start_chapter=0,
                              custom_prompt=None, last_summary=""):
        """Yield cumulative new chapters only; a failed batch never advances progress."""
        from uuid import uuid4
        template = custom_prompt or """你是专业小说编辑，按顺序生成章节细纲。
生成第 {start} 章到第 {end} 章，共 {count} 章，紧接上文：{last_summary}
只输出 JSON 数组，每项包含 chapterNum、title、summary。"""
        match = re.search(r'全书总篇幅[^\d]*(\d+)', template)
        if match:
            target_chapters = int(match.group(1))
        if not 1 <= target_chapters <= 2000 or not 1 <= batch_size <= 20:
            raise ValueError("章节目标须为 1-2000，批量大小须为 1-20")
        run_id = uuid4().hex
        generated = []
        context = self.retrieval.search(f"{title} 核心世界观与设定")
        previous = last_summary or "无（这是小说的开头）。"
        for offset in range(start_chapter, target_chapters, batch_size):
            count = min(batch_size, target_chapters - offset)
            yield {"step": f"正在推演第 {offset + 1} 到 {offset + count} 章大纲..."}
            prompt = template.replace("{start}", str(offset + 1)).replace("{end}", str(offset + count)).replace("{count}", str(count)).replace("{last_summary}", previous)
            message = json.dumps({"title": title, "synopsis": synopsis, "characters": characters,
                                  "plotNodes": plot_nodes, "memory": context}, ensure_ascii=False)
            result = self.call_llm(prompt, message, config, is_json=True)
            batch = result if isinstance(result, list) else result.get("chapters", []) if isinstance(result, dict) else None
            if not isinstance(batch, list) or len(batch) != count or any(not isinstance(ch, dict) for ch in batch):
                raise ValueError("模型返回的章节数量不完整，请从已完成位置继续")
            for i, ch in enumerate(batch):
                number = offset + i + 1
                name = ch.get("title") or ch.get("标题") or ch.get("章名")
                summary = ch.get("summary") or ch.get("摘要") or ch.get("简介") or ch.get("梗概")
                if not isinstance(name, str) or not isinstance(summary, str) or not name.strip() or not summary.strip():
                    raise ValueError("模型章节缺少标题或摘要")
                generated.append({"id": f"chap-{run_id}-{number}", "chapterNum": number,
                    "title": f"第{number}章 {name}", "summary": summary,
                    "wordCount": 0, "status": "大纲", "content": ""})
            previous = generated[-1]["summary"]
            yield {"step": f"已完成到第 {offset + count} 章", "chapters": [{
                "id": "vol-1", "title": "第一卷：起源", "summary": synopsis,
                "isExpanded": True, "chapters": [dict(ch) for ch in generated]}]}

    def generate_response(self, prompt: str, local_context: str = "", config: dict = {}) -> str:
        # For the chat interface in Editor
        retrieved_context = self.retrieval.search(prompt, search_type="rag")
        full_context = local_context + "\n[Memory Keeper 检索结果]\n" + str(retrieved_context)

        system_prompt = "你是一个专业的小说编辑。请根据Memory Keeper提供的长期记忆背景资料回答作者的问题，如果记忆缺失则根据常理回答。"
        user_message = f"[背景资料]:\n{full_context}\n\n[作者问题]:\n{prompt}"
        
        return self.call_llm(system_prompt, user_message, config)

class AuthorAgent(BaseAgent):
    def __init__(self, retrieval_system):
        super().__init__(retrieval_system, "AuthorAgent")

    def write_chapter(self, title: str, chapter_title: str, chapter_outline: str, config: dict) -> str:
        # Search RAG for related characters and worldview elements based on chapter outline
        rag_context = self.retrieval.search(f"{title} {chapter_title} {chapter_outline}", search_type="rag")
        rag_text = "\n".join([r['text'] for r in rag_context]) if rag_context else "无额外记忆片段。"
        
        system_prompt = """你是一位白金级网文大神主笔(AuthorAgent)。你的任务是根据细纲，撰写一章网文正文。
要求：
1. 字数要求：2000字左右。
2. 风格要求：爽文风格，画面感强，人物对话符合性格，避免干瘪的叙述。
3. 结构要求：有环境描写，有内心戏，高潮处必须有情绪爆发点。
4. 输出格式：直接输出正文，不要输出任何如“好的，以下是为您生成的...”等废话，也不要Markdown代码块。"""
        
        user_message = f"书名：《{title}》\n章节名：{chapter_title}\n本章节拍(细纲)：{chapter_outline}\n\n[Memory Keeper 检索到的历史记忆（可作为设定参考）]:\n{rag_text}\n\n请开始撰写本章正文："
        
        res_content = self.call_llm(system_prompt, user_message, config)
        return res_content
