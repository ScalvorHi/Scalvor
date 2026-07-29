"""
Фоновые задачи сканирования с автоматическим распределением по веткам.
"""
import uuid
from datetime import datetime, timezone
from celery import Task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.core.celery_app import celery_app
from app.core.config import settings
from app.models.scan import Scan, ScanStatus, ScanEvent
from app.services.auto_branch_manager import AutoBranchManager
import logging

logger = logging.getLogger("scan-tasks")

# Асинхронный движок для Celery-воркеров
engine = create_async_engine(settings.DATABASE_URL)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class ScanTask(Task):
    """Базовый класс задачи сканирования с авто-распределением."""
    abstract = True
    _auto_branch = None

    async def get_db(self):
        async with async_session() as session:
            yield session

    async def update_scan_status(self, scan_id: uuid.UUID, status: ScanStatus, **kwargs):
        async with async_session() as db:
            scan = await db.get(Scan, scan_id)
            if scan:
                scan.status = status
                for key, value in kwargs.items():
                    setattr(scan, key, value)
                await db.commit()

    async def add_event(self, scan_id: uuid.UUID, event_type: str, message: str, data: dict = None):
        async with async_session() as db:
            event = ScanEvent(
                scan_id=scan_id,
                event_type=event_type,
                message=message,
                data=data or {},
            )
            db.add(event)
            await db.commit()

    async def process_with_auto_branch(
        self,
        scan_id: uuid.UUID,
        scan_type: str,
        target: str,
        results: dict,
    ):
        """Распределяет результаты по веткам автоматически."""
        async with async_session() as db:
            scan = await db.get(Scan, scan_id)
            if not scan or not scan.branch_id:
                return

            manager = AutoBranchManager(db, scan.project_id)
            report = await manager.process_scan_results(
                scan_type=scan_type,
                target=target,
                raw_results=results,
            )

            await self.add_event(
                scan_id,
                "auto_branch",
                f"Данные распределены по {len(report['updated_branches'])} веткам",
                report,
            )


@celery_app.task(bind=True, base=ScanTask)
async def run_full_scan(self, scan_id: str):
    """Полное сканирование — все инструменты + авто-распределение."""
    scan_uuid = uuid.UUID(scan_id)

    async with async_session() as db:
        scan = await db.get(Scan, scan_uuid)
        if not scan:
            return {"error": "Скан не найден"}

        scan.status = ScanStatus.RUNNING
        scan.started_at = datetime.now(timezone.utc)
        await db.commit()

    all_results = {}

    # 1. DNS-разведка
    try:
        from app.services.dns_service import DNSService
        dns = DNSService()
        dns_results = await dns.full_enumeration(scan.target)
        all_results["dns"] = dns_results
        await self.add_event(scan_uuid, "dns_complete", "DNS-разведка завершена")
    except Exception as e:
        logger.error(f"DNS error: {e}")
        all_results["dns"] = {"error": str(e)}

    # 2. WHOIS
    try:
        from app.services.whois_service import WhoisService
        whois_svc = WhoisService()
        whois_results = await whois_svc.lookup(scan.target)
        all_results["whois"] = whois_results
        await self.add_event(scan_uuid, "whois_complete", "WHOIS завершён")
    except Exception as e:
        logger.error(f"WHOIS error: {e}")
        all_results["whois"] = {"error": str(e)}

    # 3. Email-охота
    try:
        from app.services.email_service import EmailService
        email_svc = EmailService()
        email_results = await email_svc.hunt_by_domain(scan.target)
        all_results["emails"] = email_results
        await self.add_event(scan_uuid, "email_complete", "Поиск email завершён")
    except Exception as e:
        logger.error(f"Email error: {e}")
        all_results["emails"] = {"error": str(e)}

    # 4. Shodan
    try:
        from app.services.shodan_service import ShodanService
        shodan_svc = ShodanService()
        shodan_results = await shodan_svc.search(scan.target)
        all_results["shodan"] = shodan_results
        await self.add_event(scan_uuid, "shodan_complete", "Shodan завершён")
    except Exception as e:
        logger.error(f"Shodan error: {e}")
        all_results["shodan"] = {"error": str(e)}

    # 5. Wayback Machine
    try:
        from app.services.wayback_service import WaybackService
        wayback_svc = WaybackService()
        wayback_results = await wayback_svc.get_history(scan.target)
        all_results["wayback"] = wayback_results
        await self.add_event(scan_uuid, "wayback_complete", "Wayback Machine завершён")
    except Exception as e:
        logger.error(f"Wayback error: {e}")
        all_results["wayback"] = {"error": str(e)}

    # Автоматическое распределение по веткам
    await self.process_with_auto_branch(
        scan_uuid,
        "full_scan",
        scan.target,
        all_results,
    )

    # Сохраняем результаты
    async with async_session() as db:
        scan = await db.get(Scan, scan_uuid)
        if scan:
            scan.status = ScanStatus.COMPLETED
            scan.results = all_results
            scan.completed_at = datetime.now(timezone.utc)
            await db.commit()

    return {"status": "completed", "scan_id": scan_id, "tools_used": list(all_results.keys())}


@celery_app.task(bind=True, base=ScanTask)
async def run_dorking_scan(self, scan_id: str):
    """Google Dorking с авто-распределением."""
    scan_uuid = uuid.UUID(scan_id)
    async with async_session() as db:
        scan = await db.get(Scan, scan_uuid)
        if not scan:
            return {"error": "Скан не найден"}
        scan.status = ScanStatus.RUNNING
        scan.started_at = datetime.now(timezone.utc)
        await db.commit()

    try:
        from app.services.dorking_service import DorkingService
        dorking = DorkingService()
        dork_query = scan.parameters.get("query", scan.target)
        results = await dorking.execute_dork(dork_query, max_results=500)

        await self.process_with_auto_branch(scan_uuid, "dorking", scan.target, results)

        async with async_session() as db:
            scan = await db.get(Scan, scan_uuid)
            scan.status = ScanStatus.COMPLETED
            scan.results = results
            scan.completed_at = datetime.now(timezone.utc)
            await db.commit()

    except Exception as e:
        logger.error(f"Dorking error: {e}")
        async with async_session() as db:
            scan = await db.get(Scan, scan_uuid)
            scan.status = ScanStatus.FAILED
            scan.error_message = str(e)
            await db.commit()

    return {"status": "completed", "scan_id": scan_id}
