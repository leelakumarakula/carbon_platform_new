from fastapi import APIRouter

from app.api.v1 import (
    audit,
    auth,
    client_config,
    consents,
    documents,
    farmers,
    farms,
    health,
    notifications,
    organizations,
    roles,
    users,
)

api_router = APIRouter()
for module in (health, auth, client_config, users, roles, organizations, audit, consents, farmers, farms, documents, notifications):
    api_router.include_router(module.router)
