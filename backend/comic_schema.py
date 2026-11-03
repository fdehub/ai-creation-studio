"""Versioned comic production records, shared by generation and work writes."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Record(BaseModel):
    model_config = ConfigDict(extra='forbid')


class ProductionSettings(Record):
    style: Literal['realistic', 'anime', '3d', 'custom'] = 'realistic'
    styleNotes: str = Field(default='', max_length=3000)
    ratio: Literal['9:16', '16:9', '1:1'] = '9:16'
    targetDuration: float = Field(default=15, ge=3, le=120)
    shotsPerClip: int = Field(default=5, ge=1, le=12)
    speechRate: float = Field(default=4, ge=1, le=10)
    fidelity: Literal['faithful', 'adapted'] = 'faithful'
    exportTarget: Literal['generic', 'seedance', 'midjourney'] = 'seedance'


class Asset(Record):
    id: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default='', max_length=5000)
    voice: str = Field(default='', max_length=1200)
    lighting: str = Field(default='', max_length=1500)
    axis: str = Field(default='', max_length=1500)
    referenceUrl: str = Field(default='', max_length=500)
    locked: bool = False

    @field_validator('referenceUrl')
    @classmethod
    def local_reference(cls, value):
        import re
        if value and not re.fullmatch(r'/api/uploads/[a-f0-9]{32}\.(png|jpg|webp)', value):
            raise ValueError('参考素材仅支持平台内已上传的图片')
        return value


class ProductionBible(Record):
    characters: list[Asset] = Field(default_factory=list, max_length=200)
    scenes: list[Asset] = Field(default_factory=list, max_length=200)
    props: list[Asset] = Field(default_factory=list, max_length=200)

    @field_validator('characters', 'scenes', 'props')
    @classmethod
    def unique_assets(cls, assets):
        if len({item.id for item in assets}) != len(assets): raise ValueError('制作设定 ID 重复')
        if len({item.name.strip().casefold() for item in assets}) != len(assets): raise ValueError('同类制作设定名称重复')
        return assets


class ComicProduction(Record):
    schemaVersion: Literal[1] = 1
    settings: ProductionSettings = Field(default_factory=ProductionSettings)
    bible: ProductionBible = Field(default_factory=ProductionBible)


class Passage(Record):
    id: str = Field(min_length=1, max_length=80)
    text: str = Field(max_length=2000)


class Beat(Record):
    id: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=2000)
    sourceIds: list[str] = Field(min_length=1, max_length=100)


class Clip(Record):
    id: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    sceneId: str = Field(default='', max_length=120)
    characterIds: list[str] = Field(default_factory=list, max_length=30)
    sourceIds: list[str] = Field(default_factory=list, max_length=100)
    beatIds: list[str] = Field(default_factory=list, max_length=100)
    summary: str = Field(default='', max_length=3000)


class Dialogue(Record):
    characterId: str = Field(default='', max_length=120)
    text: str = Field(min_length=1, max_length=3000)
    emotion: str = Field(default='', max_length=300)


class ProductionShot(Record):
    schemaVersion: Literal[2] = 2
    id: str = Field(min_length=1, max_length=120)
    shot: int = Field(ge=1)
    clipId: str = Field(min_length=1, max_length=120)
    sceneId: str = Field(default='', max_length=120)
    characterIds: list[str] = Field(default_factory=list, max_length=30)
    sourceIds: list[str] = Field(default_factory=list, max_length=100)
    duration: float = Field(default=3, ge=.1, le=120)
    shotSize: str = Field(default='中景', max_length=100)
    camera: str = Field(default='固定', max_length=400)
    angle: str = Field(default='平视', max_length=200)
    composition: str = Field(default='', max_length=1000)
    desc: str = Field(min_length=1, max_length=5000)
    dialogue: str = Field(default='', max_length=5000)
    lines: list[Dialogue] = Field(default_factory=list, max_length=50)
    prompt: str = Field(default='', max_length=6000)
    videoPromptOverride: str = Field(default='', max_length=10000)
    lighting: str = Field(default='', max_length=1500)
    transition: str = Field(default='', max_length=1000)
    sfx: str = Field(default='', max_length=1000)
    startState: str = Field(default='', max_length=2000)
    endState: str = Field(default='', max_length=2000)
    locked: bool = False


class ReviewIssue(Record):
    severity: Literal['error', 'warning', 'info'] = 'warning'
    code: str = Field(default='MODEL_REVIEW', max_length=100)
    message: str = Field(min_length=1, max_length=2000)
    shotId: str = Field(default='', max_length=120)
    clipId: str = Field(default='', max_length=120)


class ComicPlan(Record):
    schemaVersion: Literal[2] = 2
    sourceHash: str = Field(default='', max_length=64)
    settings: ProductionSettings = Field(default_factory=ProductionSettings)
    baseProduction: ComicProduction = Field(default_factory=ComicProduction)
    bible: ProductionBible = Field(default_factory=ProductionBible)
    passages: list[Passage] = Field(default_factory=list, max_length=500)
    completedBlocks: list[str] = Field(default_factory=list, max_length=500)
    reviewedClips: list[str] = Field(default_factory=list, max_length=200)
    beats: list[Beat] = Field(default_factory=list, max_length=500)
    clips: list[Clip] = Field(default_factory=list, max_length=200)
    shots: list[ProductionShot] = Field(default_factory=list, max_length=500)
    status: Literal['planning', 'directing', 'reviewing', 'interrupted', 'complete', 'manual', 'imported'] = 'planning'
    endingState: str = Field(default='', max_length=4000)
    previousContext: str = Field(default='', max_length=6000)
    reviewSummary: str = Field(default='', max_length=3000)
    issues: list[ReviewIssue] = Field(default_factory=list, max_length=100)
    reviewedSignature: str = Field(default='', max_length=64)
    generatedAt: str = Field(default='', max_length=80)


def validate_comic_data(work):
    if 'comicProduction' in work: ComicProduction.model_validate(work['comicProduction'])
    for volume in work.get('chapters', []):
        for chapter in volume.get('chapters', []):
            for field in ('comicPlan', 'comicDraft'):
                if field in chapter and chapter[field] is not None: ComicPlan.model_validate(chapter[field])
            for shot in chapter.get('comicShots', []):
                if shot.get('schemaVersion') == 2: ProductionShot.model_validate(shot)
