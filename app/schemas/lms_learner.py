"""LMS Learner Pydantic Schemas for Phase 2"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class EnrollmentResponse(BaseModel):
    """Enrollment response"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    course_id: int
    status: str
    enrolled_at: datetime
    created_at: Optional[datetime] = None


class EnrolledCourseItemResponse(BaseModel):
    """Enrolled course list item for learner dashboard"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    slug: str
    title: str
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    is_free: bool
    level: str
    status: str
    enrolled_at: datetime
    completion_percentage: float = 0.0
    is_completed: bool = False


class LessonLearnerResponse(BaseModel):
    """Protected lesson view for authorized learners or public preview"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    module_id: int
    course_id: int
    title: str
    description: Optional[str] = None
    content_type: str
    content_body: Optional[str] = None
    media_url: Optional[str] = None
    duration_seconds: int
    display_order: int
    is_preview: bool
    is_completed: bool = False
    progress_percentage: int = 0
    last_position_seconds: int = 0


class LessonProgressUpdateRequest(BaseModel):
    """Request payload for updating lesson progress"""
    progress_percentage: int = Field(..., ge=0, le=100, description="Progress percentage between 0 and 100")
    last_position_seconds: int = Field(default=0, ge=0, description="Media playback position in seconds")
    is_completed: Optional[bool] = Field(None, description="Explicit completion flag; defaults to True if progress_percentage is 100")


class LessonProgressResponse(BaseModel):
    """Lesson progress representation"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    lesson_id: int
    course_id: int
    is_completed: bool
    progress_percentage: int
    last_position_seconds: int
    completed_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CourseProgressResponse(BaseModel):
    """Course completion and aggregate progress"""
    course_id: int
    total_lessons: int
    completed_lessons: int
    completion_percentage: float
    is_completed: bool
    lesson_progress: List[LessonProgressResponse] = []


class EnrolledLessonSummary(BaseModel):
    """Lesson representation inside enrolled course view"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: Optional[str] = None
    content_type: str
    duration_seconds: int
    display_order: int
    is_preview: bool
    is_completed: bool = False
    progress_percentage: int = 0
    last_position_seconds: int = 0


class EnrolledModuleSummary(BaseModel):
    """Module representation inside enrolled course view"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: Optional[str] = None
    display_order: int
    lessons: List[EnrolledLessonSummary] = []


class EnrolledCourseDetailResponse(BaseModel):
    """Detailed enrolled course view with curriculum and user progress"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    title: str
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    is_free: bool
    level: str
    status: str
    enrolled_at: datetime
    completion_percentage: float = 0.0
    is_completed: bool = False
    modules: List[EnrolledModuleSummary] = []
