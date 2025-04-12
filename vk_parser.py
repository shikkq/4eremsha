import requests
import re
import json
import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from urllib.parse import quote
from dotenv import load_dotenv
from database import add_shelter

from yargy.tokenizer import Tokenizer, MorphTokenizer
from yargy import Parser, rule, or_
from yargy.interpretation import fact
from yargy.predicates import gram, dictionary, normalized
from pymorphy3 import MorphAnalyzer

class AddressParser:
    def __init__(self):
        self.morph = MorphAnalyzer()
        
        # Инициализация токенизатора с дефолтными настройками
        base_tokenizer = Tokenizer()
        self.tokenizer = MorphTokenizer(
            splitter=base_tokenizer.splitter,
            morph=self.morph
        )
        
        self._init_parser()

    def _init_parser(self):
        Address = fact('Address', ['city', 'street', 'building'])

        CITY = or_(
            gram('Geox'),
            dictionary({'город', 'г'}).interpretation(Address.city)
        )

        STREET = or_(
            gram('Abbr'),
            dictionary({'улица', 'ул', 'проспект', 'пр', 'шоссе', 'ш'})
        ).interpretation(Address.street)

        BUILDING = or_(
            gram('NUMR'),
            rule(normalized('д'), gram('Abbr')),
            rule(normalized('дом'), gram('NOUN'))
        ).interpretation(Address.building)

        self.parser = Parser(
            rule(CITY, STREET, BUILDING),
            tokenizer=self.tokenizer
        )

    def extract(self, text: str) -> List[str]:
        addresses = []
        for match in self.parser.findall(text):
            parts = [
                token.value 
                for token in match.tokens 
                if token.value.lower() not in {'г', 'город', 'ул', 'улица', 'д', 'дом'}
            ]
            if parts:
                addresses.append(', '.join(parts))
        return addresses

address_parser = AddressParser()

# Кэширование
class GroupCache:
    def __init__(self, filename: str = CACHE_FILE):
        self.filename = filename
        self.groups = set()
        self.load()

    def load(self):
        try:
            if os.path.exists(self.filename):
                with open(self.filename, 'r', encoding='utf-8') as f:
                    self.groups = set(json.load(f))
        except Exception as e:
            logger.error(f"Error loading cache: {e}")

    def save(self):
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(list(self.groups), f)
        except Exception as e:
            logger.error(f"Error saving cache: {e}")

    def add(self, group_id: str):
        self.groups.add(group_id)
        self.save()

cache = GroupCache()

# VK API клиент
class VKClient:
    def __init__(self, token: str, version: str = VK_API_VERSION):
        self.token = token
        self.version = version
        self.session = requests.Session()

    def _request(self, method: str, **params) -> Dict:
        try:
            response = self.session.get(
                f"https://api.vk.com/method/{method}",
                params={
                    **params,
                    "access_token": self.token,
                    "v": self.version
                },
                timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"VK API error: {e}")
            return {}

    def search_groups(self, query: str) -> List[Dict]:
        result = self._request(
            "groups.search",
            q=query,
            type="group",
            count=100
        )
        return result.get('response', {}).get('items', [])

    def get_group_posts(self, group_id: str) -> List[Dict]:
        cutoff = int((datetime.now() - timedelta(days=MAX_POST_AGE_DAYS)).timestamp())
        result = self._request(
            "wall.get",
            owner_id=f"-{group_id}",
            count=50,
            filter="owner"
        )
        return [
            post for post in result.get('response', {}).get('items', [])
            if post.get('date', 0) > cutoff
        ]

vk_client = VKClient(VK_TOKEN)

# Обработка данных
class PostProcessor:
    @staticmethod
    def normalize_contacts(text: str) -> List[str]:
        contacts = {
            'phones': set(),
            'social': set(),
            'links': set()
        }

        # Телефоны
        phones = re.findall(r"(?:\+7|8)\d{10}", text)
        contacts['phones'].update(phones)

        # Социальные сети
        social = re.findall(r"(?:@|t\.me/)\w+", text, re.IGNORECASE)
        contacts['social'].update(social)

        # Ссылки
        links = re.findall(r"https?://\S+", text)
        contacts['links'].update(links)

        result = []
        if contacts['phones']:
            result.append("📱 Телефоны: " + ", ".join(sorted(contacts['phones'])))
        if contacts['social']:
            result.append("👤 Соцсети: " + ", ".join(sorted(contacts['social'])))
        if contacts['links']:
            result.append("🔗 Ссылки: " + ", ".join(sorted(contacts['links'])))

        return result or ["❌ Контакты не найдены"]

    @staticmethod
    def calculate_post_score(post: Dict, city: str) -> int:
        text = post.get('text', '').lower()
        score = 0

        # Ключевые слова
        score += sum(1 for kw in VK_KEYWORDS if kw in text) * 2

        # Контакты
        has_contacts = any([
            'phone' in text,
            '@' in text,
            'http' in text
        ])
        score += 5 if has_contacts else 0

        # Адрес
        score += 3 if address_parser.extract(text) else 0

        # Актуальность
        days_old = (datetime.now() - datetime.fromtimestamp(post.get('date', 0))).days
        score += max(0, 10 - days_old)

        # Город
        if city and city.lower() in text.lower():
            score += 5

        return score

def search_vk_groups(city: str) -> List[Dict]:
    try:
        logger.info(f"Starting search for city: {city}")
        
        # Поиск групп
        groups = vk_client.search_groups(f"приют {city}")
        if not groups:
            return []

        # Фильтрация новых групп
        new_groups = [g for g in groups if str(g['id']) not in cache.groups]
        
        # Сбор постов
        results = []
        for group in new_groups[:10]:  # Ограничение для теста
            group_id = group['id']
            posts = vk_client.get_group_posts(group_id)
            if posts:
                cache.add(str(group_id))
                results.extend(posts)
        
        return results

    except Exception as e:
        logger.error(f"Search error: {e}")
        return []

def process_posts(posts: List[Dict], city: str) -> List[Dict]:
    processed = []
    for post in posts:
        text = post.get('text', '')
        if not text:
            continue

        # Извлечение информации
        address = address_parser.extract(text)
        contacts = PostProcessor.normalize_contacts(text)
        score = PostProcessor.calculate_post_score(post, city)

        processed.append({
            'id': post['id'],
            'text': text[:500] + '...' if len(text) > 500 else text,
            'date': datetime.fromtimestamp(post['date']).strftime("%Y-%m-%d"),
            'score': score,
            'contacts': contacts,
            'address': address,
            'link': f"https://vk.com/wall-{post['owner_id']}_{post['id']}"
        })

    return sorted(processed, key=lambda x: x['score'], reverse=True)[:20]

def format_post_info(post: Dict) -> str:
    lines = [
        f"📅 {post['date']} | ⭐ Рейтинг: {post['score']}",
        f"📍 Адрес: {post['address'][0]}" if post['address'] else "📍 Адрес не указан",
        "\n".join(post['contacts']),
        f"🔗 {post['link']}",
        "\n📝 Описание:",
        post['text']
    ]
    return "\n".join(lines)
