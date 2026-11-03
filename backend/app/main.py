import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import UserInfo, current_user
from .db import engine, get_session
from .models import init_db
from .routers import auth, llm

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Siklus hidup aplikasi: menginisialisasi ekstensi PostgreSQL,
    skema tabel, indeks HNSW, dan trigger append-only audit_logs.
    """
    try:
        logger.info("Menginisialisasi skema database PostgreSQL & pgvector...")
        await init_db(engine)
        logger.info("Inisialisasi skema database berhasil.")
    except Exception as e:
        logger.error(f"Peringatan: Gagal menginisialisasi database saat startup: {e}")
    yield


app = FastAPI(
    title="IPPL Chatbot API",
    description="API untuk chatbot dengan autentikasi Keycloak dan LLM integration",
    version="1.0.0",
    lifespan=lifespan,
)

# Include routers
app.include_router(auth.router)
app.include_router(llm.router)


@app.get("/health", tags=["System"])
async def health(session: AsyncSession = Depends(get_session)):
    """Health check endpoint untuk monitoring"""
    await session.execute(text("SELECT 1"))
    return {"status": "ok", "db": "up"}


@app.get("/me", tags=["User"], summary="Get current user info")
async def me(user: UserInfo = Depends(current_user)):
    """
    Mendapatkan informasi user yang sedang login dari JWT token.
    
    Memerlukan header: `Authorization: Bearer <access_token>`
    """
    return user.to_dict()
