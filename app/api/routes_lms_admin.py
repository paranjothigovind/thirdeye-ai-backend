"""Admin LMS Course Management Endpoints"""
from typing import List, Optional
import math
import re
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.auth import get_current_admin
from app.models.user import User
from app.models.course import Course, CourseCategory, CourseModule, Lesson
from app.schemas.lms_course import (
    CourseAdminResponse,
    CourseCreateRequest,
    CourseUpdateRequest,
    ModuleAdminResponse,
    ModuleCreateRequest,
    LessonAdminResponse,
    LessonCreateRequest,
    LessonUpdateRequest,
)

router = APIRouter()


def _slugify(text: str) -> str:
    """Generate a clean URL-friendly slug from text"""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")


@router.get("/courses")
def list_admin_courses(
    status_filter: Optional[str] = Query(None, alias="status", pattern="^(draft|published|archived)$"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """List all courses across all publication states for administrators"""
    query = (
        db.query(Course)
        .options(
            joinedload(Course.category),
            joinedload(Course.modules).joinedload(CourseModule.lessons),
        )
    )

    if status_filter:
        query = query.filter(Course.status == status_filter)

    total = query.count()
    pages = math.ceil(total / limit) if total > 0 else 1
    offset = (page - 1) * limit

    courses = (
        query.order_by(Course.created_at.desc(), Course.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "items": [CourseAdminResponse.model_validate(c) for c in courses],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages,
    }


@router.post("/courses", response_model=CourseAdminResponse, status_code=status.HTTP_201_CREATED)
def create_course(
    course_in: CourseCreateRequest,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Create a new course draft"""
    slug = course_in.slug.strip() if course_in.slug else _slugify(course_in.title)
    if not slug:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A valid slug or title is required"
        )

    # Check for existing slug
    existing = db.query(Course).filter(Course.slug == slug).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Course with slug '{slug}' already exists"
        )

    # Verify category if specified
    if course_in.category_id is not None:
        cat = db.query(CourseCategory).filter(CourseCategory.id == course_in.category_id).first()
        if not cat:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Category ID {course_in.category_id} not found"
            )

    if not course_in.is_free and (course_in.price_amount is None or course_in.price_amount <= 0):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Paid courses must have a price_amount greater than zero"
        )

    course = Course(
        title=course_in.title,
        slug=slug,
        description=course_in.description,
        thumbnail_url=course_in.thumbnail_url,
        category_id=course_in.category_id,
        is_free=course_in.is_free,
        price_amount=0 if course_in.is_free else course_in.price_amount,
        currency=course_in.currency.upper(),
        level=course_in.level,
        status=course_in.status,
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return CourseAdminResponse.model_validate(course)


@router.put("/courses/{course_id}", response_model=CourseAdminResponse)
def update_course(
    course_id: int,
    course_in: CourseUpdateRequest,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Update course attributes"""
    course = (
        db.query(Course)
        .options(
            joinedload(Course.category),
            joinedload(Course.modules).joinedload(CourseModule.lessons),
        )
        .filter(Course.id == course_id)
        .first()
    )
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )

    if course_in.slug is not None:
        slug = course_in.slug.strip()
        existing = db.query(Course).filter(Course.slug == slug, Course.id != course_id).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Course with slug '{slug}' already exists"
            )
        course.slug = slug

    if course_in.category_id is not None:
        cat = db.query(CourseCategory).filter(CourseCategory.id == course_in.category_id).first()
        if not cat:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Category ID {course_in.category_id} not found"
            )
        course.category_id = course_in.category_id

    if course_in.title is not None:
        course.title = course_in.title
    if course_in.description is not None:
        course.description = course_in.description
    if course_in.thumbnail_url is not None:
        course.thumbnail_url = course_in.thumbnail_url
    target_is_free = course_in.is_free if course_in.is_free is not None else course.is_free
    target_price = course_in.price_amount if course_in.price_amount is not None else course.price_amount
    if not target_is_free and (target_price is None or target_price <= 0):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Paid courses must have a price_amount greater than zero"
        )

    if course_in.is_free is not None:
        course.is_free = course_in.is_free
        if course.is_free:
            course.price_amount = 0
    if course_in.price_amount is not None and not course.is_free:
        course.price_amount = course_in.price_amount
    if course_in.currency is not None:
        course.currency = course_in.currency.upper()
    if course_in.level is not None:
        course.level = course_in.level
    if course_in.status is not None:
        course.status = course_in.status


    db.commit()
    db.refresh(course)
    return CourseAdminResponse.model_validate(course)


