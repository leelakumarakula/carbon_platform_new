from fastapi import APIRouter

from app.api.v1 import audit, auth, health, organizations, roles, users

api_router = APIRouter()
for module in (health, auth, users, roles, organizations, audit):
    api_router.include_router(module.router)
