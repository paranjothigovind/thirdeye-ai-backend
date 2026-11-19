"""Public LMS Course Catalog Endpoints"""
from typing import List, Optional
import math
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_

from app.core.database import get_db
from app.models.course import Course, CourseCategory, CourseModule, Lesson
from app.schemas.lms_course import (
    CategoryResponse,
    CourseListItemResponse,
    CourseDetailResponse,
    ModulePublicResponse,
    LessonPublicResponse,
    PaginatedCoursesResponse,
)

router = APIRouter()


@router.get("/categories", response_model=List[CategoryResponse])
def list_categories(db: Session = Depends(get_db)):
    """List all active course categories ordered by display order"""
    categories = (
        db.query(CourseCategory)
        .filter(CourseCategory.is_active.is_(True))
        .order_by(CourseCategory.display_order.asc(), CourseCategory.name.asc())
        .all()
    )
    return categories


@router.get("/courses", response_model=PaginatedCoursesResponse)
def list_courses(
    category_id: Optional[int] = Query(None, description="Filter by category ID"),
    level: Optional[str] = Query(None, description="Filter by level (beginner, intermediate, advanced, all_levels)"),
    is_free: Optional[bool] = Query(None, description="Filter free or paid courses"),
    search: Optional[str] = Query(None, description="Search keyword in title or description"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
):
    """List published courses with filters and pagination"""
    query = (
        db.query(Course)
        .options(joinedload(Course.category))
        .filter(Course.status == "published")
    )

    if category_id is not None:
        query = query.filter(Course.category_id == category_id)

    if level is not None:
        query = query.filter(Course.level == level)

    if is_free is not None:
        query = query.filter(Course.is_free.is_(is_free))

    if search:
        search_filter = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Course.title.ilike(search_filter),
                Course.description.ilike(search_filter),
            )
        )

    total = query.count()
    pages = math.ceil(total / limit) if total > 0 else 1
    offset = (page - 1) * limit

    courses = (
        query.order_by(Course.created_at.desc(), Course.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return PaginatedCoursesResponse(
        items=[CourseListItemResponse.model_validate(c) for c in courses],
        total=total,
        page=page,
        limit=limit,
        pages=pages,
    )


@router.get("/courses/{slug_or_id}", response_model=CourseDetailResponse)
def get_course_detail(slug_or_id: str, db: Session = Depends(get_db)):
    """
    Get course overview and syllabus by slug or numeric ID.
    Only published courses are visible to the public.
    Protected media URLs and content bodies are excluded from this response.
    """
    query = (
        db.query(Course)
        .options(
            joinedload(Course.category),
            joinedload(Course.modules).joinedload(CourseModule.lessons),
        )
        .filter(Course.status == "published")
    )

    if slug_or_id.isdigit():
        course = query.filter(Course.id == int(slug_or_id)).first()
    else:
        course = query.filter(Course.slug == slug_or_id).first()

    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )

    # Filter only published modules and published lessons
    public_modules = []
    for m in course.modules:
        if not m.is_published:
            continue
        public_lessons = [
            LessonPublicResponse.model_validate(l)
            for l in m.lessons
            if l.is_published
        ]
        public_modules.append(
            ModulePublicResponse(
                id=m.id,
                title=m.title,
                description=m.description,
                display_order=m.display_order,
                lessons=public_lessons,
            )
        )

    return CourseDetailResponse(
        id=course.id,
        slug=course.slug,
        title=course.title,
        description=course.description,
        thumbnail_url=course.thumbnail_url,
        is_free=course.is_free,
        price_amount=course.price_amount,
        currency=course.currency,
        status=course.status,
        level=course.level,
        category=CategoryResponse.model_validate(course.category) if course.category else None,
        modules=public_modules,
    )
