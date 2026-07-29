"""
Главный роутер API v1.
Объединяет все модули.
"""
from fastapi import APIRouter
from app.api.v1 import auth, users, projects, scans, branches
from app.api.v1 import dorking, dns_enum, whois_lookup, email_hunting, breach_check

api_v1_router = APIRouter()

api_v1_router.include_router(auth.router, prefix="/auth")
api_v1_router.include_router(users.router, prefix="/users")
api_v1_router.include_router(projects.router, prefix="/projects")
api_v1_router.include_router(branches.router, prefix="/branches")
api_v1_router.include_router(scans.router, prefix="/scans")
api_v1_router.include_router(dorking.router, prefix="/dorking")
api_v1_router.include_router(dns_enum.router, prefix="/dns")
api_v1_router.include_router(whois_lookup.router, prefix="/whois")
api_v1_router.include_router(email_hunting.router, prefix="/email")
api_v1_router.include_router(breach_check.router, prefix="/breach")
