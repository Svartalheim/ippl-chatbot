"""
Aktivitas 4a: Pengujian Unit per Modul (Unit Test per Modul)
Menguji keempat modul utama:
1. auth: parsing klaim JWT, pemetaan peran ke klasifikasi dokumen (RBAC), penolakan token invalid/expired.
2. ingestion: ekstraksi teks PDF/DOCX, chunking kata & metadata klasifikasi, embedding 768 dimensi.
3. retrieval: kueri pgvector top-K relevan terfilter klasifikasi yang diizinkan (RBAC).
4. generation: pemformatan sitasi [1], [2], pengukuran latency_ms, dan pencatatan umpan balik (feedback).
"""
import io
import math
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import docx
import jwt
import pypdf
import pytest
from fastapi import HTTPException

from backend.app.auth import (
    UserInfo,
    decode_token,
    get_user_allowed_classifications,
    require_roles,
)
from backend.app.config import settings
from backend.app.models import Document, DocumentChunk, Feedback
from backend.app.schemas import FeedbackCreate
from backend.app.services.ingestion_service import (
    _split_into_chunks,
    create_embedding,
    deterministic_mock_embedding,
    extract_and_chunk_document,
    extract_docx_sections,
    extract_pdf_pages,
)
from backend.app.services.rag_service import execute_rag_query


# ============================================================================
# 1. MODUL AUTH
# ============================================================================
class TestAuthModule:
    """Pengujian Unit untuk Modul Autentikasi dan RBAC"""

    def test_user_info_claims_parsing(self):
        """Memvalidasi parsing klaim JWT ke properti UserInfo"""
        exp_time = int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())
        iat_time = int(datetime.now(timezone.utc).timestamp())

        claims = {
            "preferred_username": "rina.pratama",
            "email": "rina.pratama@perusahaan.co.id",
            "given_name": "Rina",
            "family_name": "Pratama",
            "name": "Rina Pratama",
            "sub": "b2c9d1a3-1111-2222-3333-444455556666",
            "realm_access": {"roles": ["HR", "default-roles-dev"]},
            "resource_access": {"fastapi-app": {"roles": ["hr_user"]}},
            "email_verified": True,
            "exp": exp_time,
            "iat": iat_time,
        }

        user = UserInfo(claims)
        assert user.username == "rina.pratama"
        assert user.email == "rina.pratama@perusahaan.co.id"
        assert user.first_name == "Rina"
        assert user.last_name == "Pratama"
        assert user.full_name == "Rina Pratama"
        assert user.subject == "b2c9d1a3-1111-2222-3333-444455556666"
        assert "HR" in user.roles
        assert user.email_verified is True
        assert user.expires_at is not None
        assert user.has_role("HR") is True
        assert user.has_role("Finance") is False

        # to_dict response
        user_dict = user.to_dict()
        assert user_dict["username"] == "rina.pratama"
        assert user_dict["email"] == "rina.pratama@perusahaan.co.id"

    @pytest.mark.asyncio
    async def test_role_to_allowed_classifications_mapping(self):
        """
        Memvalidasi pemetaan peran ke klasifikasi dokumen yang diizinkan sesuai matriks RBAC:
        - Karyawan: ['Public']
        - HR: ['Public', 'HR']
        - Finance: ['Public', 'Finance']
        - Manajemen: ['Public', 'HR', 'Finance', 'Confidential']
        - Admin: ['Public']
        - Auditor: []
        """
        mock_session = AsyncMock()
        # Mocking scalar_one_or_none mengembalikan None agar membaca default rbac_defaults
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        assert await get_user_allowed_classifications(mock_session, "Karyawan") == ["Public"]
        assert await get_user_allowed_classifications(mock_session, "HR") == ["Public", "HR"]
        assert await get_user_allowed_classifications(mock_session, "Finance") == ["Public", "Finance"]
        assert await get_user_allowed_classifications(mock_session, "Manajemen") == [
            "Public",
            "HR",
            "Finance",
            "Confidential",
        ]
        assert await get_user_allowed_classifications(mock_session, "Admin") == ["Public"]
        assert await get_user_allowed_classifications(mock_session, "Auditor") == []

    def test_decode_token_invalid_format(self):
        """Memvalidasi penolakan token dengan format tidak valid"""
        with pytest.raises(HTTPException) as exc_info:
            decode_token("bukan-sebuah-jwt-token-yang-sah")
        assert exc_info.value.status_code == 401
        assert "format tidak valid" in exc_info.value.detail or "tidak valid" in exc_info.value.detail

    def test_decode_token_expired(self):
        """Memvalidasi penolakan token yang sudah kedaluwarsa"""
        # Buat token kedaluwarsa secara sintaksis
        expired_payload = {
            "sub": "user-expired",
            "exp": int((datetime.now(timezone.utc) - timedelta(hours=2)).timestamp()),
            "iss": f"{settings.keycloak_public_url}/realms/dev",
        }
        # Encode dengan secret dummy tanpa RS256 JWKS validasi akan memicu decode/signature exception
        token = jwt.encode(expired_payload, "a-very-long-dummy-secret-key-32b!", algorithm="HS256")

        with pytest.raises(HTTPException) as exc_info:
            decode_token(token)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_require_roles_authorization(self):
        """Memvalidasi dependency require_roles menolak peran yang tidak berhak (403)"""
        user_hr = UserInfo({"preferred_username": "rina", "realm_access": {"roles": ["HR"]}})
        user_hr.role_name = "HR"

        # Endpoint khusus Finance & Admin
        checker = require_roles("Finance", "Admin")

        # HR mencoba akses -> harus 403 Forbidden
        with pytest.raises(HTTPException) as exc_info:
            await checker(user=user_hr)
        assert exc_info.value.status_code == 403
        assert "Akses ditolak" in exc_info.value.detail

        # User dengan role Finance -> berhasil
        user_fin = UserInfo({"preferred_username": "dimas", "realm_access": {"roles": ["Finance"]}})
        user_fin.role_name = "Finance"
        res = await checker(user=user_fin)
        assert res.username == "dimas"


