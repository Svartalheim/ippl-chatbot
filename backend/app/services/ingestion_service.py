"""
Layanan Ingestion Dokumen untuk Sistem Chatbot IPPL
Menangani ekstraksi PDF/DOCX, chunking teks, pemberian metadata RBAC,
pembuatan embedding 768-dimensi via Ollama/Mock, dan penyimpanan ke pgvector.
"""
import asyncio
import io
import logging
import math
import hashlib
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..config import settings
from ..models import Document, DocumentChunk

logger = logging.getLogger(__name__)

# Direktori penyimpanan file yang diunggah
STORAGE_DIR = Path(
    os.environ.get(
        "STORAGE_DIR",
        str(Path(__file__).resolve().parent.parent.parent / "data" / "documents"),
    )
)
try:
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    pass

# Import opsional pypdf dan docx (graceful fallback)
try:
    import pypdf
except ImportError:
    pypdf = None  # type: ignore

try:
    import docx
except ImportError:
    docx = None  # type: ignore


def deterministic_mock_embedding(text: str, dim: int = 768) -> List[float]:
    """
    Menghasilkan vektor embedding deterministik ternormalisasi 768-dimensi
    sebagai fallback ketika mode test/offline diaktifkan (ALLOW_MOCK_EMBEDDING=true).
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


def _uses_task_prefix() -> bool:
    """nomic-embed-text dilatih dengan prefiks tugas; tanpa prefiks skor kemiripan menumpuk."""
    return "nomic" in settings.ollama_embed_model.lower()


def embedding_version() -> str:
    """Label versi embedding. Mengubahnya memicu embed ulang otomatis saat startup."""
    suffix = ":prefixed" if _uses_task_prefix() else ""
    return f"ollama:{settings.ollama_embed_model}{suffix}:titled"


def document_embedding_text(filename: Optional[str], section_title: Optional[str], content: str) -> str:
    """
    Teks yang di-embed untuk sebuah chunk: nama dokumen + judul bagian + isi.
    Judul sering memuat kata kunci yang tidak muncul di isi (mis. 'Orientasi Karyawan Baru'),
    sehingga menyertakannya membuat pertanyaan seperti itu menemukan dokumen yang benar.
    Kolom `content` di database tetap hanya isi chunk.
    """
    title = Path(filename).stem if filename else ""
    header = " — ".join(x for x in (title, section_title) if x)
    return f"{header}\n{content}" if header else content


async def ollama_embedding(text: str, timeout: float = 10.0, kind: str = "document") -> List[float]:
    """
    Membuat embedding 768-dimensi via Ollama TANPA fallback.
    kind: 'document' untuk chunk yang disimpan, 'query' untuk pertanyaan pengguna.
    Melempar RuntimeError bila Ollama/model embedding belum siap.
    """
    if _uses_task_prefix():
        text = ("search_query: " if kind == "query" else "search_document: ") + text
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            res = await client.post(
                f"{settings.ollama_url}/api/embeddings",
                json={
                    "model": settings.ollama_embed_model,
                    "prompt": text,
                },
            )
    except Exception as e:
        raise RuntimeError(f"Gagal menghubungi Ollama untuk embedding: {e}") from e

    if res.status_code != 200:
        raise RuntimeError(
            f"Ollama embedding gagal (HTTP {res.status_code}): {res.text[:200]}"
        )
    emb = res.json().get("embedding")
    if not emb or len(emb) != 768:
        raise RuntimeError("Ollama tidak mengembalikan vektor embedding 768 dimensi.")
    return emb


def current_embedding_source() -> str:
    """Label sumber embedding yang disimpan di metadata_json chunk."""
    return "mock" if getattr(settings, "allow_mock_embedding", False) else embedding_version()


async def create_embedding(text: str, kind: str = "document") -> List[float]:
    """
    Membuat embedding 768-dimensi menggunakan Ollama API.
    Sediakan fallback deterministik hanya bila ALLOW_MOCK_EMBEDDING=true.
    """
    if getattr(settings, "allow_mock_embedding", False):
        return deterministic_mock_embedding(text, dim=768)
    return await ollama_embedding(text, kind=kind)


def extract_pdf_pages(file_bytes: bytes, filename: str) -> List[Dict[str, Any]]:
    """
    Mengekstrak teks per halaman dari dokumen PDF beserta nomor halaman dan deteksi judul bab/subbab.
    """
    if pypdf is None:
        raise RuntimeError("Library pypdf tidak tersedia di lingkungan saat ini.")

    reader = pypdf.PdfReader(io.BytesIO(file_bytes))
    pages: List[Dict[str, Any]] = []
    current_section = filename

    # Pola regex deteksi judul bab/subbab/bagian
    section_pattern = re.compile(
        r"(?:(?:Bab|BAB|Bagian|BAGIAN|Section|SECTION)\s+[IVXLCDM0-9]+[^\n]*|"
        r"(?:Pasal|PASAL)\s+[0-9]+[^\n]*)",
        re.MULTILINE,
    )

    for idx, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        match = section_pattern.search(text)
        if match:
            current_section = match.group(0).strip()

        pages.append({
            "page_number": idx,
            "section_title": current_section,
            "text": text,
        })

    return pages


def extract_docx_sections(file_bytes: bytes, filename: str) -> List[Dict[str, Any]]:
    """
    Mengekstrak teks per paragraf/heading dari dokumen DOCX beserta estimasi halaman dan judul bagian.
    """
    if docx is None:
        raise RuntimeError("Library python-docx tidak tersedia di lingkungan saat ini.")

    doc = docx.Document(io.BytesIO(file_bytes))
    sections: List[Dict[str, Any]] = []
    current_section = filename
    current_text_buf: List[str] = []
    current_page = 1
    char_count = 0

    section_pattern = re.compile(
        r"(?:(?:Bab|BAB|Bagian|BAGIAN|Section|SECTION)\s+[IVXLCDM0-9]+[^\n]*|"
        r"(?:Pasal|PASAL)\s+[0-9]+[^\n]*)",
    )

    for p in doc.paragraphs:
        text = p.text.strip()
        if not text:
            continue

        is_heading = (
            (p.style and p.style.name.startswith("Heading"))
            or section_pattern.match(text) is not None
        )

        if is_heading:
            if current_text_buf:
                sections.append({
                    "page_number": current_page,
                    "section_title": current_section,
                    "text": "\n".join(current_text_buf),
                })
                current_text_buf = []
            current_section = text
        else:
            current_text_buf.append(text)
            char_count += len(text)
            if char_count >= 1500:  # Estimasi pergantian halaman
                current_page += 1
                char_count = 0

    if current_text_buf:
        sections.append({
            "page_number": current_page,
            "section_title": current_section,
            "text": "\n".join(current_text_buf),
        })

    return sections


def _split_into_chunks(text: str, target_size: int = 500, overlap: int = 100) -> List[str]:
    """
    Memotong teks menjadi chunk berukuran ~target_size karakter dengan overlap ~overlap karakter
    tanpa memotong kata di tengah.
    """
    text = text.strip()
    if not text:
        return []
    if len(text) <= target_size:
        return [text]

    chunks: List[str] = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = start + target_size
        if end >= text_len:
            chunk = text[start:].strip()
            if chunk:
                chunks.append(chunk)
            break

        # Cari batas spasi terdekat sebelum target_size
        boundary = text.rfind(" ", start, end)
        if boundary == -1 or boundary <= start:
            # Jika tidak ada spasi di belakang, cari ke depan
            boundary = text.find(" ", end)
            if boundary == -1:
                boundary = text_len

        chunk = text[start:boundary].strip()
        if chunk:
            chunks.append(chunk)

        # Geser posisi awal dengan overlap namun tetap sejajar pada batas kata
        next_target = boundary - overlap
        if next_target <= start:
            start = boundary + 1
        else:
            space_pos = text.find(" ", next_target, boundary)
            if space_pos != -1:
                start = space_pos + 1
            else:
                start = boundary + 1

    return chunks


def extract_and_chunk_document(
    file_bytes: bytes,
    file_type: str,
    filename: str,
    target_size: int = 500,
    overlap: int = 100,
) -> List[Dict[str, Any]]:
    """
    Mengekstrak teks dokumen (PDF/DOCX) dan membaginya menjadi potongan-potongan chunk bernomor.
    """
    ext = file_type.lower().replace(".", "")
    if ext == "pdf":
        sections = extract_pdf_pages(file_bytes, filename)
    elif ext in ("docx", "doc"):
        sections = extract_docx_sections(file_bytes, filename)
    else:
        raise ValueError(f"Format file '{file_type}' tidak didukung. Harap gunakan PDF atau DOCX.")

    chunks: List[Dict[str, Any]] = []
    global_chunk_idx = 0

    for sec in sections:
        raw_text = sec.get("text", "").strip()
        if not raw_text:
            continue

        sec_chunks = _split_into_chunks(raw_text, target_size=target_size, overlap=overlap)
        for chunk_text in sec_chunks:
            chunks.append({
                "chunk_index": global_chunk_idx,
                "content": chunk_text,
                "page_number": sec.get("page_number", 1),
                "section_title": sec.get("section_title", filename),
            })
            global_chunk_idx += 1

    return chunks


async def process_document_file(
    session: AsyncSession,
    document: Document,
    file_bytes: bytes,
) -> Document:
    """
    Pipeline pemrosesan dokumen lengkap:
    1. Ekstraksi & chunking
    2. Pembuatan vektor embedding
    3. Penyimpanan ke document_chunks
    4. Pembaruan status dokumen
    """
    document.status = "Memproses"
    document.error_message = None
    await session.commit()

    try:
        # Simpan file ke disk storage untuk reindexing di masa depan
        saved_path = STORAGE_DIR / f"{document.id}_{document.filename}"
        with open(saved_path, "wb") as f:
            f.write(file_bytes)

        # 1. Ekstraksi dan chunking
        chunks_data = extract_and_chunk_document(
            file_bytes=file_bytes,
            file_type=document.file_type,
            filename=document.filename,
            target_size=500,
            overlap=100,
        )

        if not chunks_data:
            raise ValueError("Tidak ada teks yang dapat diekstrak dari dokumen ini.")

        # 2. Hapus chunks lama bila ada
        await session.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == document.id)
        )

        # 3. Generate embedding dan simpan ke document_chunks
        chunk_instances: List[DocumentChunk] = []
        for c in chunks_data:
            emb = await create_embedding(
                document_embedding_text(document.filename, c.get("section_title"), c["content"])
            )
            chunk_obj = DocumentChunk(
                id=uuid.uuid4(),
                document_id=document.id,
                chunk_index=c["chunk_index"],
                content=c["content"],
                page_number=c.get("page_number"),
                section_title=c.get("section_title"),
                classification=document.classification,
                embedding=emb,
                metadata_json={
                    "document_id": str(document.id),
                    "filename": document.filename,
                    "classification": document.classification,
                    "page_number": c.get("page_number"),
                    "section_title": c.get("section_title"),
                    "chunk_index": c["chunk_index"],
                    "embedding_source": current_embedding_source(),
                },
            )
            session.add(chunk_obj)
            chunk_instances.append(chunk_obj)

        document.status = "Terindeks"
        document.chunk_count = len(chunk_instances)
        document.error_message = None
        await session.commit()
        await session.refresh(document)
        logger.info(
            f"Dokumen '{document.filename}' berhasil diindeks ({len(chunk_instances)} chunks)."
        )
        return document

    except Exception as e:
        logger.error(f"Gagal memproses dokumen '{document.filename}': {e}")
        document.status = "Gagal"
        document.error_message = str(e)
        await session.commit()
        await session.refresh(document)
        return document


async def ingest_document(
    session: AsyncSession,
    filename: str,
    file_type: str,
    file_bytes: bytes,
    classification: str,
    uploaded_by: Optional[uuid.UUID] = None,
) -> Document:
    """
    Membuat record dokumen baru di basis data lalu menjalankan pipeline ingestion.
    """
    valid_classifications = ["Public", "HR", "Finance", "Confidential"]
    if classification not in valid_classifications:
        raise ValueError(
            f"Klasifikasi '{classification}' tidak valid. Pilih dari {valid_classifications}."
        )

    doc = Document(
        id=uuid.uuid4(),
        filename=filename,
        file_type=file_type.lower().replace(".", ""),
        file_size_bytes=len(file_bytes),
        classification=classification,
        status="Memproses",
        chunk_count=0,
        uploaded_by=uploaded_by,
    )
    session.add(doc)
    await session.commit()
    await session.refresh(doc)

    return await process_document_file(session, doc, file_bytes)


async def reindex_all_documents(session: AsyncSession) -> Dict[str, Any]:
    """
    Mengindeks ulang seluruh dokumen yang ada di tabel documents.
    Jika file tersimpan di disk, memproses ulang file tersebut.
    Jika file fisik tidak ditemukan (misal dokumen seed), memperbarui embedding chunk yang ada.
    """
    stmt = select(Document)
    res = await session.execute(stmt)
    docs = res.scalars().all()

    total = len(docs)
    reindexed = 0
    failed = 0
    errors: List[str] = []

    for doc in docs:
        saved_path = STORAGE_DIR / f"{doc.id}_{doc.filename}"
        if saved_path.exists():
            try:
                with open(saved_path, "rb") as f:
                    file_bytes = f.read()
                await process_document_file(session, doc, file_bytes)
                if doc.status == "Terindeks":
                    reindexed += 1
                else:
                    failed += 1
                    errors.append(f"{doc.filename}: {doc.error_message}")
            except Exception as e:
                failed += 1
                errors.append(f"{doc.filename}: {str(e)}")
        else:
            # Dokumen seed atau tanpa file fisik: re-embedding chunks yang ada
            try:
                stmt_chunks = select(DocumentChunk).where(
                    DocumentChunk.document_id == doc.id
                )
                res_chunks = await session.execute(stmt_chunks)
                chunks = res_chunks.scalars().all()

                for chunk in chunks:
                    emb = await create_embedding(
                        document_embedding_text(doc.filename, chunk.section_title, chunk.content)
                    )
                    chunk.embedding = emb
                    chunk.classification = doc.classification
                    chunk.metadata_json = {
                        "document_id": str(doc.id),
                        "filename": doc.filename,
                        "classification": doc.classification,
                        "page_number": chunk.page_number,
                        "section_title": chunk.section_title,
                        "chunk_index": chunk.chunk_index,
                        "embedding_source": current_embedding_source(),
                    }

                doc.status = "Terindeks"
                doc.chunk_count = len(chunks)
                doc.error_message = None
                await session.commit()
                reindexed += 1
            except Exception as e:
                failed += 1
                doc.status = "Gagal"
                doc.error_message = str(e)
                await session.commit()
                errors.append(f"{doc.filename}: {str(e)}")

    return {
        "total": total,
        "reindexed": reindexed,
        "failed": failed,
        "errors": errors,
        "checked_at": datetime.now(timezone.utc),
    }


async def reembed_stale_chunks(session: AsyncSession) -> int:
    """
    Meng-embed ulang chunk yang vektornya bukan versi embedding saat ini
    (vektor mock, chunk seed lama tanpa label, atau versi tanpa prefiks).
    Mengembalikan jumlah chunk yang diperbarui.
    """
    version = embedding_version()
    stmt = select(DocumentChunk).where(
        (DocumentChunk.embedding.is_(None))
        | (DocumentChunk.metadata_json["embedding_source"].astext.is_distinct_from(version))
    )
    chunks = (await session.execute(stmt.options(selectinload(DocumentChunk.document)))).scalars().all()
    for chunk in chunks:
        chunk.embedding = await ollama_embedding(
            document_embedding_text(chunk.document.filename, chunk.section_title, chunk.content),
            kind="document",
        )
        chunk.metadata_json = {**(chunk.metadata_json or {}), "embedding_source": version}
    if chunks:
        await session.commit()
    return len(chunks)


async def reembed_when_model_ready(
    session_factory: Any,
    poll_seconds: float = 15.0,
    max_wait_seconds: float = 1800.0,
) -> None:
    """
    Tugas latar belakang saat startup: tunggu model embedding Ollama siap
    (biasanya masih di-pull oleh service ollama-pull), lalu embed ulang
    chunk yang masih memakai vektor mock agar retrieval & deteksi RBAC akurat.
    """
    if getattr(settings, "allow_mock_embedding", False):
        return

    waited = 0.0
    while waited <= max_wait_seconds:
        try:
            await ollama_embedding("ping", timeout=5.0)
            break
        except Exception:
            await asyncio.sleep(poll_seconds)
            waited += poll_seconds
    else:
        logger.error(
            "Model embedding Ollama belum siap setelah %.0f detik; chunk mock tidak di-embed ulang. "
            "Jalankan 'Indeks ulang semua' di halaman Admin setelah model tersedia.",
            max_wait_seconds,
        )
        return

    try:
        async with session_factory() as session:
            count = await reembed_stale_chunks(session)
        if count:
            logger.info("Embedding ulang %d chunk mock dengan model %s selesai.", count, settings.ollama_embed_model)
    except Exception as e:
        logger.error(f"Gagal meng-embed ulang chunk mock: {e}")

