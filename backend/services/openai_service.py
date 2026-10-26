"""
Сервис для работы с OpenAI API (или ProxyAPI — OpenAI-совместимый)
https://proxyapi.ru/docs/openai-text-generation
Промпты адаптированы под нишу «производство спортивной одежды»
"""
import base64
import json
import re
import time
import logging
from typing import Optional

from openai import OpenAI

from backend.config import settings
from backend.models.schemas import CompetitorAnalysis, ImageAnalysis

# Логгер для сервиса
logger = logging.getLogger("competitor_monitor.openai")

# Общий контекст ниши для всех промптов
NICHE_CONTEXT = f"""Ниша: {settings.niche}. Мы — производитель спортивной одежды и анализируем конкурентов.
Учитывай специфику ниши:
- технологичность тканей и материалов (влагоотведение, компрессия, бесшовность, переработанные волокна)
- как показан продукт: фото/видео в движении, крупные планы ткани, посадка на разных фигурах
- коллаборации со спортсменами и амбассадорами, комьюнити, спортивные события
- размерная сетка, инклюзивность, женские/мужские/детские линейки
- устойчивое производство (sustainability), страна производства
- цена и ценовой сегмент, акции, программа лояльности"""

# Описание числовых оценок, которые добавлены под нишу
SCORES_GUIDE = """Оценки (целые числа 0-10):
- design_score — качество визуального стиля бренда: цвет, типографика, композиция, фото продукта
- animation_potential — насколько бренд использует (или мог бы использовать) анимацию и моушн-контент:
  видео-обложки, анимированные карточки товара, 3D-ткань, Reels/Shorts. 10 = анимация — ключевая часть коммуникации"""


def _score(value, default: int = 5) -> int:
    """Привести оценку модели к целому 0-10"""
    try:
        return max(0, min(10, int(round(float(value)))))
    except (TypeError, ValueError):
        return default


def _build_competitor_analysis(data: dict) -> CompetitorAnalysis:
    """Собрать CompetitorAnalysis из JSON ответа модели"""
    return CompetitorAnalysis(
        strengths=data.get("strengths", []),
        weaknesses=data.get("weaknesses", []),
        unique_offers=data.get("unique_offers", []),
        recommendations=data.get("recommendations", []),
        summary=data.get("summary", ""),
        design_score=_score(data.get("design_score")),
        animation_potential=_score(data.get("animation_potential")),
        brand_positioning=data.get("brand_positioning", ""),
        target_audience=data.get("target_audience", ""),
        price_segment=data.get("price_segment", "")
    )


