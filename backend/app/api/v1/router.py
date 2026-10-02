from fastapi import APIRouter

from app.api.v1 import audit, auth, documents, farmers, farms, health, notifications, organizations, roles, users

api_router = APIRouter()
for module in (health, auth, users, roles, organizations, audit, farmers, farms, documents, notifications):
    api_router.include_router(module.router)
