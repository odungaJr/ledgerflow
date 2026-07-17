"""
LedgerFlow — FastAPI application entry point
=============================================
Mounts all routers and applies CORS for local frontend development.

Run with:
  uvicorn app.main:app --reload --port 8000
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import engine, Base
from app.routers import accounts, categories, transactions, budgets, dashboard


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

app.include_router(accounts.router)
app.include_router(categories.router)
app.include_router(transactions.router)
app.include_router(budgets.router)
app.include_router(dashboard.router)


@app.get("/", tags=["Health"])
def health():
    return {"status": "LedgerFlow API running", "version": "1.0.0"}
