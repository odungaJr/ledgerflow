"""
LedgerFlow — FastAPI application entry point
=============================================
Mounts all routers and applies CORS for local frontend development.

Run with:
  uvicorn app.main:app --reload --port 8000
"""
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.auth import get_current_user
from app.core.database import engine, Base
from app.routers import accounts, auth, categories, transactions, budgets, dashboard, income, assets, reports


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup if they don't exist (dev convenience)
    # In production, rely on Alembic migrations instead
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="LedgerFlow API",
    version="1.0.0",
    description="Personal finance engine with AI-powered categorisation and insights",
    lifespan=lifespan,
)

# Allow the Next.js frontend to call the API — comma-separated origins,
# e.g. CORS_ORIGINS=https://ledgerflow.example.com,http://localhost:3000
_cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_require_auth = [Depends(get_current_user)]

app.include_router(auth.router)
app.include_router(accounts.router, dependencies=_require_auth)
app.include_router(categories.router, dependencies=_require_auth)
app.include_router(transactions.router, dependencies=_require_auth)
app.include_router(budgets.router, dependencies=_require_auth)
app.include_router(income.router, dependencies=_require_auth)
app.include_router(assets.router, dependencies=_require_auth)
app.include_router(dashboard.router, dependencies=_require_auth)
app.include_router(reports.router, dependencies=_require_auth)


@app.get("/", tags=["Health"])
def health():
    return {"status": "LedgerFlow API running", "version": "1.0.0"}
