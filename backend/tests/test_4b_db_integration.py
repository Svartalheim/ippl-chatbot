"""
Aktivitas 4b (integrasi): Uji Imutabilitas & Integritas Log Audit terhadap PostgreSQL asli.

Berbeda dengan test_4b_security.py (yang memakai mock), pengujian ini menjalankan
perintah SQL sungguhan ke database stack Docker:
  - UPDATE / DELETE / TRUNCATE pada audit_logs harus ditolak trigger PostgreSQL.
  - Penulisan audit log secara bersamaan tidak boleh membuat rantai hash bercabang.
  - verify_audit_chain() atas seluruh tabel harus mengembalikan verified=True.

Prasyarat: stack berjalan (`make up`) dan backend sudah pernah start (membuat trigger).
Koneksi: env TEST_DATABASE_URL, atau dibangun dari POSTGRES_* di .env ke localhost:5432.
Bila database tidak dapat dihubungi, seluruh test di file ini di-skip.

Catatan: test menambahkan beberapa baris audit_logs berlabel actor 'pytest-integration'.
Itu disengaja — tabel append-only memang tidak bisa dibersihkan.
"""
import asyncio
import os
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.models import AuditLog
from backend.app.services.audit_service import record_audit_log, verify_audit_chain

pytestmark = pytest.mark.integration

TEST_ACTOR = "pytest-integration"


def _database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        return url
    env = {}
    env_file = Path(__file__).resolve().parents[2] / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    user = os.environ.get("POSTGRES_USER", env.get("POSTGRES_USER", "app"))
    pwd = os.environ.get("POSTGRES_PASSWORD", env.get("POSTGRES_PASSWORD", ""))
    db = os.environ.get("POSTGRES_DB", env.get("POSTGRES_DB", "app"))
    host = os.environ.get("POSTGRES_HOST", "localhost")
    return f"postgresql+asyncpg://{user}:{pwd}@{host}:5432/{db}"


@pytest_asyncio.fixture
async def sessionmaker():
    try:
        import greenlet  # noqa: F401
    except ImportError:
        pytest.fail(
            "Paket 'greenlet' belum terpasang (wajib untuk SQLAlchemy async). "
            "Jalankan: pip install -r backend/requirements.txt"
        )

    engine = create_async_engine(_database_url(), pool_size=30, max_overflow=0)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:  # pragma: no cover - tergantung lingkungan
        try:
            await engine.dispose()
        except Exception:
            pass
        pytest.skip(f"PostgreSQL tidak dapat dihubungi ({e}); jalankan 'make up' dulu.")
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def _ensure_one_row(sm) -> int:
    async with sm() as s:
        last_id = (await s.execute(select(AuditLog.id).order_by(AuditLog.id.desc()).limit(1))).scalar()
        if last_id is None:
            entry = await record_audit_log(
                s, TEST_ACTOR, "Auditor", "INTEGRATION_TEST", "baris awal uji imutabilitas", "Berhasil"
            )
            last_id = entry.id
        return last_id


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE audit_logs SET detail = 'hacked' WHERE id = :id",
        "DELETE FROM audit_logs WHERE id = :id",
    ],
    ids=["update", "delete"],
)
async def test_row_modification_rejected_by_trigger(sessionmaker, sql):
    row_id = await _ensure_one_row(sessionmaker)
    async with sessionmaker() as s:
        with pytest.raises(DBAPIError) as exc:
            await s.execute(text(sql), {"id": row_id})
        await s.rollback()
    assert "append-only" in str(exc.value)

    # Baris tetap ada dan tidak berubah
    async with sessionmaker() as s:
        row = (await s.execute(select(AuditLog).where(AuditLog.id == row_id))).scalar_one()
        assert row.detail != "hacked"


@pytest.mark.asyncio
async def test_truncate_rejected_by_trigger(sessionmaker):
    await _ensure_one_row(sessionmaker)
    async with sessionmaker() as s:
        # Cek dulu trigger-nya ada, supaya TRUNCATE tidak pernah dicoba tanpa proteksi.
        installed = (
            await s.execute(
                text(
                    "SELECT count(*) FROM pg_trigger "
                    "WHERE tgname = 'trg_prevent_audit_log_truncate' AND NOT tgisinternal"
                )
            )
        ).scalar_one()
        assert installed == 1, (
            "Trigger trg_prevent_audit_log_truncate belum terpasang. Restart backend "
            "(docker compose restart backend) agar init_db() membuatnya, lalu cek log backend."
        )

        before = (await s.execute(text("SELECT count(*) FROM audit_logs"))).scalar_one()
        try:
            with pytest.raises(DBAPIError) as exc:
                await s.execute(text("TRUNCATE audit_logs"))
        finally:
            await s.rollback()  # jangan pernah commit, apa pun hasilnya
    assert "append-only" in str(exc.value)
    async with sessionmaker() as s:
        after = (await s.execute(text("SELECT count(*) FROM audit_logs"))).scalar_one()
    assert after >= before


@pytest.mark.asyncio
async def test_concurrent_writes_keep_hash_chain_linear(sessionmaker):
    """
    25 penulisan bersamaan dari sesi DB berbeda. Tanpa advisory lock, beberapa baris
    akan memiliki prev_hash yang sama (rantai bercabang).
    """
    n = 25

    async def write(i: int) -> int:
        async with sessionmaker() as s:
            entry = await record_audit_log(
                s, TEST_ACTOR, "Auditor", "INTEGRATION_TEST", f"tulis bersamaan #{i}", "Berhasil"
            )
            return entry.id

    ids = await asyncio.gather(*(write(i) for i in range(n)))
    first, last = min(ids), max(ids)

    async with sessionmaker() as s:
        rows = (
            await s.execute(
                select(AuditLog)
                .where(AuditLog.id >= first, AuditLog.id <= last)
                .order_by(AuditLog.id.asc())
            )
        ).scalars().all()
        prev_of_first = (
            await s.execute(
                select(AuditLog.curr_hash).where(AuditLog.id < first).order_by(AuditLog.id.desc()).limit(1)
            )
        ).scalar() or "GENESIS"

    prev_hashes = [r.prev_hash for r in rows]
    assert len(prev_hashes) == len(set(prev_hashes)), "Rantai hash bercabang: ada prev_hash ganda"
    expected = prev_of_first
    for r in rows:
        assert r.prev_hash == expected, f"Rantai putus di id={r.id}"
        expected = r.curr_hash


@pytest.mark.asyncio
async def test_full_audit_chain_verifies(sessionmaker):
    async with sessionmaker() as s:
        result = await verify_audit_chain(s)
    assert result["verified"], (
        f"Rantai hash rusak di id={result['broken_at_id']}. Jika ini database dev lama yang "
        "ditulis sebelum perbaikan advisory lock, rantainya memang sudah bercabang secara permanen "
        "(tabel append-only). Jalankan 'make reset && make up' untuk database dev yang bersih."
    )
