"""
Skema Pydantic v2 untuk Sistem Chatbot IPPL
Mendefinisikan DTO untuk validasi request & serialisasi response.
"""
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# Klasifikasi & Status Literals
ClassificationType = Literal["Public", "HR", "Finance", "Confidential"]
DocumentStatusType = Literal["Terindeks", "Memproses", "Gagal"]
MessageSenderType = Literal["user", "assistant"]
MessageStatusType = Literal["SUCCESS", "QUERY_DENIED", "PROMPT_INJECTION", "ERROR"]
AuditLogStatusType = Literal["Berhasil", "Ditolak RBAC", "Diblokir", "Gagal"]


# ==========================================
# 1. Role Schemas
# ==========================================
class RoleBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, description="Nama peran unik (cth: HR, Finance)")
    description: Optional[str] = Field(None, description="Deskripsi tugas dan cakupan peran")
    allowed_classifications: List[ClassificationType] = Field(
        default_factory=list, description="Daftar klasifikasi dokumen yang diizinkan diakses"
    )
    can_manage_docs: bool = Field(False, description="Izin mengunggah dan mengelola dokumen")
    can_manage_rbac: bool = Field(False, description="Izin mengubah peran & izin RBAC")
    can_view_audit: bool = Field(False, description="Izin meninjau log audit")


class RoleCreate(RoleBase):
    pass


class RoleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = None
    allowed_classifications: Optional[List[ClassificationType]] = None
    can_manage_docs: Optional[bool] = None
    can_manage_rbac: Optional[bool] = None
    can_view_audit: Optional[bool] = None


class RoleResponse(RoleBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# 2. User Schemas
# ==========================================
class UserBase(BaseModel):
    keycloak_sub: str = Field(..., description="Subject identifier unik dari Keycloak")
    username: str = Field(..., min_length=1, max_length=100)
    full_name: Optional[str] = None
    email: Optional[str] = None
    role_id: Optional[int] = None
    is_active: bool = True


class UserCreate(UserBase):
    pass


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    role_id: Optional[int] = None
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    id: UUID
    last_login_at: Optional[datetime] = None
    created_at: datetime
    role: Optional[RoleResponse] = None

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# 3. Document & Chunk Schemas
# ==========================================
class DocumentBase(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)
    file_type: str = Field(..., min_length=1, max_length=50)
    file_size_bytes: int = Field(..., ge=0)
    classification: ClassificationType = Field(..., description="Tingkat klasifikasi keamanan")


class DocumentCreate(DocumentBase):
    uploaded_by: Optional[UUID] = None


class DocumentResponse(DocumentBase):
    id: UUID
    status: DocumentStatusType
    error_message: Optional[str] = None
    chunk_count: int
    uploaded_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CitationItem(BaseModel):
    index: int = Field(..., description="Nomor urut sitasi inline [1], [2]")
    document_id: UUID
    filename: str
    section_title: Optional[str] = None
    page_number: Optional[int] = None
    classification: ClassificationType
    relevance_score: float = Field(..., ge=0.0, le=1.0)


class DocumentChunkResponse(BaseModel):
    id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    page_number: Optional[int] = None
    section_title: Optional[str] = None
    classification: ClassificationType
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# 4. Feedback Schemas
# ==========================================
class FeedbackBase(BaseModel):
    is_positive: bool = Field(..., description="True untuk thumbs up, False untuk thumbs down")
    comment: Optional[str] = Field(None, description="Komentar tambahan evaluasi respons")


class FeedbackCreate(FeedbackBase):
    message_id: UUID


class FeedbackResponse(FeedbackBase):
    id: UUID
    message_id: UUID
    user_id: Optional[UUID] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# 5. Chat Message & Session Schemas
# ==========================================
class ChatMessageBase(BaseModel):
    content: str = Field(..., min_length=1)


class ChatMessageCreate(ChatMessageBase):
    pass


class ChatMessageResponse(BaseModel):
    id: UUID
    session_id: UUID
    sender: MessageSenderType
    content: str
    status: MessageStatusType
    blocked_classification: Optional[str] = None
    citations_json: List[Dict[str, Any]] = Field(default_factory=list)
    latency_ms: Optional[int] = None
    created_at: datetime
    feedback: Optional[FeedbackResponse] = None

    model_config = ConfigDict(from_attributes=True)


class ChatSessionCreate(BaseModel):
    title: str = Field(default="Percakapan Baru", min_length=1, max_length=255)


class ChatSessionResponse(BaseModel):
    id: UUID
    user_id: Optional[UUID] = None
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatSessionDetailResponse(ChatSessionResponse):
    messages: List[ChatMessageResponse] = Field(default_factory=list)


# ==========================================
# 6. Audit Log Schemas
# ==========================================
class AuditLogBase(BaseModel):
    actor_name: str
    actor_role: str
    action: str
    status: AuditLogStatusType
    detail: Optional[str] = None
    ip_address: Optional[str] = None


class AuditLogCreate(AuditLogBase):
    actor_user_id: Optional[UUID] = None
    prev_hash: str
    curr_hash: str


class AuditLogResponse(AuditLogBase):
    id: int
    created_at: datetime
    actor_user_id: Optional[UUID] = None
    prev_hash: str
    curr_hash: str

    model_config = ConfigDict(from_attributes=True)


class AuditVerificationResponse(BaseModel):
    verified: bool
    total_entries: int
    checked_at: datetime
    broken_at_id: Optional[int] = None


# ==========================================
# 7. System Health Schema
# ==========================================
class HealthResponse(BaseModel):
    status: str
    db: str
