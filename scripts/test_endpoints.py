"""
Прогон всех эндпоинтов на данных из data/ (сервер должен быть запущен: python run.py).
Ответы сохраняются в data/results/*.json
"""
import json
import sys
import time
from pathlib import Path

import httpx

BASE_URL = "http://127.0.0.1:8000"
DATA = Path(__file__).resolve().parent.parent / "data"
RESULTS = DATA / "results"


def save(name: str, payload: dict):
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"{name}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def check(name: str, ok: bool, details: str = ""):
    print(f"{'✅' if ok else '❌'} {name} {details}")
    return ok


def main() -> int:
    client = httpx.Client(base_url=BASE_URL, timeout=900)
    results = []

    r = client.get("/health").json()
    results.append(check("GET /health", r.get("status") == "healthy"))

    r = client.get("/competitors").json()
    results.append(check("GET /competitors", len(r.get("urls", [])) >= 3, f"({len(r.get('urls', []))} сайтов)"))

    # Анализ текста: все описания конкурентов
    for path in sorted((DATA / "texts").glob("*.txt")):
        start = time.time()
        r = client.post("/analyze_text", json={"text": path.read_text(encoding="utf-8")}).json()
        save(f"text_{path.stem}", r)
        a = r.get("analysis") or {}
        results.append(check(
            f"POST /analyze_text [{path.stem}]",
            r.get("success") and "design_score" in a and "animation_potential" in a,
            f"design={a.get('design_score')} anim={a.get('animation_potential')} "
            f"сегмент={a.get('price_segment', '')[:30]!r} ({time.time() - start:.1f}с) {r.get('error') or ''}"
        ))

    # Анализ изображения: последний скриншот каждого сайта
    shots = {}
    for shot in sorted((DATA / "screenshots").glob("*.png")):
        shots[shot.name.split("_")[0]] = shot
    for domain, shot in shots.items():
        start = time.time()
        with shot.open("rb") as f:
            r = client.post("/analyze_image", files={"file": (shot.name, f, "image/png")}).json()
        save(f"image_{domain}", r)
        a = r.get("analysis") or {}
        results.append(check(
            f"POST /analyze_image [{domain}]",
            r.get("success") and len(a.get("animation_ideas", [])) > 0,
            f"design={a.get('design_score')} anim={a.get('animation_potential')} "
            f"идей анимации={len(a.get('animation_ideas', []))} ({time.time() - start:.1f}с) {r.get('error') or ''}"
        ))

    # Парсинг одного сайта
    start = time.time()
    r = client.post("/parse_demo", json={"url": "https://www.gymshark.com"}).json()
    save("parse_demo_gymshark", r)
    a = ((r.get("data") or {}).get("analysis")) or {}
    results.append(check(
        "POST /parse_demo [gymshark]",
        r.get("success") and a.get("design_score", 0) > 0,
        f"design={a.get('design_score')} ({time.time() - start:.1f}с) {r.get('error') or ''}"
    ))

    # Парсинг всех конкурентов из config.py
    start = time.time()
    r = client.post("/parse_competitors").json()
    save("parse_competitors", r)
    results.append(check(
        "POST /parse_competitors",
        r.get("succeeded") == r.get("total"),
        f"{r.get('succeeded')}/{r.get('total')} ({time.time() - start:.1f}с)"
    ))
    for item in r.get("results", []):
        a = ((item.get("data") or {}).get("analysis")) or {}
        print(f"     {item['url']}: design={a.get('design_score')} anim={a.get('animation_potential')} "
              f"{item.get('error') or ''}")

    r = client.get("/history").json()
    types = [i["request_type"] for i in r.get("items", [])]
    results.append(check("GET /history", types.count("parse") >= 5, f"(записей: {r.get('total')}, parse: {types.count('parse')})"))

    print(f"\nИтого: {sum(results)}/{len(results)} проверок пройдено")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
