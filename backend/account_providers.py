"""Normalize account backends to the application's existing text/chat interface."""
import json
from uuid import uuid4
import httpx
from fastapi import HTTPException
from account_store import vault
from chatgpt_oauth import RESOURCE, access_credentials
from muse_accounts import muse_text
from security import first_party_target


def response_payload(messages, model):
    if not isinstance(model, str) or not model.strip(): raise HTTPException(400, '请先选择该账号可用的模型')
    if not isinstance(messages, list) or not messages: raise HTTPException(400, '写作消息不能为空')
    instructions, inputs = [], []
    for message in messages:
        if not isinstance(message, dict) or not isinstance(message.get('content'), str):
            raise HTTPException(400, '账号模型目前仅支持纯文本写作')
        role = message.get('role')
        if role in ('system', 'developer'): instructions.append(message['content'])
        elif role in ('user', 'assistant'): inputs.append({'role': role, 'content': message['content']})
        else: raise HTTPException(400, '不支持的写作消息角色')
    payload = {'model': model, 'store': False, 'stream': True,
               'input': inputs or [{'role': 'user', 'content': '请完成上述写作任务。'}]}
    if instructions: payload['instructions'] = '\n\n'.join(instructions)
    return payload


def chatgpt_text(account_id, messages, model):
    payload = response_payload(messages, model)
    target, host, sni = first_party_target(RESOURCE + '/responses', {'api.openai.com'})
    for attempt in range(2):
        account = access_credentials(account_id, force=bool(attempt))
        try:
            with httpx.Client(timeout=httpx.Timeout(180, connect=20), follow_redirects=False, trust_env=False) as client:
                with client.stream('POST', target, json=payload,
                    headers={'Host': host, 'Authorization': 'Bearer ' + account['access_token'], 'Content-Type': 'application/json'},
                    extensions={'sni_hostname': sni}) as response:
                    if response.status_code == 401 and not attempt: continue
                    if not response.is_success:
                        raise HTTPException(response.status_code if response.status_code >= 400 else 502,
                                            f'ChatGPT 模型服务返回 HTTP {response.status_code}，请检查授权、模型和额度')
                    completed = False
                    data_lines = []
                    for line in response.iter_lines():
                        if line.startswith('data:'): data_lines.append(line[5:].lstrip(' '))
                        elif not line and data_lines:
                            raw = '\n'.join(data_lines); data_lines = []
                            if raw == '[DONE]': continue
                            try: event = json.loads(raw)
                            except ValueError: raise HTTPException(502, 'ChatGPT 数据流格式无效')
                            event_type = event.get('type')
                            if event_type == 'response.output_text.delta':
                                delta = event.get('delta')
                                if isinstance(delta, str): yield delta
                            elif event_type == 'response.completed': completed = True
                            elif event_type in ('response.failed', 'response.incomplete', 'error'):
                                raise HTTPException(409, 'ChatGPT 生成未完成，请检查账号额度或模型可用性；原文已保留')
                    if not completed or data_lines: raise HTTPException(502, 'ChatGPT 数据流中断，未收到完成事件')
                    return
        except httpx.HTTPError:
            raise HTTPException(502, 'ChatGPT 连接中断，请重试')
    raise HTTPException(409, 'ChatGPT 认证失败，请重新授权')


def account_text(account_id, messages, model):
    account = vault.account(account_id)
    if account['provider'] == 'chatgpt': yield from chatgpt_text(account_id, messages, model)
    elif account['provider'] == 'muse':
        if model != 'muse': raise HTTPException(400, 'Muse 网页会话仅使用 Muse 当前模型，不支持其他平台模型别名')
        yield from muse_text(account_id, messages)
    else: raise HTTPException(400, '不支持的账号类型')


def complete_account_chat(account_id, messages, model):
    text = ''.join(account_text(account_id, messages, model))
    if not text.strip(): raise HTTPException(502, '账号模型未返回正文')
    return text


def chat_result(text, model):
    return {'id': 'chatcmpl-' + uuid4().hex, 'object': 'chat.completion', 'model': model,
            'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': text}, 'finish_reason': 'stop'}]}


def chat_stream(account_id, messages, model):
    identifier = 'chatcmpl-' + uuid4().hex
    for text in account_text(account_id, messages, model):
        event = {'id': identifier, 'object': 'chat.completion.chunk', 'model': model,
                 'choices': [{'index': 0, 'delta': {'content': text}, 'finish_reason': None}]}
        yield 'data: ' + json.dumps(event, ensure_ascii=False) + '\n\n'
    yield 'data: ' + json.dumps({'id': identifier, 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]}) + '\n\n'
    yield 'data: [DONE]\n\n'
