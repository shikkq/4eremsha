import requests
import time
import re
import json
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from database import add_shelter
from natasha import (
    Doc,
    Segmenter,
    NewsEmbedding,
    NewsNERTagger,
    NewsMorphTagger,
    AddrExtractor
)

load_dotenv()

VK_TOKEN = os.getenv("VK_TOKEN")
VK_KEYWORDS = os.getenv("VK_KEYWORDS", "приют,волонт,животн,кошк,собак,хвост,помощь,нужн,срочно,помогите,поддержка").split(",")
VK_API_VERSION = "5.199"
CACHE_FILE = "parsed_groups.json"

segmenter = Segmenter()
emb = NewsEmbedding()
morph_tagger = NewsMorphTagger(emb)
ner_tagger = NewsNERTagger(emb)
addr_extractor = AddrExtractor(morph=morph_tagger)  # ← здесь было упущено

if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        parsed_groups = set(json.load(f))
else:
    parsed_groups = set()

def save_cache():
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(list(parsed_groups), f)

def get_city_id(city_name):
    url = "https://api.vk.com/method/database.getCities"
    params = {
        "access_token": VK_TOKEN,
        "country_id": 1,
        "q": city_name,
        "count": 1,
        "v": VK_API_VERSION
    }
    res = requests.get(url, params=params).json()
    items = res.get("response", {}).get("items", [])
    return items[0]["id"] if items else None

def contains_keywords(text):
    lowered = text.lower()
    return any(kw.lower() in lowered for kw in VK_KEYWORDS)

def contains_city(text, city_name):
    lowered = text.lower()
    city_lower = city_name.lower()
    if f"г. {city_lower}" in lowered:
        return True
    if re.search(rf"\b{re.escape(city_lower)}\b", lowered):
        return True
    return False

def normalize_contacts(contacts):
    phones = set()
    tg = set()
    links = set()

    for contact in contacts:
        contact = contact.strip().lower()
        contact = re.sub(r"\s+", "", contact)

        if re.match(r"^\+?7\d{10}$", contact) or re.match(r"^8\d{10}$", contact):
            phones.add(contact)
        elif contact.startswith("@") or "t.me" in contact:
            tg.add(contact)
        elif contact.startswith("http"):
            links.add(contact)

    result = []
    if phones:
        result.append("Телефоны: " + ", ".join(sorted(phones)))
    if tg:
        result.append("Telegram: " + ", ".join(sorted(tg)))
    if links:
        result.append("Ссылки: " + ", ".join(sorted(links)))

    return result

def extract_address_natasha(text):
    doc = Doc(text)
    doc.segment(segmenter)
    doc.tag_ner(ner_tagger)
    doc.tag_morph(morph_tagger)
    matches = addr_extractor(text)
    return [_.fact.__str__() for _ in matches] if matches else []

def extract_info_from_posts(posts_texts, city_name):
    keyword_found = False
    best_info = None
    best_score = 0

    help_keywords = ["нужны", "нужен", "нужная", "нужное", "помощь", "помогите", "срочно", "сбор", "поддержка"]
    contact_patterns = [
        r"\+7[\d\-\s]{10,15}",
        r"\b8[\d\-\s]{9,15}",
        r"https?://[^\s]+",
        r"@[\w\d_]+",
        r"t\.me/[\w\d_]+"
    ]

    for post in posts_texts:
        text = post.get("text", "")
        lowered = text.lower()

        if not contains_keywords(text):
            continue

        if city_name and not contains_city(text, city_name):
            continue

        keyword_found = True
        score = 0
        contacts = set()
        info_lines = []
        post_date_unix = post.get("date")
        post_date = datetime.fromtimestamp(post_date_unix)
        days_ago = (datetime.now() - post_date).days

        if "(неактивно)" in lowered:
            score -= 2

        if any(kw in lowered for kw in help_keywords):
            score += 3
            info_lines.append(text[:500].strip())

        for pattern in contact_patterns:
            found = re.findall(pattern, text)
            contacts.update(found)
        if contacts:
            score += 2

        addresses = extract_address_natasha(text)
        if addresses:
            score += 2

        if any(kw in lowered for kw in ["приют", "животн", "собак", "кошк", "хвост", "волонт"]):
            score += 1
        if city_name and contains_city(text, city_name):
            score += 1

        if score >= best_score:
            best_score = score
            result = f"\U0001F4C5 Пост опубликован {days_ago} дней назад\n\n"
            if info_lines:
                result += "\U0001F4CC Что нужно:\n" + "\n".join(info_lines[:1]) + "\n"
            if contacts:
                result += "\n\U0001F4DE Контакты:\n" + "\n".join(normalize_contacts(contacts)) + "\n"
            if addresses:
                result += "\n\U0001F4CD Адрес или место:\n" + "\n".join(addresses) + "\n"

            if not contacts or not addresses:
                result += "\n⚠️ Пост может быть неполным — проверьте информацию вручную.\n"

            best_info = result.strip()

    if not keyword_found or best_score < 5:
        return None

    return best_info
