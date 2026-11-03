"""
Modul Seeding Awal untuk Sistem Chatbot IPPL
Mengisi data awal: Peran & Izin RBAC, Pengguna, Dokumen Sampel, Chunks Vektor, dan Log Audit Genesis.
"""
import logging
import math
import hashlib
from datetime import datetime, timezone
from typing import List, Tuple
import uuid

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .models import Document, DocumentChunk, Role, User
from .services.audit_service import record_audit_log, verify_audit_chain
from .services.ingestion_service import document_embedding_text, embedding_version, ollama_embedding

logger = logging.getLogger(__name__)


def deterministic_mock_embedding(text: str, dim: int = 768) -> List[float]:
    """
    Menghasilkan embedding deterministik ternormalisasi 768-dimensi
    sebagai fallback ketika Ollama belum aktif atau belum menarik model.
    """
    vec: List[float] = []
    for i in range(dim):
        val = (
            int(
                hashlib.sha256(f"{text}_{i}".encode("utf-8")).hexdigest()[:8],
                16,
            )
            / 0xFFFFFFFF
        )
        vec.append(val - 0.5)

    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0:
        return [0.0] * dim
    return [round(x / norm, 6) for x in vec]


async def get_embedding(text: str) -> Tuple[List[float], str]:
    """
    Membuat embedding via Ollama. Bila model belum siap (umum saat startup pertama,
    karena ollama-pull masih mengunduh model), gunakan vektor mock sementara dan
    beri label 'mock'. Tugas latar belakang reembed_when_model_ready() akan
    menggantinya dengan vektor Ollama asli setelah model tersedia.
    """
    if not getattr(settings, "allow_mock_embedding", False):
        try:
            return await ollama_embedding(text, timeout=5.0, kind="document"), embedding_version()
        except Exception:
            pass
    return deterministic_mock_embedding(text, dim=768), "mock"


