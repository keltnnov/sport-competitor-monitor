# 🏃 AI-анализатор конкурентов: производство спортивной одежды

Персональный AI-ассистент для мониторинга рынка спортивной одежды. Анализирует тексты, изображения и сайты конкурентов через OpenAI (GPT-4o-mini, vision). Работает как веб-приложение (FastAPI) и как десктоп-приложение (PyQt6 → `.exe`).

Домашнее задание курса Zerocoder (модуль 4). Основа — код из урока ([Toxap/pem08](https://github.com/Toxap/pem08)), адаптированный под свою нишу.

## 🎯 Кейс

**Ниша:** мы — небольшой производитель спортивной одежды. Нужно понять, как крупные бренды подают продукт, в каком они ценовом сегменте и где у них слабые места, которые можно занять.

**Конкуренты** (список в `backend/config.py` → `competitor_urls`):

| Бренд | Сайт | Почему в выборке |
|---|---|---|
| Gymshark | gymshark.com | D2C-бренд для фитнеса, сильный инфлюенс-маркетинг |
| Under Armour | underarmour.com | Перфоманс и технологии тканей |
| PUMA | eu.puma.com | Спорт + лайфстайл, много моушн-контента |
| ASICS | asics.com | Бег, научный подход |
| Forward | forward-sport.ru | Российский экипировщик сборных |

## ✨ Что изменено относительно урока

### 1. Промпты и модели под нишу (`backend/services/openai_service.py`, `backend/models/schemas.py`)
- Общий контекст ниши во всех промптах: ткани и технологии, подача продукта в движении, амбассадоры, размерная сетка, sustainability, цена.
- Новые поля JSON-ответа:

| Поле | Где | Что значит |
|---|---|---|
| `design_score` | текст, изображение, сайт | Визуальный стиль бренда, 0–10 |
| `animation_potential` | текст, изображение, сайт | Насколько бренд использует или мог бы использовать анимацию и моушн-контент, 0–10 |
| `animation_ideas` | изображение | Как оживить этот визуал анимацией |
| `product_presentation` | изображение | Как показан товар: ткань, посадка, движение |
| `brand_positioning` | текст, сайт | Перфоманс / лайфстайл / премиум / масс-маркет |
| `target_audience` | текст, сайт | Кто покупатель |
| `price_segment` | текст, сайт | Эконом / средний / премиум |

- Оценки модели нормализуются к целому 0–10 (`_score`), поэтому ответ вроде `"8.5"` или `12` не ломает валидацию.

### 2. Парсинг конкурентов через Selenium (`backend/services/parser_service.py`, `backend/main.py`)
- `POST /parse_competitors` по очереди открывает в Chrome все сайты из `config.py`, делает скриншот, анализирует его через vision-модель и сохраняет каждый результат в историю.
- `GET /competitors` возвращает нишу и список URL.
- Перед скриншотом парсер закрывает cookie-баннеры и прокручивает страницу, чтобы подгрузились картинки товаров.
- Скриншоты сохраняются в `data/screenshots/` и подходят для `/analyze_image`.

### 3. Интерфейсы
- В веб-версии и desktop-версии появились шкалы `design_score` и `animation_potential`, новые блоки и кнопка «Проанализировать всех конкурентов» со сводной таблицей.

### 4. Ключ API
- В уроке использовался ProxyAPI. Здесь запросы идут напрямую в OpenAI, ключ `OPENAI_API_KEY` задаётся в `.env` (пример в `env.example.txt`).
- `.env` внесён в `.gitignore`, ключи в репозиторий не попадают.

## 📊 Результаты прогона

Все эндпоинты проверены скриптом `scripts/test_endpoints.py` на gpt-4o-mini: **15 из 15 проверок пройдено**. Полные ответы сохранены в `data/results/`.

Сводка `/parse_competitors` (Selenium-скриншот главной страницы → vision-анализ):

| Конкурент | design_score | animation_potential | Позиционирование (по оценке модели) |
|---|---|---|---|
| Gymshark | 8 | 9 | перфоманс, качество и технологичность |
| Under Armour | 8 | 7 | перфоманс, высокая производительность |
| PUMA | 8 | 5 | премиум: стиль и коллаборации с дизайнерами |
| ASICS | 8 | 7 | перфоманс / лайфстайл |
| Forward | 8 | 7 | перфоманс, экипировка сборных |

По текстам из `data/texts/` выше всех по `animation_potential` оказалась PUMA (9/10), ниже всех — ASICS и Forward (5/10).

Наблюдение: на скриншотах модель ставит почти всем `design_score` 8. Чтобы различать бренды, оценки стоит усреднять по нескольким страницам (главная, каталог, карточка товара) или сравнивать сайты попарно в одном запросе.

## 📁 Структура

```
├── backend/
│   ├── config.py                # настройки, ниша, список конкурентов
│   ├── main.py                  # FastAPI: эндпоинты
│   ├── models/schemas.py        # Pydantic-модели (+ поля ниши)
│   └── services/
│       ├── openai_service.py    # промпты и запросы к OpenAI
│       ├── parser_service.py    # Selenium: скриншот и текст страницы
│       └── history_service.py   # история в history.json
├── frontend/                    # веб-интерфейс (HTML/CSS/JS)
├── desktop/                     # PyQt6-приложение и build.py для .exe
├── data/
│   ├── texts/                   # описания конкурентов для /analyze_text
│   ├── screenshots/             # скриншоты лендингов (собирает парсер)
│   └── results/                 # JSON-ответы прогона всех эндпоинтов
├── scripts/test_endpoints.py    # прогон всех эндпоинтов
├── requirements.txt
├── env.example.txt
└── run.py
```

## 🚀 Запуск

Нужны Python 3.10+ и Google Chrome (для Selenium).

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# скопируйте пример и впишите свой ключ
copy env.example.txt .env

python run.py
```

- Веб-интерфейс: http://localhost:8000
- Swagger (тест эндпоинтов): http://localhost:8000/docs

### Эндпоинты

| Метод | Путь | Что делает |
|---|---|---|
| POST | `/analyze_text` | Анализ текста конкурента (`{"text": "..."}`) |
| POST | `/analyze_image` | Анализ изображения (multipart `file`) |
| POST | `/parse_demo` | Парсинг и анализ одного сайта (`{"url": "..."}`) |
| GET | `/competitors` | Ниша и список конкурентов из config |
| POST | `/parse_competitors` | Парсинг и анализ всех конкурентов, результаты сохраняются в историю |
| GET / DELETE | `/history` | История запросов |
| GET | `/health` | Проверка сервера |

Прогнать все эндпоинты разом на данных из `data/` (при запущенном сервере):

```powershell
python scripts\test_endpoints.py
```

## 🖥️ Desktop-приложение (.exe)

```powershell
pip install -r desktop\requirements.txt pyinstaller
cd desktop
python main.py          # запуск без сборки
python build.py         # сборка → desktop\dist\CompetitionMonitor.exe
```

Перед запуском `.exe` должен работать backend (`python run.py`). Сам `.exe` в репозиторий не загружается.

## 🛠️ Технологии

FastAPI · OpenAI API (GPT-4o-mini + vision) · Selenium + webdriver-manager · Pydantic · PyQt6 · PyInstaller