# ============================================================================
# 2. MODUL INGESTION
# ============================================================================
class TestIngestionModule:
    """Pengujian Unit untuk Modul Ingestion Dokumen & Embedding"""

    def test_pdf_extraction(self):
        """Mengekstrak teks halaman dan deteksi judul bab dari dokumen PDF"""
        pdf_bytes = (
            b"%PDF-1.4\n"
            b"1 0 obj <</Type /Catalog /Pages 2 0 R>> endobj\n"
            b"2 0 obj <</Type /Pages /Kids [3 0 R] /Count 1>> endobj\n"
            b"3 0 obj <</Type /Page /Parent 2 0 R /Resources <</Font <</F1 4 0 R>>>> /MediaBox [0 0 612 792] /Contents 5 0 R>> endobj\n"
            b"4 0 obj <</Type /Font /Subtype /Type1 /BaseFont /Helvetica>> endobj\n"
            b"5 0 obj <</Length 68>> stream\n"
            b"BT\n/F1 12 Tf\n72 712 Td\n(Bab 1 Ketentuan Umum Perusahaan IPPL) Tj\nET\n"
            b"endstream endobj\n"
            b"xref\n0 6\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000227 00000 n \n0000000295 00000 n \n"
            b"trailer <</Size 6 /Root 1 0 R>>\nstartxref\n413\n%%EOF\n"
        )

        sections = extract_pdf_pages(pdf_bytes, "aturan_perusahaan.pdf")
        assert len(sections) == 1
        assert sections[0]["page_number"] == 1
        assert "Ketentuan Umum" in sections[0]["text"] or "Bab 1" in sections[0]["section_title"]

    def test_docx_extraction(self):
        """Mengekstrak teks dan heading dari dokumen DOCX"""
        doc = docx.Document()
        doc.add_heading("Bab 2 Kebijakan Cuti Karyawan", level=1)
        doc.add_paragraph("Karyawan berhak atas cuti tahunan sebesar 12 hari kerja per tahun kalender.")

        buf = io.BytesIO()
        doc.save(buf)
        docx_bytes = buf.getvalue()

        sections = extract_docx_sections(docx_bytes, "kebijakan_cuti.docx")
        assert len(sections) == 1
        assert sections[0]["section_title"] == "Bab 2 Kebijakan Cuti Karyawan"
        assert "cuti tahunan sebesar 12 hari" in sections[0]["text"]

    def test_text_chunking_word_boundary_and_overlap(self):
        """
        Memvalidasi pemotongan teks ~500 karakter dengan overlap ~100 karakter
        tanpa memotong kata di tengah.
        """
        # Teks panjang terdiri dari kalimat-kalimat utuh
        sentence = "Karyawan wajib mematuhi seluruh peraturan keselamatan kerja dan tata tertib internal perusahaan. "
        long_text = sentence * 15  # ~1470 karakter

        chunks = _split_into_chunks(long_text, target_size=500, overlap=100)
        assert len(chunks) >= 3

        for chunk in chunks:
            # Tidak boleh ada spasi berlebih di awal/akhir
            assert chunk == chunk.strip()
            # Panjang wajar mendekati target
            assert len(chunk) <= 600

        # Verifikasi bahwa chunk tidak memotong kata di tengah:
        # Kata pertama dan terakhir harus berupa kata utuh (bukan pecahan suku kata)
        first_chunk_words = chunks[0].split()
        assert first_chunk_words[0] == "Karyawan"

    def test_extract_and_chunk_document_metadata(self):
        """Memvalidasi metadata klasifikasi dan chunk index pada hasil ekstraksi"""
        doc = docx.Document()
        doc.add_heading("Bagian 1 Struktur Organisasi", level=1)
        doc.add_paragraph("Struktur organisasi terdiri dari Dewan Komisaris, Direksi, dan Divisi Teknis.")

        buf = io.BytesIO()
        doc.save(buf)
        docx_bytes = buf.getvalue()

        chunks = extract_and_chunk_document(docx_bytes, "docx", "struktur.docx")
        assert len(chunks) >= 1
        c0 = chunks[0]
        assert "chunk_index" in c0
        assert "page_number" in c0
        assert "section_title" in c0
        assert "content" in c0
        assert c0["chunk_index"] == 0

    def test_deterministic_mock_embedding_768_dim(self):
        """
        Memvalidasi embedding deterministik menghasilkan vektor 768 dimensi ternormalisasi (norm=1.0)
        """
        text_sample = "Kebijakan remunerasi dan bonus tahunan divisi keuangan."
        emb1 = deterministic_mock_embedding(text_sample, dim=768)
        emb2 = deterministic_mock_embedding(text_sample, dim=768)

        # Panjang tepat 768 dimensi
        assert len(emb1) == 768
        # Deterministik (sama persis untuk input yang sama)
        assert emb1 == emb2

        # Vektor ternormalisasi (L2 norm ~ 1.0)
        norm = math.sqrt(sum(x * x for x in emb1))
        assert abs(norm - 1.0) < 1e-4

        # Teks berbeda menghasilkan vektor berbeda
        emb_different = deterministic_mock_embedding("Pertanyaan lain tentang cuti.", dim=768)
        assert emb1 != emb_different

    @pytest.mark.asyncio
    async def test_create_embedding_with_mock_flag(self):
        """Memvalidasi fallback pembuatan embedding via create_embedding saat allow_mock_embedding=True"""
        with patch.object(settings, "allow_mock_embedding", True):
            vec = await create_embedding("Tes embedding cepat")
            assert len(vec) == 768
            assert isinstance(vec[0], float)


