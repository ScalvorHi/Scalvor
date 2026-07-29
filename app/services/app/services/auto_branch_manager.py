"""
Менеджер автоматического создания и заполнения веток.
При запуске сканирования данные сами распределяются по нужным веткам.
"""
import uuid
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.branch import Branch, BranchNote
from app.models.project import Project
from app.services.data_classifier import DataClassifier, ClassifiedData
import logging

logger = logging.getLogger("auto-branch")


class AutoBranchManager:
    """
    Автоматически создаёт ветки и распределяет данные.
    Работает по принципу:
    1. Получил данные сканирования
    2. Классифицировал
    3. Нашёл подходящую ветку или создал новую
    4. Сохранил данные в ветку
    """

    def __init__(self, db: AsyncSession, project_id: uuid.UUID):
        self.db = db
        self.project_id = project_id
        self.classifier = DataClassifier()

    async def process_scan_results(
        self,
        scan_type: str,
        target: str,
        raw_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Обрабатывает результаты сканирования.
        Автоматически раскидывает данные по веткам.
        """
        report = {
            "new_branches": [],
            "updated_branches": [],
            "total_items": 0,
            "by_branch": {},
        }

        # Извлекаем весь текст из результатов
        all_text = self._extract_text(raw_results)

        # Классифицируем данные
        classified = self.classifier.classify(all_text, source=scan_type)

        # Группируем по предлагаемым веткам
        groups = self.classifier.group_by_branch(classified)

        for branch_name, items in groups.items():
            branch = await self._get_or_create_branch(branch_name)
            await self._save_items_to_branch(branch, items, scan_type, target)

            report["by_branch"][branch_name] = len(items)
            report["total_items"] += len(items)

            if branch not in report["updated_branches"]:
                report["updated_branches"].append({
                    "id": str(branch.id),
                    "name": branch.name,
                    "items_count": len(items),
                })

        return report

    def _extract_text(self, data: Any, depth: int = 0) -> str:
        if depth > 10:
            return ""
        if isinstance(data, str):
            return data + " "
        if isinstance(data, dict):
            return "".join(self._extract_text(v, depth + 1) for v in data.values())
        if isinstance(data, list):
            return "".join(self._extract_text(item, depth + 1) for item in data)
        return str(data) + " " if data else ""

    async def _get_or_create_branch(self, name: str) -> Branch:
        result = await self.db.execute(
            select(Branch).where(
                Branch.project_id == self.project_id,
                Branch.name == name,
                Branch.is_archived == False,
            )
        )
        branch = result.scalar_one_or_none()

        if not branch:
            branch = Branch(
                project_id=self.project_id,
                name=name,
                description=f"Автоматически создана для {name}",
                color=self._get_branch_color(name),
            )
            self.db.add(branch)
            await self.db.flush()
            await self.db.refresh(branch)
            logger.info(f"Создана новая ветка: {name}")

        return branch

    async def _save_items_to_branch(
        self,
        branch: Branch,
        items: List[ClassifiedData],
        scan_type: str,
        target: str,
    ):
        for item in items:
            note = BranchNote(
                branch_id=branch.id,
                title=f"{item.category.value}: {item.value[:100]}",
                content=f"**Тип:** {item.category.value}\n"
                        f"**Значение:** {item.value}\n"
                        f"**Источник:** {scan_type}\n"
                        f"**Цель:** {target}\n"
                        f"**Уверенность:** {item.confidence:.0%}",
                note_type="text",
                attachments={
                    "category": item.category.value,
                    "source": scan_type,
                    "target": target,
                    "confidence": item.confidence,
                },
            )
            self.db.add(note)

    def _get_branch_color(self, name: str) -> str:
        colors = {
            "Контакты и email": "#ff69b4",
            "Социальные сети": "#ff1493",
            "Домены и DNS": "#db7093",
            "IP и инфраструктура": "#ffb6c1",
            "WHOIS и регистрация": "#ffc0cb",
            "SSL и сертификаты": "#ffe4e1",
            "Утечки и пароли": "#ff6eb4",
            "Уязвимости": "#ff3e96",
            "Документы и файлы": "#ff82ab",
            "Метаданные": "#ffaeb9",
            "Геолокация": "#ff8da1",
            "URL и ссылки": "#ffb3b8",
            "Общее": "#ffd1dc",
        }
        return colors.get(name, "#ffd1dc")