class OpenAIService:
    """Сервис для анализа через OpenAI или ProxyAPI"""

    def __init__(self):
        logger.info("=" * 50)
        logger.info("Инициализация OpenAI сервиса")
        logger.info(f"  Провайдер: {settings.api_provider}")
        logger.info(f"  Base URL: {settings.api_base_url}")
        logger.info(f"  Модель текста: {settings.openai_model}")
        logger.info(f"  Модель vision: {settings.openai_vision_model}")
        logger.info(f"  API ключ: {'*' * 10}...{settings.api_key[-4:] if settings.api_key else 'НЕ ЗАДАН'}")

        # OpenAI напрямую или ProxyAPI - в зависимости от ключа в .env
        self.client = OpenAI(
            api_key=settings.api_key or "not-set",
            base_url=settings.api_base_url
        )
        self.model = settings.openai_model
        self.vision_model = settings.openai_vision_model
        
        logger.info("OpenAI сервис инициализирован успешно ✓")
        logger.info("=" * 50)
    
    def _parse_json_response(self, content: str) -> dict:
        """Извлечь JSON из ответа модели"""
        logger.debug(f"Парсинг JSON ответа, длина: {len(content)} символов")
        
        # Пробуем найти JSON в markdown блоке
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
        if json_match:
            content = json_match.group(1)
            logger.debug("JSON найден в markdown блоке")
        
        # Пробуем найти JSON объект
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            content = json_match.group(0)
            logger.debug("JSON объект извлечён")
        
        try:
            result = json.loads(content)
            logger.debug(f"JSON успешно распарсен, ключей: {len(result)}")
            return result
        except json.JSONDecodeError as e:
            logger.warning(f"Ошибка парсинга JSON: {e}")
            logger.debug(f"Проблемный контент: {content[:200]}...")
            return {}
    
    async def analyze_text(self, text: str) -> CompetitorAnalysis:
        """Анализ текста конкурента"""
        logger.info("=" * 50)
        logger.info("📝 АНАЛИЗ ТЕКСТА КОНКУРЕНТА")
        logger.info(f"  Длина текста: {len(text)} символов")
        logger.info(f"  Превью: {text[:100]}...")
        logger.info(f"  Модель: {self.model}")
        
        system_prompt = f"""Ты — эксперт по конкурентному анализу брендов спортивной одежды. Проанализируй предоставленный текст конкурента (описание бренда, УТП, тексты с сайта, отчёт) и верни структурированный JSON-ответ.

{NICHE_CONTEXT}

Формат ответа (строго JSON):
{{
    "strengths": ["сильная сторона 1", "сильная сторона 2", ...],
    "weaknesses": ["слабая сторона 1", "слабая сторона 2", ...],
    "unique_offers": ["уникальное предложение 1", "уникальное предложение 2", ...],
    "recommendations": ["рекомендация для нашего производства 1", ...],
    "summary": "Краткое резюме анализа",
    "design_score": 7,
    "animation_potential": 6,
    "brand_positioning": "перфоманс / лайфстайл / премиум / масс-маркет + пояснение",
    "target_audience": "Кто покупатель: пол, возраст, вид спорта, уровень подготовки",
    "price_segment": "эконом / средний / премиум + пояснение"
}}

{SCORES_GUIDE}
Если по тексту визуал оценить нельзя — оцени по тому, как бренд описывает свою визуальную коммуникацию.

Важно:
- Каждый массив должен содержать 3-5 пунктов
- Пиши на русском языке
- Будь конкретен и практичен в рекомендациях"""

        start_time = time.time()
        logger.info("  Отправка запроса к API...")
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Проанализируй текст конкурента:\n\n{text}"}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            elapsed = time.time() - start_time
            logger.info(f"  ✓ Ответ получен за {elapsed:.2f} сек")
            
            content = response.choices[0].message.content
            logger.info(f"  Длина ответа: {len(content)} символов")
            logger.debug(f"  Использовано токенов: {response.usage.total_tokens if response.usage else 'N/A'}")
            
            data = self._parse_json_response(content)

            result = _build_competitor_analysis(data)

            logger.info(f"  Результат: {len(result.strengths)} сильных, {len(result.weaknesses)} слабых сторон")
            logger.info(f"  Дизайн: {result.design_score}/10, анимация: {result.animation_potential}/10")
            logger.info("=" * 50)
            
            return result
            
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"  ✗ Ошибка API за {elapsed:.2f} сек: {e}")
            logger.error("=" * 50)
            raise
    
    async def analyze_image(self, image_base64: str, mime_type: str = "image/jpeg") -> ImageAnalysis:
        """Анализ изображения (баннер, сайт, упаковка)"""
        logger.info("=" * 50)
        logger.info("🖼️ АНАЛИЗ ИЗОБРАЖЕНИЯ")
        logger.info(f"  Размер base64: {len(image_base64)} символов")
        logger.info(f"  MIME тип: {mime_type}")
        logger.info(f"  Модель: {self.vision_model}")
        
        system_prompt = f"""Ты — эксперт по визуальному маркетингу, дизайну и моушн-дизайну в индустрии спортивной одежды. Проанализируй изображение конкурента (лендинг, баннер, карточка товара, лукбук, упаковка) и верни структурированный JSON-ответ.

{NICHE_CONTEXT}

Формат ответа (строго JSON):
{{
    "description": "Детальное описание того, что изображено",
    "marketing_insights": ["инсайт 1", "инсайт 2", ...],
    "visual_style_score": 7,
    "visual_style_analysis": "Анализ визуального стиля конкурента",
    "recommendations": ["рекомендация 1", "рекомендация 2", ...],
    "design_score": 7,
    "animation_potential": 6,
    "animation_ideas": ["как оживить этот визуал анимацией 1", ...],
    "product_presentation": "Как показан продукт: ткань, посадка, движение, модели"
}}

{SCORES_GUIDE}

Важно:
- visual_style_score от 0 до 10 (общее впечатление), design_score — именно дизайн
- Каждый массив должен содержать 3-5 пунктов
- Пиши на русском языке
- Оценивай: цветовую палитру, типографику, композицию, UX/UI элементы, подачу продукта"""

        start_time = time.time()
        logger.info("  Отправка запроса к Vision API...")
        
        try:
            response = self.client.chat.completions.create(
                model=self.vision_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Проанализируй это изображение конкурента с точки зрения маркетинга и дизайна:"
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{image_base64}"
                                }
                            }
                        ]
                    }
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            elapsed = time.time() - start_time
            logger.info(f"  ✓ Ответ получен за {elapsed:.2f} сек")
            
            content = response.choices[0].message.content
            logger.info(f"  Длина ответа: {len(content)} символов")
            
            data = self._parse_json_response(content)
            
            result = ImageAnalysis(
                description=data.get("description", ""),
                marketing_insights=data.get("marketing_insights", []),
                visual_style_score=_score(data.get("visual_style_score")),
                visual_style_analysis=data.get("visual_style_analysis", ""),
                recommendations=data.get("recommendations", []),
                design_score=_score(data.get("design_score")),
                animation_potential=_score(data.get("animation_potential")),
                animation_ideas=data.get("animation_ideas", []),
                product_presentation=data.get("product_presentation", "")
            )

            logger.info(f"  Результат: оценка стиля {result.visual_style_score}/10")
            logger.info(f"  Дизайн: {result.design_score}/10, анимация: {result.animation_potential}/10")
            logger.info(f"  Инсайтов: {len(result.marketing_insights)}, рекомендаций: {len(result.recommendations)}")
            logger.info("=" * 50)
            
            return result
            
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"  ✗ Ошибка Vision API за {elapsed:.2f} сек: {e}")
            logger.error("=" * 50)
            raise
    
    async def analyze_parsed_content(
        self, 
        title: Optional[str], 
        h1: Optional[str], 
        paragraph: Optional[str]
    ) -> CompetitorAnalysis:
        """Анализ распарсенного контента сайта"""
        logger.info("📄 Анализ распарсенного контента")
        logger.info(f"  Title: {title[:50] if title else 'N/A'}...")
        logger.info(f"  H1: {h1[:50] if h1 else 'N/A'}...")
        logger.info(f"  Абзац: {paragraph[:50] if paragraph else 'N/A'}...")
        
        content_parts = []
        if title:
            content_parts.append(f"Заголовок страницы (title): {title}")
        if h1:
            content_parts.append(f"Главный заголовок (H1): {h1}")
        if paragraph:
            content_parts.append(f"Первый абзац: {paragraph}")
        
        combined_text = "\n\n".join(content_parts)
        
        if not combined_text.strip():
            logger.warning("  ⚠ Контент пустой, возвращаем пустой анализ")
            return CompetitorAnalysis(
                summary="Не удалось извлечь контент для анализа"
            )
        
        return await self.analyze_text(combined_text)
    
    async def analyze_website_screenshot(
        self,
        screenshot_base64: str,
        url: str,
        title: Optional[str] = None,
        h1: Optional[str] = None,
        first_paragraph: Optional[str] = None
    ) -> CompetitorAnalysis:
        """Комплексный анализ сайта конкурента по скриншоту"""
        logger.info("=" * 50)
        logger.info("🌐 КОМПЛЕКСНЫЙ АНАЛИЗ САЙТА")
        logger.info(f"  URL: {url}")
        logger.info(f"  Title: {title[:50] if title else 'N/A'}...")
        logger.info(f"  H1: {h1[:50] if h1 else 'N/A'}...")
        logger.info(f"  Размер скриншота: {len(screenshot_base64)} символов base64")
        logger.info(f"  Модель: {self.vision_model}")
        
        # Формируем контекст из извлечённых данных
        context_parts = [f"URL сайта: {url}"]
        if title:
            context_parts.append(f"Title страницы: {title}")
        if h1:
            context_parts.append(f"Главный заголовок (H1): {h1}")
        if first_paragraph:
            context_parts.append(f"Текст на странице: {first_paragraph[:300]}")
        
        context = "\n".join(context_parts)
        logger.debug(f"  Контекст:\n{context}")
        
        system_prompt = f"""Ты — эксперт по конкурентному анализу и UX/UI дизайну в индустрии спортивной одежды. Проанализируй скриншот сайта конкурента и верни структурированный JSON-ответ.

{NICHE_CONTEXT}

Формат ответа (строго JSON):
{{
    "strengths": ["сильная сторона 1", "сильная сторона 2", ...],
    "weaknesses": ["слабая сторона 1", "слабая сторона 2", ...],
    "unique_offers": ["уникальное предложение/фича 1", "уникальное предложение/фича 2", ...],
    "recommendations": ["рекомендация для нашего производства 1", ...],
    "summary": "Комплексное резюме анализа сайта конкурента",
    "design_score": 7,
    "animation_potential": 6,
    "brand_positioning": "перфоманс / лайфстайл / премиум / масс-маркет + пояснение",
    "target_audience": "Кто покупатель: пол, возраст, вид спорта",
    "price_segment": "эконом / средний / премиум + пояснение"
}}

{SCORES_GUIDE}

При анализе обращай внимание на:
- Дизайн и визуальный стиль (цвета, шрифты, композиция)
- UX/UI: навигация, расположение элементов, CTA кнопки
- Контент: заголовки, тексты, призывы к действию
- Уникальные торговые предложения (УТП)
- Целевая аудитория (на кого ориентирован сайт)
- Технологичность и современность дизайна

Важно:
- Каждый массив должен содержать 4-6 конкретных пунктов
- Пиши на русском языке
- Будь конкретен и практичен
- Давай actionable рекомендации"""

        start_time = time.time()
        logger.info("  Отправка скриншота в Vision API...")
        
        try:
            response = self.client.chat.completions.create(
                model=self.vision_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"Проведи комплексный конкурентный анализ этого сайта:\n\n{context}"
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{screenshot_base64}"
                                }
                            }
                        ]
                    }
                ],
                temperature=0.7,
                max_tokens=3000
            )
            
            elapsed = time.time() - start_time
            logger.info(f"  ✓ Ответ получен за {elapsed:.2f} сек")
            
            content = response.choices[0].message.content
            logger.info(f"  Длина ответа: {len(content)} символов")
            
            data = self._parse_json_response(content)

            result = _build_competitor_analysis(data)

            logger.info(f"  Результат:")
            logger.info(f"    - Дизайн: {result.design_score}/10, анимация: {result.animation_potential}/10")
            logger.info(f"    - Сильных сторон: {len(result.strengths)}")
            logger.info(f"    - Слабых сторон: {len(result.weaknesses)}")
            logger.info(f"    - УТП: {len(result.unique_offers)}")
            logger.info(f"    - Рекомендаций: {len(result.recommendations)}")
            logger.info(f"  Резюме: {result.summary[:100]}...")
            logger.info("=" * 50)
            
            return result
            
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"  ✗ Ошибка Vision API за {elapsed:.2f} сек: {e}")
            logger.error("=" * 50)
            raise


# Глобальный экземпляр
logger.info("Создание глобального экземпляра OpenAI сервиса...")
openai_service = OpenAIService()