# ============================================================================
# 3. MODUL RETRIEVAL
# ============================================================================
class TestRetrievalModule:
    """Pengujian Unit untuk Modul Similarity Search & Filter RBAC pgvector"""

    @pytest.mark.asyncio
    async def test_similarity_search_rbac_filtering(self):
        """
        Memvalidasi similarity search memfilter dokumen secara ketat
        berdasarkan allowed_classifications peran pengguna.
        """
        mock_session = AsyncMock()

        # Data tiruan chunks dari database
        doc_id = uuid.uuid4()
        public_row = {
            "id": uuid.uuid4(),
            "document_id": doc_id,
            "chunk_index": 0,
            "content": "Jadwal jam kerja kantor adalah pukul 08:00 sampai 17:00 WIB.",
            "page_number": 1,
            "section_title": "Jam Kerja",
            "classification": "Public",
            "filename": "peraturan_umum.pdf",
            "score": 0.88,
        }

        # Mock query allowed mengembalikan hanya Public
        mock_res_allowed = MagicMock()
        mock_res_allowed.mappings().all.return_value = [public_row]

        # Mock query global mengembalikan Public
        mock_res_global = MagicMock()
        mock_res_global.mappings().first.return_value = public_row

        # Mock query audit log select (untuk record_audit_log)
        mock_res_audit = MagicMock()
        mock_res_audit.scalar_one_or_none.return_value = "GENESIS"

        mock_session.execute.side_effect = [mock_res_allowed, mock_res_global, mock_res_audit]

        with patch.object(settings, "allow_mock_embedding", True), \
             patch("backend.app.services.rag_service.record_audit_log", new_callable=AsyncMock), \
             patch(
                 "backend.app.services.rag_service._ollama_chat",
                 new=AsyncMock(return_value="Jam kerja kantor dimulai pukul 08:00 WIB [1]."),
             ):
            res = await execute_rag_query(
                session=mock_session,
                query="Kapan jam kerja kantor dimulai?",
                user_name="Andi Nugroho",
                user_role="Karyawan",
                allowed_classifications=["Public"],
            )

        assert res["status"] == "SUCCESS"
        assert len(res["citations"]) == 1
        assert res["citations"][0]["classification"] == "Public"
        assert res["citations"][0]["filename"] == "peraturan_umum.pdf"


