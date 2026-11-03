import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import UserInfo, current_user
from .db import SessionLocal, engine, get_session
from .models import init_db
from .routers import admin, audit, auth, chat, llm
from .seed import seed_database

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Siklus hidup aplikasi: menginisialisasi ekstensi PostgreSQL,
    skema tabel, indeks HNSW, trigger append-only audit_logs,
    serta menjalankan seeding awal pengguna & dokumen.
    """
    try:
        logger.info("Menginisialisasi skema database PostgreSQL & pgvector...")
        await init_db(engine)
        logger.info("Inisialisasi skema database berhasil.")

        logger.info("Memeriksa dan menjalankan seeding awal basis data...")
        async with SessionLocal() as session:
            await seed_database(session)
    except Exception as e:
        logger.error(f"Peringatan saat inisialisasi / seeding database: {e}")
    yield


app = FastAPI(
    title="IPPL Chatbot API",
    description="API untuk chatbot dengan autentikasi Keycloak dan LLM integration",
    version="1.0.0",
    lifespan=lifespan,
)

# Konfigurasi CORS untuk Frontend React & Akses Jaringan (termasuk 100.102.226.75)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "http://100.102.226.75:5173",
        "http://100.102.226.75:3000",
        "http://100.102.226.75:8000",
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|100\.102\.226\.75)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(llm.router)
app.include_router(admin.router)
app.include_router(audit.router)


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
