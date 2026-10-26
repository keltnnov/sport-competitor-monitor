"""
Pydantic схемы для API
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


# === Запросы ===

class TextAnalysisRequest(BaseModel):
    """Запрос на анализ текста"""
    text: str = Field(..., min_length=10, description="Текст для анализа")


class ParseDemoRequest(BaseModel):
    """Запрос на парсинг URL"""
    url: str = Field(..., description="URL для парсинга")


# === Ответы ===

class CompetitorAnalysis(BaseModel):
    """Структурированный анализ конкурента"""
    strengths: List[str] = Field(default_factory=list, description="Сильные стороны")
    weaknesses: List[str] = Field(default_factory=list, description="Слабые стороны")
    unique_offers: List[str] = Field(default_factory=list, description="Уникальные предложения")
    recommendations: List[str] = Field(default_factory=list, description="Рекомендации")
    summary: str = Field("", description="Общее резюме")
    # Поля под нишу «производство спортивной одежды»
    design_score: int = Field(0, ge=0, le=10, description="Оценка визуального стиля бренда (0-10)")
    animation_potential: int = Field(0, ge=0, le=10, description="Потенциал для анимации/моушн-контента (0-10)")
    brand_positioning: str = Field("", description="Позиционирование: перфоманс / лайфстайл / премиум / масс-маркет")
    target_audience: str = Field("", description="Целевая аудитория")
    price_segment: str = Field("", description="Ценовой сегмент")


class ImageAnalysis(BaseModel):
    """Анализ изображения"""
    description: str = Field("", description="Описание изображения")
    marketing_insights: List[str] = Field(default_factory=list, description="Маркетинговые инсайты")
    visual_style_score: int = Field(0, ge=0, le=10, description="Оценка визуального стиля (0-10)")
    visual_style_analysis: str = Field("", description="Анализ визуального стиля")
    recommendations: List[str] = Field(default_factory=list, description="Рекомендации")
    # Поля под нишу «производство спортивной одежды»
    design_score: int = Field(0, ge=0, le=10, description="Оценка дизайна (0-10)")
    animation_potential: int = Field(0, ge=0, le=10, description="Потенциал для анимации/моушн-контента (0-10)")
    animation_ideas: List[str] = Field(default_factory=list, description="Идеи анимации для этого визуала")
    product_presentation: str = Field("", description="Как показан продукт: ткань, посадка, движение")


class ParsedContent(BaseModel):
    """Результат парсинга страницы"""
    url: str
    title: Optional[str] = None
    h1: Optional[str] = None
    first_paragraph: Optional[str] = None
    screenshot_path: Optional[str] = None
    analysis: Optional[CompetitorAnalysis] = None
    error: Optional[str] = None


class TextAnalysisResponse(BaseModel):
    """Ответ на анализ текста"""
    success: bool
    analysis: Optional[CompetitorAnalysis] = None
    error: Optional[str] = None


class ImageAnalysisResponse(BaseModel):
    """Ответ на анализ изображения"""
    success: bool
    analysis: Optional[ImageAnalysis] = None
    error: Optional[str] = None


class ParseDemoResponse(BaseModel):
    """Ответ на парсинг"""
    success: bool
    data: Optional[ParsedContent] = None
    error: Optional[str] = None


class CompetitorParseResult(ParseDemoResponse):
    """Результат парсинга одного конкурента из config"""
    url: str


class ParseCompetitorsResponse(BaseModel):
    """Ответ на парсинг всех конкурентов из config"""
    niche: str
    total: int
    succeeded: int
    results: List[CompetitorParseResult]


# === История ===

class HistoryItem(BaseModel):
    """Элемент истории"""
    id: str
    timestamp: datetime
    request_type: str  # "text", "image", "parse"
    request_summary: str
    response_summary: str


class HistoryResponse(BaseModel):
    """Ответ со списком истории"""
    items: List[HistoryItem]
    total: int