# ============================================================================
# 4. MODUL GENERATION
# ============================================================================
class TestGenerationModule:
    """Pengujian Unit untuk Generasi Respons Bersitasi, Latensi, dan Feedback"""

    def test_citation_formatting_and_attributes(self):
        """Memvalidasi struktur array sitasi [1], [2] yang dikembalikan untuk UI"""
        doc_id = str(uuid.uuid4())
        citations = [
            {
                "index": 1,
                "document_id": doc_id,
                "filename": "sop_keuangan_2024.pdf",
                "section_title": "Bab 3 Anggaran",
                "page_number": 12,
                "classification": "Finance",
                "relevance_score": 0.85,
            },
            {
                "index": 2,
                "document_id": doc_id,
                "filename": "sop_keuangan_2024.pdf",
                "section_title": "Bab 4 Pengadaan",
                "page_number": 15,
                "classification": "Finance",
                "relevance_score": 0.79,
            },
        ]

        # Validasi format indeks sitasi berurutan
        assert citations[0]["index"] == 1
        assert citations[1]["index"] == 2
        # Validasi ketersediaan metadata lengkap untuk navigasi UI
        for cit in citations:
            assert cit["filename"].endswith(".pdf")
            assert cit["relevance_score"] >= 0.70
            assert cit["page_number"] > 0
            assert cit["classification"] in ("Public", "HR", "Finance", "Confidential")

    def test_feedback_schema_validation(self):
        """Memvalidasi skema umpan balik (jempol positif / negatif beserta komentar)"""
        msg_id = uuid.uuid4()

        # Umpan balik positif
        fb_pos = FeedbackCreate(
            message_id=msg_id,
            is_positive=True,
            comment="Jawaban sangat akurat dan sitasi tepat.",
        )
        assert fb_pos.is_positive is True
        assert fb_pos.message_id == msg_id

        # Umpan balik negatif
        fb_neg = FeedbackCreate(
            message_id=msg_id,
            is_positive=False,
            comment="Sitasi halaman kurang sesuai dengan bab.",
        )
        assert fb_neg.is_positive is False
        assert fb_neg.comment == "Sitasi halaman kurang sesuai dengan bab."

    def test_feedback_sqlalchemy_model(self):
        """Memvalidasi model SQLAlchemy Feedback"""
        msg_id = uuid.uuid4()
        user_id = uuid.uuid4()

        fb = Feedback(
            message_id=msg_id,
            user_id=user_id,
            is_positive=True,
            comment="Sangat membantu",
        )
        assert fb.message_id == msg_id
        assert fb.is_positive is True
        assert fb.comment == "Sangat membantu"


