"""
Автоматический классификатор данных.
Определяет тип найденной информации и распределяет по нужным веткам.
"""
import re
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum


class DataCategory(str, Enum):
    EMAIL = "email"
    PHONE = "phone"
    DOMAIN = "domain"
    SUBDOMAIN = "subdomain"
    IP_ADDRESS = "ip_address"
    URL = "url"
    PERSON_NAME = "person_name"
    USERNAME = "username"
    PASSWORD_HASH = "password_hash"
    API_KEY = "api_key"
    CREDIT_CARD = "credit_card"
    SOCIAL_MEDIA = "social_media"
    DOCUMENT = "document"
    IMAGE_METADATA = "image_metadata"
    GEO_LOCATION = "geo_location"
    TECHNOLOGY = "technology"
    VULNERABILITY = "vulnerability"
    PORT_SERVICE = "port_service"
    SSL_CERT = "ssl_cert"
    WHOIS_DATA = "whois_data"
    DNS_RECORD = "dns_record"
    LEAKED_DATA = "leaked_data"
    UNKNOWN = "unknown"


@dataclass
class ClassifiedData:
    category: DataCategory
    value: str
    confidence: float
    source: str
    context: Dict[str, Any] = field(default_factory=dict)
    suggested_branch: str = ""


class DataClassifier:
    PATTERNS = {
        DataCategory.EMAIL: [
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        ],
        DataCategory.PHONE: [
            r'\b(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}\b',
            r'\b(?:\+1)?[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{4}\b',
        ],
        DataCategory.IP_ADDRESS: [
            r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b',
        ],
        DataCategory.URL: [
            r'https?://[^\s<>"{}|\\^`\[\]]+',
        ],
        DataCategory.API_KEY: [
            r'(?:api[_-]?key|apikey|token|secret)[\s]*[=:][\s]*["\']?([A-Za-z0-9_\-]{20,})',
            r'sk-[A-Za-z0-9]{32,}',
            r'AIza[0-9A-Za-z\-_]{35}',
        ],
        DataCategory.SOCIAL_MEDIA: [
            r'(?:vk\.com|vkontakte\.ru)/[A-Za-z0-9_.]+',
            r'(?:t\.me|telegram\.me)/[A-Za-z0-9_]+',
            r'(?:instagram\.com)/[A-Za-z0-9_.]+',
            r'(?:twitter\.com|x\.com)/[A-Za-z0-9_]+',
            r'(?:linkedin\.com/in)/[A-Za-z0-9\-]+',
            r'(?:github\.com)/[A-Za-z0-9\-]+',
        ],
        DataCategory.GEO_LOCATION: [
            r'(-?\d{1,2}\.\d{4,})\s*[,;]\s*(-?\d{1,3}\.\d{4,})',
        ],
    }

    BRANCH_RULES = {
        DataCategory.EMAIL: "Контакты и email",
        DataCategory.PHONE: "Контакты и email",
        DataCategory.PERSON_NAME: "Контакты и email",
        DataCategory.USERNAME: "Социальные сети",
        DataCategory.SOCIAL_MEDIA: "Социальные сети",
        DataCategory.DOMAIN: "Домены и DNS",
        DataCategory.SUBDOMAIN: "Домены и DNS",
        DataCategory.DNS_RECORD: "Домены и DNS",
        DataCategory.IP_ADDRESS: "IP и инфраструктура",
        DataCategory.PORT_SERVICE: "IP и инфраструктура",
        DataCategory.TECHNOLOGY: "IP и инфраструктура",
        DataCategory.WHOIS_DATA: "WHOIS и регистрация",
        DataCategory.SSL_CERT: "SSL и сертификаты",
        DataCategory.PASSWORD_HASH: "Утечки и пароли",
        DataCategory.LEAKED_DATA: "Утечки и пароли",
        DataCategory.API_KEY: "Утечки и пароли",
        DataCategory.CREDIT_CARD: "Утечки и пароли",
        DataCategory.VULNERABILITY: "Уязвимости",
        DataCategory.DOCUMENT: "Документы и файлы",
        DataCategory.IMAGE_METADATA: "Метаданные",
        DataCategory.GEO_LOCATION: "Геолокация",
        DataCategory.URL: "URL и ссылки",
    }

    def classify(self, text: str, source: str = "unknown") -> List[ClassifiedData]:
        results = []
        for category, patterns in self.PATTERNS.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    value = match.group(0)
                    branch = self.BRANCH_RULES.get(category, "Общее")
                    results.append(ClassifiedData(
                        category=category,
                        value=value,
                        confidence=0.9,
                        source=source,
                        suggested_branch=branch,
                        context={"match_position": match.start()}
                    ))
        return results

    def suggest_branch_name(self, classified_items: List[ClassifiedData]) -> str:
        if not classified_items:
            return "Общее"
        branch_votes = {}
        for item in classified_items:
            branch = item.suggested_branch
            branch_votes[branch] = branch_votes.get(branch, 0) + 1
        return max(branch_votes, key=branch_votes.get)

    def group_by_branch(self, classified_items: List[ClassifiedData]) -> Dict[str, List[ClassifiedData]]:
        groups = {}
        for item in classified_items:
            branch = item.suggested_branch
            if branch not in groups:
                groups[branch] = []
            groups[branch].append(item)
        return groups