@router.post("/courses/{course_id}/modules", response_model=ModuleAdminResponse, status_code=status.HTTP_201_CREATED)
def create_course_module(
    course_id: int,
    module_in: ModuleCreateRequest,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Add a module to an existing course"""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )

    module = CourseModule(
        course_id=course_id,
        title=module_in.title,
        description=module_in.description,
        display_order=module_in.display_order,
        is_published=module_in.is_published,
    )
    db.add(module)
    db.commit()
    db.refresh(module)
    return ModuleAdminResponse.model_validate(module)


@router.post("/modules/{module_id}/lessons", response_model=LessonAdminResponse, status_code=status.HTTP_201_CREATED)
def create_module_lesson(
    module_id: int,
    lesson_in: LessonCreateRequest,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Add a lesson to an existing module"""
    module = db.query(CourseModule).filter(CourseModule.id == module_id).first()
    if not module:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Module not found"
        )

    lesson = Lesson(
        module_id=module_id,
        title=lesson_in.title,
        description=lesson_in.description,
        content_type=lesson_in.content_type,
        content_body=lesson_in.content_body,
        media_url=lesson_in.media_url,
        duration_seconds=lesson_in.duration_seconds,
        display_order=lesson_in.display_order,
        is_preview=lesson_in.is_preview,
        is_published=lesson_in.is_published,
    )
    db.add(lesson)
    db.commit()
    db.refresh(lesson)
    return LessonAdminResponse.model_validate(lesson)


@router.put("/lessons/{lesson_id}", response_model=LessonAdminResponse)
def update_lesson(
    lesson_id: int,
    lesson_in: LessonUpdateRequest,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Update lesson details, content or media"""
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson not found"
        )

    if lesson_in.title is not None:
        lesson.title = lesson_in.title
    if lesson_in.description is not None:
        lesson.description = lesson_in.description
    if lesson_in.content_type is not None:
        lesson.content_type = lesson_in.content_type
    if lesson_in.content_body is not None:
        lesson.content_body = lesson_in.content_body
    if lesson_in.media_url is not None:
        lesson.media_url = lesson_in.media_url
    if lesson_in.duration_seconds is not None:
        lesson.duration_seconds = lesson_in.duration_seconds
    if lesson_in.display_order is not None:
        lesson.display_order = lesson_in.display_order
    if lesson_in.is_preview is not None:
        lesson.is_preview = lesson_in.is_preview
    if lesson_in.is_published is not None:
        lesson.is_published = lesson_in.is_published

    db.commit()
    db.refresh(lesson)
    return LessonAdminResponse.model_validate(lesson)


@router.post("/courses/{course_id}/publish", response_model=CourseAdminResponse)
def publish_course(
    course_id: int,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Publish a course to make it visible in the public catalog"""
    course = (
        db.query(Course)
        .options(
            joinedload(Course.category),
            joinedload(Course.modules).joinedload(CourseModule.lessons),
        )
        .filter(Course.id == course_id)
        .first()
    )
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )

    if not course.is_free and (course.price_amount is None or course.price_amount <= 0):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Paid courses must have a price_amount greater than zero before publishing"
        )

    has_published_curriculum = any(
        m.is_published and any(l.is_published for l in m.lessons)
        for m in course.modules
    )
    if not has_published_curriculum:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot publish a course without at least one published module and lesson"
        )

    course.status = "published"
    db.commit()
    db.refresh(course)
    return CourseAdminResponse.model_validate(course)

