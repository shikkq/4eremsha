import requests
import re
import json
import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from urllib.parse import quote
from dotenv import load_dotenv
from yargy import Parser, rule, or_
from yargy.interpretation import fact
from yargy.predicates import gram, dictionary, normalized
from yargy.tokenizer import Tokenizer, MorphTokenizer
from pymorphy3 import MorphAnalyzer
from database import add_shelter

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# Конфигурация
VK_TOKEN = os.getenv("VK_TOKEN")
VK_KEYWORDS = os.getenv(
    "VK_KEYWORDS", 
    "приют,волонт,животн,кошк,собак,хвост,помощь,нужн,срочно,помогите,поддержка"
).split(",")
VK_API_VERSION = "5.199"
CACHE_FILE = "parsed_groups.json"
REQUEST_TIMEOUT = 10
MAX_POST_AGE_DAYS = 30

# Инициализация NLP-компонентов
class AddressParser:
    def __init__(self):
        self.morph = MorphAnalyzer()
        self.tokenizer = MorphTokenizer(
            rules=Tokenizer.DEFAULT_RULES,  # Исправлено здесь
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

# Остальная часть кода остается без изменений
# ...
