"""
Model SQLAlchemy 2.0 untuk Sistem Chatbot IPPL
Mendukung pgvector, RBAC, RAG chunking, chat session, feedback, dan audit_logs (append-only).
"""
import uuid
from datetime import datetime
from typing import Any, List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

try:
    from pgvector.sqlalchemy import Vector
except ImportError:  # Fallback jika pgvector belum terpasang di runtime lokal
    from sqlalchemy.types import UserDefinedType

    class Vector(UserDefinedType):  # type: ignore
        def __init__(self, dim: int = 768):
            self.dim = dim

        def get_col_spec(self, **kw: Any) -> str:
            return f"vector({self.dim})"


class Base(DeclarativeBase):
    pass


# 1. Tabel Roles
class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    allowed_classifications: Mapped[List[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list
    )
    can_manage_docs: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_manage_rbac: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_view_audit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    users: Mapped[List["User"]] = relationship("User", back_populates="role")


# 2. Tabel Users
class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    keycloak_sub: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("roles.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    role: Mapped[Optional["Role"]] = relationship("Role", back_populates="users")
    documents: Mapped[List["Document"]] = relationship("Document", back_populates="uploader")
    chat_sessions: Mapped[List["ChatSession"]] = relationship("ChatSession", back_populates="user")
    feedbacks: Mapped[List["Feedback"]] = relationship("Feedback", back_populates="user")
    audit_logs: Mapped[List["AuditLog"]] = relationship("AuditLog", back_populates="actor_user")


# 3. Tabel Documents
class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "classification IN ('Public', 'HR', 'Finance', 'Confidential')",
            name="check_document_classification",
        ),
        CheckConstraint(
            "status IN ('Terindeks', 'Memproses', 'Gagal')",
            name="check_document_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    classification: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="Memproses")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    uploaded_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    uploader: Mapped[Optional["User"]] = relationship("User", back_populates="documents")
    chunks: Mapped[List["DocumentChunk"]] = relationship(
        "DocumentChunk", back_populates="document", cascade="all, delete-orphan"
    )


# 4. Tabel Document Chunks (Vektor RAG)
class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        CheckConstraint(
            "classification IN ('Public', 'HR', 'Finance', 'Confidential')",
            name="check_chunk_classification",
        ),
        Index("idx_document_chunks_classification", "classification"),
        Index("idx_document_chunks_document_id", "document_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    section_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    classification: Mapped[str] = mapped_column(String(20), nullable=False)
    embedding = Column(Vector(768), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    document: Mapped["Document"] = relationship("Document", back_populates="chunks")


# 5. Tabel Chat Sessions
class ChatSession(Base):
    __tablename__ = "chat_sessions"
    __table_args__ = (
        Index("idx_chat_sessions_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped[Optional["User"]] = relationship("User", back_populates="chat_sessions")
    messages: Mapped[List["ChatMessage"]] = relationship(
        "ChatMessage", back_populates="session", cascade="all, delete-orphan"
    )


# 6. Tabel Chat Messages
class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        CheckConstraint(
            "sender IN ('user', 'assistant')",
            name="check_chat_message_sender",
        ),
        CheckConstraint(
            "status IN ('SUCCESS', 'QUERY_DENIED', 'PROMPT_INJECTION', 'ERROR')",
            name="check_chat_message_status",
        ),
        Index("idx_chat_messages_session_id", "session_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False
    )
    sender: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="SUCCESS")
    blocked_classification: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    citations_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    session: Mapped["ChatSession"] = relationship("ChatSession", back_populates="messages")
    feedback: Mapped[Optional["Feedback"]] = relationship(
        "Feedback",
        back_populates="message",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )


# 7. Tabel Feedbacks
class Feedback(Base):
    __tablename__ = "feedbacks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_messages.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    is_positive: Mapped[bool] = mapped_column(Boolean, nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    message: Mapped["ChatMessage"] = relationship("ChatMessage", back_populates="feedback")
    user: Mapped[Optional["User"]] = relationship("User", back_populates="feedbacks")


# 8. Tabel Audit Logs (Append-Only & Rantai Hash SHA-256)
class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('Berhasil', 'Ditolak RBAC', 'Diblokir', 'Gagal')",
            name="check_audit_log_status",
        ),
        Index("idx_audit_logs_created_at", "created_at"),
        Index("idx_audit_logs_action", "action"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    actor_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    actor_name: Mapped[str] = mapped_column(Text, nullable=False)
    actor_role: Mapped[str] = mapped_column(Text, nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    prev_hash: Mapped[str] = mapped_column(Text, nullable=False)
    curr_hash: Mapped[str] = mapped_column(Text, nullable=False)

    actor_user: Mapped[Optional["User"]] = relationship("User", back_populates="audit_logs")


async def init_db(engine: AsyncEngine) -> None:
    """
    Inisialisasi ekstensi PostgreSQL, skema tabel, indeks HNSW,
    dan trigger append-only untuk tabel audit_logs.
    """
    async with engine.begin() as conn:
        # 1. Ekstensi
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto;"))

        # 2. Tabel SQLAlchemy
        await conn.run_sync(Base.metadata.create_all)

        # 3. Indeks HNSW khusus vector (jika belum ada)
        await conn.execute(
            text(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_indexes
                        WHERE tablename = 'document_chunks'
                        AND indexname = 'idx_document_chunks_embedding'
                    ) THEN
                        CREATE INDEX idx_document_chunks_embedding
                        ON document_chunks USING hnsw (embedding vector_cosine_ops);
                    END IF;
                END $$;
                """
            )
        )

        # 4. Trigger append-only untuk audit_logs.
        # PENTING: driver asyncpg menolak beberapa perintah SQL dalam satu execute()
        # ("cannot insert multiple commands into a prepared statement"), jadi setiap
        # perintah dijalankan terpisah.
        for stmt in AUDIT_LOG_TRIGGER_STATEMENTS:
            await conn.execute(text(stmt))


AUDIT_LOG_TRIGGER_STATEMENTS = [
    """
    CREATE OR REPLACE FUNCTION prevent_audit_log_modification()
    RETURNS TRIGGER AS $$
    BEGIN
        RAISE EXCEPTION 'Operasi % pada tabel audit_logs tidak diizinkan. Audit log bersifat append-only.', TG_OP;
        RETURN NULL;
    END;
    $$ LANGUAGE plpgsql
    """,
    "DROP TRIGGER IF EXISTS trg_prevent_audit_log_modification ON audit_logs",
    """
    CREATE TRIGGER trg_prevent_audit_log_modification
    BEFORE UPDATE OR DELETE ON audit_logs
    FOR EACH ROW
    EXECUTE FUNCTION prevent_audit_log_modification()
    """,
    # Trigger baris tidak menangkap TRUNCATE, sehingga butuh trigger tingkat statement.
    """
    CREATE OR REPLACE FUNCTION prevent_audit_log_truncate()
    RETURNS TRIGGER AS $$
    BEGIN
        RAISE EXCEPTION 'Operasi TRUNCATE pada tabel audit_logs tidak diizinkan. Audit log bersifat append-only.';
        RETURN NULL;
    END;
    $$ LANGUAGE plpgsql
    """,
    "DROP TRIGGER IF EXISTS trg_prevent_audit_log_truncate ON audit_logs",
    """
    CREATE TRIGGER trg_prevent_audit_log_truncate
    BEFORE TRUNCATE ON audit_logs
    FOR EACH STATEMENT
    EXECUTE FUNCTION prevent_audit_log_truncate()
    """,
]