async def seed_database(session: AsyncSession) -> None:
    """
    Menjalankan proses seeding jika database belum ter-seed.
    """
    # 1. Cek apakah roles sudah ada
    stmt_check = select(func.count(Role.id))
    role_count = (await session.execute(stmt_check)).scalar_one()
    if role_count > 0:
        logger.info("Database sudah memiliki data peran, melewati seeding.")
        return

    logger.info("Memulai seeding data awal...")

    # 2. Seed 6 Peran Matriks RBAC
    roles_data = [
        {
            "name": "Karyawan",
            "description": "Default untuk semua karyawan",
            "allowed_classifications": ["Public"],
            "can_manage_docs": False,
            "can_manage_rbac": False,
            "can_view_audit": False,
        },
        {
            "name": "HR",
            "description": "Divisi Human Resources",
            "allowed_classifications": ["Public", "HR"],
            "can_manage_docs": False,
            "can_manage_rbac": False,
            "can_view_audit": False,
        },
        {
            "name": "Finance",
            "description": "Divisi Keuangan",
            "allowed_classifications": ["Public", "Finance"],
            "can_manage_docs": False,
            "can_manage_rbac": False,
            "can_view_audit": False,
        },
        {
            "name": "Manajemen",
            "description": "Direksi & kepala divisi",
            "allowed_classifications": ["Public", "HR", "Finance", "Confidential"],
            "can_manage_docs": False,
            "can_manage_rbac": False,
            "can_view_audit": False,
        },
        {
            "name": "Admin",
            "description": "Pengelola sistem",
            "allowed_classifications": ["Public"],
            "can_manage_docs": True,
            "can_manage_rbac": True,
            "can_view_audit": False,
        },
        {
            "name": "Auditor",
            "description": "Peninjau kepatuhan - hanya baca",
            "allowed_classifications": [],
            "can_manage_docs": False,
            "can_manage_rbac": False,
            "can_view_audit": True,
        },
    ]

    role_instances = {}
    for r in roles_data:
        role_obj = Role(**r)
        session.add(role_obj)
        role_instances[r["name"]] = role_obj

    await session.flush()

    # 3. Seed Pengguna Prototipe Figma
    users_data = [
        {
            "username": "rina",
            "email": "rina.pratama@perusahaan.co.id",
            "full_name": "Rina Pratama",
            "keycloak_sub": "keycloak-sub-rina",
            "role_name": "HR",
        },
        {
            "username": "dimas",
            "email": "dimas.fajar@perusahaan.co.id",
            "full_name": "Dimas Fajar",
            "keycloak_sub": "keycloak-sub-dimas",
            "role_name": "Finance",
        },
        {
            "username": "sari",
            "email": "sari.wulandari@perusahaan.co.id",
            "full_name": "Sari Wulandari",
            "keycloak_sub": "keycloak-sub-sari",
            "role_name": "Manajemen",
        },
        {
            "username": "budi",
            "email": "budi.santoso@perusahaan.co.id",
            "full_name": "Budi Santoso",
            "keycloak_sub": "keycloak-sub-budi",
            "role_name": "Auditor",
        },
        {
            "username": "andi",
            "email": "andi.nugroho@perusahaan.co.id",
            "full_name": "Andi Nugroho",
            "keycloak_sub": "keycloak-sub-andi",
            "role_name": "Karyawan",
        },
        {
            "username": "admin_sistem",
            "email": "admin@perusahaan.co.id",
            "full_name": "Admin Sistem",
            "keycloak_sub": "keycloak-sub-admin",
            "role_name": "Admin",
        },
        {
            "username": "dev",
            "email": "dev@example.com",
            "full_name": "Dev User",
            "keycloak_sub": "keycloak-sub-dev",
            "role_name": "Karyawan",
        },
    ]

    user_instances = {}
    for u in users_data:
        role_obj = role_instances[u["role_name"]]
        user_obj = User(
            username=u["username"],
            email=u["email"],
            full_name=u["full_name"],
            keycloak_sub=u["keycloak_sub"],
            role_id=role_obj.id,
            is_active=True,
            last_login_at=datetime.now(timezone.utc),
        )
        session.add(user_obj)
        user_instances[u["username"]] = user_obj

    await session.flush()
    admin_user = user_instances["admin_sistem"]

    # 4. Seed Dokumen Sampel & Chunks Vektor (Public, HR, Finance, Confidential)
    documents_data = [
        {
            "filename": "Peraturan Perusahaan 2026.pdf",
            "file_type": "pdf",
            "file_size_bytes": 4200000,
            "classification": "HR",
            "status": "Terindeks",
            "uploaded_by": admin_user.id,
            "chunks": [
                {
                    "chunk_index": 0,
                    "section_title": "Bab IV Hal. 14: Kebijakan Cuti Tahunan",
                    "page_number": 14,
                    "content": (
                        "Karyawan tetap berhak atas 12 hari cuti tahunan setelah masa kerja 12 bulan berturut-turut. "
                        "Sisa cuti maksimal 6 hari kerja dapat dibawa ke tahun berikutnya dan harus digunakan paling "
                        "lambat 31 Maret; lewat dari itu, sisa cuti dianggap hangus. Pengajuan dilakukan melalui portal HR "
                        "minimal 7 hari kerja sebelumnya."
                    ),
                }
            ],
        },
        {
            "filename": "Panduan Portal HR.pdf",
            "file_type": "pdf",
            "file_size_bytes": 1100000,
            "classification": "Public",
            "status": "Terindeks",
            "uploaded_by": admin_user.id,
            "chunks": [
                {
                    "chunk_index": 0,
                    "section_title": "Bagian 2.3 Hal. 6: Prosedur Pengajuan Cuti di Portal HR",
                    "page_number": 6,
                    "content": (
                        "Prosedur pengajuan cuti tahunan dilakukan secara mandiri oleh karyawan melalui portal HR online. "
                        "Karyawan memilih jenis cuti, memasukkan rentang tanggal, dan melampirkan keterangan bila diperlukan. "
                        "Persetujuan otomatis diteruskan ke atasan langsung dan tim HR."
                    ),
                }
            ],
        },
        {
            "filename": "Laporan Keuangan Q3 2026.pdf",
            "file_type": "pdf",
            "file_size_bytes": 6500000,
            "classification": "Finance",
            "status": "Terindeks",
            "uploaded_by": admin_user.id,
            "chunks": [
                {
                    "chunk_index": 0,
                    "section_title": "Laporan Realisasi Anggaran Q3 2026",
                    "page_number": 8,
                    "content": (
                        "Realisasi anggaran belanja operasional Q3 2026 mencapai 84% dari total alokasi pagu tahunan. "
                        "Efisiensi belanja modal berhasil dipertahankan pada tingkat margin 12% di bawah batas maksimal deviasi."
                    ),
                }
            ],
        },
        {
            "filename": "Anggaran Bonus 2026.pdf",
            "file_type": "pdf",
            "file_size_bytes": 900000,
            "classification": "Finance",
            "status": "Terindeks",
            "uploaded_by": admin_user.id,
            "chunks": [
                {
                    "chunk_index": 0,
                    "section_title": "Total Anggaran Bonus Divisi Finance 2026",
                    "page_number": 3,
                    "content": (
                        "Berapa total anggaran bonus divisi Finance tahun ini: Total alokasi anggaran bonus untuk seluruh staf "
                        "dan manajemen divisi Finance tahun 2026 ditetapkan sebesar Rp 1.850.000.000 (Satu Miliar Delapan Ratus "
                        "Lima Puluh Juta Rupiah) berdasarkan pencapaian target efisiensi keuangan kuartalan."
                    ),
                }
            ],
        },
        {
            "filename": "Rencana Akuisisi Proyek X.pdf",
            "file_type": "pdf",
            "file_size_bytes": 3500000,
            "classification": "Confidential",
            "status": "Terindeks",
            "uploaded_by": admin_user.id,
            "chunks": [
                {
                    "chunk_index": 0,
                    "section_title": "Rencana Akuisisi Strategis Proyek X",
                    "page_number": 1,
                    "content": (
                        "Rencana akuisisi strategis kepemilikan 65% saham Proyek X bernilai valuasi Rp 45 Miliar ditargetkan "
                        "selesai pada penutupan tahun fiskal 2026. Dokumen ini bersifat sangat rahasia (Confidential) dan hanya "
                        "dapat diakses oleh Manajemen."
                    ),
                }
            ],
        },
        {
            "filename": "SOP Onboarding Karyawan.docx",
            "file_type": "docx",
            "file_size_bytes": 800000,
            "classification": "Public",
            "status": "Terindeks",
            "uploaded_by": admin_user.id,
            "chunks": [
                {
                    "chunk_index": 0,
                    "section_title": "Panduan Orientasi & Fasilitas Karyawan Baru",
                    "page_number": 1,
                    "content": (
                        "Standard Operating Procedure (SOP) onboarding karyawan baru meliputi pengenalan budaya kerja perusahaan, "
                        "serah terima laptop kerja, kartu akses gedung, serta pembuatan akun SSO Keycloak dan email kantor."
                    ),
                }
            ],
        },
        {
            "filename": "Jadwal Libur Nasional 2026.pdf",
            "file_type": "pdf",
            "file_size_bytes": 200000,
            "classification": "Public",
            "status": "Terindeks",
            "uploaded_by": admin_user.id,
            "chunks": [
                {
                    "chunk_index": 0,
                    "section_title": "Daftar Hari Libur Nasional & Cuti Bersama 2026",
                    "page_number": 1,
                    "content": (
                        "Daftar hari libur resmi nasional dan cuti bersama tahun 2026 mencakup total 17 hari libur nasional "
                        "dan 8 hari cuti bersama sesuai Keputusan Bersama Tiga Menteri Republik Indonesia."
                    ),
                }
            ],
        },
    ]

    for doc_item in documents_data:
        chunks = doc_item.pop("chunks")
        doc_obj = Document(
            id=uuid.uuid4(),
            filename=doc_item["filename"],
            file_type=doc_item["file_type"],
            file_size_bytes=doc_item["file_size_bytes"],
            classification=doc_item["classification"],
            status=doc_item["status"],
            chunk_count=len(chunks),
            uploaded_by=doc_item["uploaded_by"],
        )
        session.add(doc_obj)
        await session.flush()

        for c in chunks:
            emb, emb_source = await get_embedding(
                document_embedding_text(doc_obj.filename, c.get("section_title"), c["content"])
            )
            chunk_obj = DocumentChunk(
                id=uuid.uuid4(),
                document_id=doc_obj.id,
                chunk_index=c["chunk_index"],
                content=c["content"],
                page_number=c.get("page_number"),
                section_title=c.get("section_title"),
                classification=doc_obj.classification,
                embedding=emb,
                metadata_json={
                    "filename": doc_obj.filename,
                    "classification": doc_obj.classification,
                    "page_number": c.get("page_number"),
                    "section_title": c.get("section_title"),
                    "embedding_source": emb_source,
                },
            )
            session.add(chunk_obj)

    await session.commit()

    # 5. Seed Log Audit Awal Berantai Hash SHA-256
    await record_audit_log(
        session=session,
        actor_name="Sistem",
        actor_role="Admin",
        action="ROLE_UPDATE",
        detail="Inisialisasi 6 peran dan matriks izin RBAC berhasil",
        status="Berhasil",
        actor_user_id=admin_user.id,
        commit=True,
    )

    await record_audit_log(
        session=session,
        actor_name="Admin Sistem",
        actor_role="Admin",
        action="DOC_UPLOAD",
        detail="Inisialisasi 7 dokumen sampel dan chunk pgvector berhasil",
        status="Berhasil",
        actor_user_id=admin_user.id,
        commit=True,
    )

    # 6. Verifikasi keutuhan rantai hash awal
    verification = await verify_audit_chain(session)
    logger.info(
        f"Seeding selesai! Verifikasi audit chain: {verification['verified']}, total entri: {verification['total_entries']}"
    )


async def main():
    from .db import SessionLocal
    async with SessionLocal() as session:
        await seed_database(session)
        print("✅ Seeding basis data berhasil diselesaikan!")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
