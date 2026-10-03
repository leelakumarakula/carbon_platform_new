from fastapi import APIRouter

from app.api.v1 import (
    audit,
    auth,
    calculation_preverification,
    calculations,
    catalog,
    client_config,
    consents,
    credits,
    documents,
    farmers,
    farms,
    health,
    lab,
    laboratory,
    marketplace,
    methodologies,
    mrv,
    notifications,
    orders,
    organizations,
    payments,
    projects,
    registry,
    roles,
    users,
    verification,
    vvb,
)

api_router = APIRouter()
for module in (health, auth, client_config, users, roles, organizations, audit, consents, farmers, farms, catalog, projects,
               methodologies, mrv, lab, laboratory, calculations, calculation_preverification, verification, vvb, registry, credits,
               marketplace, orders, payments, documents, notifications):
    api_router.include_router(module.router)