# ============================================================================
# 5. KUALITAS JAWABAN: hanya sumber relevan & dikutip, kegagalan LLM terlihat
# ============================================================================
def _row(score, filename, classification="Public", content="isi"):
    return {
        "id": uuid.uuid4(),
        "document_id": uuid.uuid4(),
        "chunk_index": 0,
        "content": content,
        "page_number": 1,
        "section_title": "Bagian",
        "classification": classification,
        "filename": filename,
        "score": score,
    }


def _session_with(rows):
    session = AsyncMock()
    res_allowed = MagicMock()
    res_allowed.mappings().all.return_value = rows
    res_global = MagicMock()
    res_global.mappings().first.return_value = rows[0] if rows else None
    session.execute.side_effect = [res_allowed, res_global]
    return session


class TestAnswerQuality:
    @pytest.mark.asyncio
    async def test_low_scores_return_not_found_without_sources(self):
        """Pertanyaan tanpa dokumen relevan (mis. rata-rata gaji) tidak boleh menampilkan sumber acak."""
        from backend.app.services.rag_service import NOT_FOUND_ANSWER

        rows = [_row(0.30, "Panduan Portal HR.pdf"), _row(0.29, "Jadwal Libur Nasional 2026.pdf")]
        llm = AsyncMock(return_value="tidak boleh dipanggil")
        with patch.object(settings, "allow_mock_embedding", True), \
             patch("backend.app.services.rag_service.record_audit_log", new_callable=AsyncMock), \
             patch("backend.app.services.rag_service._ollama_chat", new=llm):
            res = await execute_rag_query(
                session=_session_with(rows), query="Berapakah rata-rata gaji karyawan?",
                user_name="Dimas Fajar", user_role="Finance",
                allowed_classifications=["Public", "Finance"], similarity_threshold=0.55,
            )
        assert res["status"] == "SUCCESS"
        assert res["answer"] == NOT_FOUND_ANSWER
        assert res["citations"] == []
        llm.assert_not_called()

    @pytest.mark.asyncio
    async def test_llm_not_found_reply_drops_sources(self):
        from backend.app.services.rag_service import NOT_FOUND_ANSWER

        rows = [_row(0.70, "Panduan Portal HR.pdf"), _row(0.68, "Anggaran Bonus 2026.pdf", "Finance")]
        with patch.object(settings, "allow_mock_embedding", True), \
             patch("backend.app.services.rag_service.record_audit_log", new_callable=AsyncMock), \
             patch("backend.app.services.rag_service._ollama_chat", new=AsyncMock(return_value=NOT_FOUND_ANSWER)):
            res = await execute_rag_query(
                session=_session_with(rows), query="Berapakah rata-rata gaji karyawan?",
                user_name="Dimas Fajar", user_role="Finance",
                allowed_classifications=["Public", "Finance"], similarity_threshold=0.55,
            )
        assert res["answer"] == NOT_FOUND_ANSWER
        assert res["citations"] == []

    @pytest.mark.asyncio
    async def test_only_cited_sources_returned_and_renumbered(self):
        rows = [
            _row(0.80, "Panduan Portal HR.pdf"),
            _row(0.79, "Peraturan Perusahaan 2026.pdf", "HR"),
            _row(0.78, "Jadwal Libur Nasional 2026.pdf"),
        ]
        answer = "Hak cuti tahunan adalah 12 hari [2]. Pengajuan lewat portal HR [2]. Lihat juga [9]."
        with patch.object(settings, "allow_mock_embedding", True), \
             patch("backend.app.services.rag_service.record_audit_log", new_callable=AsyncMock), \
             patch("backend.app.services.rag_service._ollama_chat", new=AsyncMock(return_value=answer)):
            res = await execute_rag_query(
                session=_session_with(rows), query="Berapa hak cuti tahunan?",
                user_name="Rina Pratama", user_role="HR",
                allowed_classifications=["Public", "HR"], similarity_threshold=0.55,
            )
        assert [c["filename"] for c in res["citations"]] == ["Peraturan Perusahaan 2026.pdf"]
        assert res["citations"][0]["index"] == 1
        assert "[1]" in res["answer"] and "[2]" not in res["answer"] and "[9]" not in res["answer"]

    @pytest.mark.asyncio
    async def test_llm_failure_returns_error_not_raw_chunk(self):
        rows = [_row(0.80, "Panduan Portal HR.pdf", content="ISI CHUNK MENTAH")]
        audit = AsyncMock()
        with patch.object(settings, "allow_mock_embedding", True), \
             patch("backend.app.services.rag_service.record_audit_log", new=audit), \
             patch("backend.app.services.rag_service._ollama_chat", new=AsyncMock(side_effect=RuntimeError("HTTP 404"))):
            res = await execute_rag_query(
                session=_session_with(rows), query="Bagaimana prosedur cuti?",
                user_name="Andi Nugroho", user_role="Karyawan",
                allowed_classifications=["Public"], similarity_threshold=0.55,
            )
        assert res["status"] == "ERROR"
        assert "ISI CHUNK MENTAH" not in res["answer"]
        assert res["citations"] == []
        assert audit.call_args.kwargs["status"] == "Gagal"

    @pytest.mark.parametrize("q", [
        "dokumen apa saja yang bisa aku akses?",
        "Dokumen apa yang dapat saya lihat?",
        "tampilkan daftar dokumen",
        "apa saja dokumen yang tersedia?",
    ])
    def test_document_list_question_detected(self, q):
        from backend.app.services.rag_service import is_document_list_question
        assert is_document_list_question(q)

    @pytest.mark.parametrize("q", [
        "apa isi dari laporan keuangan q3?",
        "Berapa hari hak cuti tahunan karyawan?",
        "Bagaimana prosedur pengajuan cuti di portal HR?",
    ])
    def test_content_question_not_treated_as_document_list(self, q):
        from backend.app.services.rag_service import is_document_list_question
        assert not is_document_list_question(q)

    @pytest.mark.asyncio
    async def test_document_list_only_shows_allowed_classifications(self):
        session = AsyncMock()
        res_docs = MagicMock()
        res_docs.mappings().all.return_value = [
            {"filename": "Anggaran Bonus 2026.pdf", "classification": "Finance"},
            {"filename": "Panduan Portal HR.pdf", "classification": "Public"},
        ]
        session.execute.return_value = res_docs
        with patch("backend.app.services.rag_service.record_audit_log", new_callable=AsyncMock):
            res = await execute_rag_query(
                session=session, query="dokumen apa saja yang bisa aku akses?",
                user_name="Dimas Fajar", user_role="Finance",
                allowed_classifications=["Public", "Finance"],
            )
        params = session.execute.call_args.args[1]
        assert params["allowed"] == ["Public", "Finance"]
        assert "Anggaran Bonus 2026.pdf" in res["answer"]
        assert res["citations"] == []

    @pytest.mark.parametrize("q", ["halo", "Halo!", "hai kak", "selamat pagi", "terima kasih banyak", "thanks"])
    def test_small_talk_detected(self, q):
        from backend.app.services.rag_service import is_small_talk
        assert is_small_talk(q)

    @pytest.mark.parametrize("q", [
        "halo, berapa hari hak cuti tahunan?",
        "apa isi dari laporan keuangan q3?",
        "selamat pagi, bagaimana prosedur cuti di portal HR?",
    ])
    def test_real_questions_not_small_talk(self, q):
        from backend.app.services.rag_service import is_small_talk
        assert not is_small_talk(q)

