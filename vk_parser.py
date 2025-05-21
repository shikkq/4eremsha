
import requests
import re
import time
import json
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

VK_TOKEN = os.getenv("VK_TOKEN")
VK_KEYWORDS = os.getenv("VK_KEYWORDS", "приют,животные,кошки,собаки,дом,отдаётся,ищет,ласковый,в добрые руки").split(",")
VK_BADWORDS = os.getenv("VK_BADWORDS", "бизнес,магазин,доставка,реклама,бренд,торговля").split(",")
VK_API_VERSION = "5.199"

def get_group_posts(domain):
    url = "https://api.vk.com/method/wall.get"
    params = {
        "access_token": VK_TOKEN,
        "domain": domain,
        "count": 10,
        "filter": "owner",
        "v": VK_API_VERSION
    }
    try:
        res = requests.get(url, params=params).json()
        return res.get("response", {}).get("items", [])
    except Exception as e:
        print(f"[Ошибка] Получение постов: {e}")
        return []

def score_post(text):
    score = 0
    reasons = []

    lower_text = text.lower()

    keyword_matches = [kw for kw in VK_KEYWORDS if kw.strip() in lower_text]
    if keyword_matches:
        points = len(keyword_matches)
        score += points
        reasons.append(f"+{points} ключ. слова: {', '.join(keyword_matches)}")

    # Связки типа "в добрые руки", "ищет дом"
    phrase_patterns = [
        "в добрые руки", "ищет дом", "отда(е|ё)тся", "ищет хозяина", "нуждается в доме"
    ]
    for phrase in phrase_patterns:
        if re.search(rf"\b{phrase}\b", lower_text):
            score += 3
            reasons.append(f"+3 фраза: {phrase}")

    badword_matches = [bw for bw in VK_BADWORDS if bw in lower_text]
    if badword_matches:
        penalty = -2 * len(badword_matches)
        score += penalty
        reasons.append(f"{penalty} плохие слова: {', '.join(badword_matches)}")

    if len(text.strip()) < 50:
        score -= 1
        reasons.append("-1 слишком короткий текст")

    return score, reasons

def analyze_posts(domain):
    print(f"\n📡 Анализ группы: {domain}")
    posts = get_group_posts(domain)
    if not posts:
        print("⚠️ Посты не найдены")
        return

    for i, post in enumerate(posts, 1):
        text = post.get("text", "")
        date = datetime.fromtimestamp(post["date"]).strftime("%d.%m.%Y")
        score, reasons = score_post(text)
        if score >= 3:
            print(f"[✅ {i}] {date} | {score} баллов — ПРОШЁЛ")
        else:
            print(f"[❌ {i}] {date} | {score} баллов — ОТКЛОНЁН")
        print("Причины: " + "; ".join(reasons) + "\n")
