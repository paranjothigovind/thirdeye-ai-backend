"""LMS Course Catalog Pydantic Schemas"""
from datetime import datetime
from typing import List, Optional, Generic, TypeVar
from pydantic import BaseModel, Field, ConfigDict

T = TypeVar("T")


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    description: Optional[str] = None
    display_order: int
    is_active: bool


class LessonPublicResponse(BaseModel):
    """Public lesson metadata without protected media references or full content"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: Optional[str] = None
    content_type: str
    duration_seconds: int
    display_order: int
    is_preview: bool


class LessonAdminResponse(BaseModel):
    """Admin lesson representation including protected media and published state"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    module_id: int
    title: str
    description: Optional[str] = None
    content_type: str
    content_body: Optional[str] = None
    media_url: Optional[str] = None
    duration_seconds: int
    display_order: int
    is_preview: bool
    is_published: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class LessonCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    content_type: str = Field(default="video", pattern="^(video|audio|article|quiz)$")
    content_body: Optional[str] = None
    media_url: Optional[str] = None
    duration_seconds: int = Field(default=0, ge=0)
    display_order: int = Field(default=0, ge=0)
    is_preview: bool = False
    is_published: bool = True


class LessonUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    content_type: Optional[str] = Field(None, pattern="^(video|audio|article|quiz)$")
    content_body: Optional[str] = None
    media_url: Optional[str] = None
    duration_seconds: Optional[int] = Field(None, ge=0)
    display_order: Optional[int] = Field(None, ge=0)
    is_preview: Optional[bool] = None
    is_published: Optional[bool] = None


class ModulePublicResponse(BaseModel):
    """Public module representation with public lessons"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: Optional[str] = None
    display_order: int
    lessons: List[LessonPublicResponse] = []


class ModuleAdminResponse(BaseModel):
    """Admin module representation with full lessons"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    title: str
    description: Optional[str] = None
    display_order: int
    is_published: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    lessons: List[LessonAdminResponse] = []


class ModuleCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    display_order: int = Field(default=0, ge=0)
    is_published: bool = True


class CourseListItemResponse(BaseModel):
    """Catalog course card representation"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    title: str
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    is_free: bool
    price_amount: Optional[int] = None
    currency: str
    status: str
    level: str
    category: Optional[CategoryResponse] = None


class CourseDetailResponse(BaseModel):
    """Detailed public course syllabus and metadata"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    title: str
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    is_free: bool
    price_amount: Optional[int] = None
    currency: str
    status: str
    level: str
    category: Optional[CategoryResponse] = None
    modules: List[ModulePublicResponse] = []


class CourseAdminResponse(BaseModel):
    """Admin view of course with all module/lesson hierarchy"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    category_id: Optional[int] = None
    slug: str
    title: str
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    is_free: bool
    price_amount: Optional[int] = None
    currency: str
    status: str
    level: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    category: Optional[CategoryResponse] = None
    modules: List[ModuleAdminResponse] = []


class CourseCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    slug: Optional[str] = Field(None, min_length=1, max_length=150)
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    category_id: Optional[int] = None
    is_free: bool = False
    price_amount: Optional[int] = Field(None, ge=0)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    level: str = Field(default="beginner", pattern="^(beginner|intermediate|advanced|all_levels)$")
    status: str = Field(default="draft", pattern="^(draft|published|archived)$")


class CourseUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    slug: Optional[str] = Field(None, min_length=1, max_length=150)
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    category_id: Optional[int] = None
    is_free: Optional[bool] = None
    price_amount: Optional[int] = Field(None, ge=0)
    currency: Optional[str] = Field(None, min_length=3, max_length=3)
    level: Optional[str] = Field(None, pattern="^(beginner|intermediate|advanced|all_levels)$")
    status: Optional[str] = Field(None, pattern="^(draft|published|archived)$")


class PaginatedCoursesResponse(BaseModel):
    items: List[CourseListItemResponse]
    total: int
    page: int
    limit: int
    pages: int
