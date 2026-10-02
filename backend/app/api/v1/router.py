from fastapi import APIRouter

from app.api.v1 import (
    audit,
    auth,
    catalog,
    client_config,
    consents,
    documents,
    farmers,
    farms,
    health,
    methodologies,
    mrv,
    notifications,
    organizations,
    projects,
    roles,
    users,
)

api_router = APIRouter()
for module in (health, auth, client_config, users, roles, organizations, audit, consents, farmers, farms, catalog, projects,
               methodologies, mrv, documents,
               notifications):
    api_router.include_router(module.router)
