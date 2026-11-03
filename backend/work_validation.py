"""Validate nested work data before it reaches SQLite or a streaming client."""
import math


def validate_work_data(data):
    if not isinstance(data, dict): raise ValueError('作品资料应为对象')

    def objects(value, field):
        if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
            raise ValueError(f'{field} 应为对象数组')
        return value

    def text_fields(row):
        for key in ('title', 'name', 'content', 'summary', 'desc', 'description', 'faction', 'dialogue', 'prompt'):
            if key in row and not isinstance(row[key], str): raise ValueError(f'{key} 应为文本')
        if 'tags' in row and (not isinstance(row['tags'], list) or any(not isinstance(tag, str) for tag in row['tags'])):
            raise ValueError('tags 应为文本数组')

    def item_tree(rows, depth=0):
        if depth > 12: raise ValueError('设定层级过深')
        for row in objects(rows, '设定'):
            text_fields(row)
            if 'items' in row: item_tree(row['items'], depth + 1)
            if 'children' in row: item_tree(row['children'], depth + 1)

    for field in ('worldview', 'terms', 'timeline', 'rules'):
        if field in data: item_tree(data[field])
    for field in ('characters', 'plotNodes', 'threads', 'materials', 'activities'):
        for row in objects(data.get(field, []), field):
            text_fields(row)
            if 'states' in row:
                for state in objects(row['states'], 'states'):
                    if 'chapterRange' in state and (not isinstance(state['chapterRange'], list) or len(state['chapterRange']) != 2 or any(type(n) not in (int, float) or (type(n) is float and not math.isfinite(n)) for n in state['chapterRange'])):
                        raise ValueError('角色状态章节范围无效')
    seen = set()
    for volume in objects(data.get('chapters', []), 'chapters'):
        text_fields(volume)
        for chapter in objects(volume.get('chapters', []), '分卷章节'):
            text_fields(chapter)
            if 'id' in chapter:
                identifier = chapter['id']
                if type(identifier) not in (str, int, float) or (type(identifier) is float and not math.isfinite(identifier)) or identifier in seen:
                    raise ValueError('章节 ID 无效或重复')
                seen.add(identifier)
            if 'comicShots' in chapter:
                for shot in objects(chapter['comicShots'], 'comicShots'): text_fields(shot)
    return data
