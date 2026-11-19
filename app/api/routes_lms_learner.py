"""LMS Learner Endpoints: Enrollment, Lesson Access & Progress Tracking"""
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.auth import get_current_user, get_optional_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.course import Course, CourseModule, Lesson, CourseEnrollment, UserLessonProgress
from app.schemas.lms_learner import (
    EnrollmentResponse,
    EnrolledCourseItemResponse,
    EnrolledCourseDetailResponse,
    EnrolledModuleSummary,
    EnrolledLessonSummary,
    LessonLearnerResponse,
    LessonProgressUpdateRequest,
    LessonProgressResponse,
    CourseProgressResponse,
)
from app.services.lms_access_service import LMSAccessService

router = APIRouter()


@router.post(
    "/courses/{course_id}/enroll",
    response_model=EnrollmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Enroll in a free course",
)
def enroll_in_course(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Enroll the authenticated learner in a published free course.
    Paid courses and duplicate enrollments are rejected.
    """
    course = (
        db.query(Course)
        .filter(Course.id == course_id, Course.status == "published")
        .first()
    )
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found",
        )

    if not course.is_free:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Enrollment is only supported for free courses in this phase. Paid courses require purchase.",
        )

    existing = LMSAccessService.get_course_enrollment(db, current_user.id, course.id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Already enrolled in this course",
        )

    enrollment = CourseEnrollment(
        user_id=current_user.id,
        course_id=course.id,
        status="active",
        enrolled_at=datetime.now(timezone.utc),
    )
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    return enrollment


@router.get(
    "/courses",
    response_model=List[EnrolledCourseItemResponse],
    summary="List enrolled courses for current learner",
)
def list_enrolled_courses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all published courses the authenticated learner is enrolled in with progress"""
    enrollments = (
        db.query(CourseEnrollment)
        .options(joinedload(CourseEnrollment.course))
        .join(Course, CourseEnrollment.course_id == Course.id)
        .filter(
            CourseEnrollment.user_id == current_user.id,
            CourseEnrollment.status == "active",
            Course.status == "published",
        )
        .all()
    )

    results = []
    for enr in enrollments:
        course = enr.course
        # Published curriculum lessons
        published_lessons = (
            db.query(Lesson.id)
            .join(CourseModule, Lesson.module_id == CourseModule.id)
            .filter(
                CourseModule.course_id == course.id,
                CourseModule.is_published.is_(True),
                Lesson.is_published.is_(True),
            )
            .all()
        )
        total_lessons = len(published_lessons)
        completion_pct = 0.0
        is_completed = False

        if total_lessons > 0:
            lesson_ids = [l[0] for l in published_lessons]
            completed_count = (
                db.query(UserLessonProgress)
                .filter(
                    UserLessonProgress.user_id == current_user.id,
                    UserLessonProgress.lesson_id.in_(lesson_ids),
                    UserLessonProgress.is_completed.is_(True),
                )
                .count()
            )
            completion_pct = round((completed_count / total_lessons) * 100, 2)
            is_completed = (completion_pct == 100.0)

        results.append(
            EnrolledCourseItemResponse(
                id=enr.id,
                course_id=course.id,
                slug=course.slug,
                title=course.title,
                description=course.description,
                thumbnail_url=course.thumbnail_url,
                is_free=course.is_free,
                level=course.level,
                status=enr.status,
                enrolled_at=enr.enrolled_at,
                completion_percentage=completion_pct,
                is_completed=is_completed,
            )
        )
    return results


@router.get(
    "/courses/{course_id}",
    response_model=EnrolledCourseDetailResponse,
    summary="Get enrolled course curriculum and learner progress",
)
def get_enrolled_course_detail(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get full published syllabus for an enrolled course, including learner's
    completion status on each lesson.
    """
    course = (
        db.query(Course)
        .filter(Course.id == course_id, Course.status == "published")
        .first()
    )
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found",
        )

    enrollment = LMSAccessService.get_course_enrollment(db, current_user.id, course.id)
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not enrolled in this course",
        )

    # Fetch published modules and lessons
    modules = (
        db.query(CourseModule)
        .options(joinedload(CourseModule.lessons))
        .filter(
            CourseModule.course_id == course.id,
            CourseModule.is_published.is_(True),
        )
        .order_by(CourseModule.display_order.asc())
        .all()
    )

    # Fetch learner's progress for this course
    progress_map = {
        p.lesson_id: p
        for p in db.query(UserLessonProgress)
        .filter(
            UserLessonProgress.user_id == current_user.id,
            UserLessonProgress.course_id == course.id,
        )
        .all()
    }

    total_lessons = 0
    completed_lessons = 0
    module_summaries = []

    for mod in modules:
        published_lessons = [l for l in mod.lessons if l.is_published]
        published_lessons.sort(key=lambda l: l.display_order)
        lesson_summaries = []

        for les in published_lessons:
            total_lessons += 1
            prog = progress_map.get(les.id)
            les_completed = prog.is_completed if prog else False
            les_pct = prog.progress_percentage if prog else 0
            les_pos = prog.last_position_seconds if prog else 0

            if les_completed:
                completed_lessons += 1

            lesson_summaries.append(
                EnrolledLessonSummary(
                    id=les.id,
                    title=les.title,
                    description=les.description,
                    content_type=les.content_type,
                    duration_seconds=les.duration_seconds,
                    display_order=les.display_order,
                    is_preview=les.is_preview,
                    is_completed=les_completed,
                    progress_percentage=les_pct,
                    last_position_seconds=les_pos,
                )
            )

        module_summaries.append(
            EnrolledModuleSummary(
                id=mod.id,
                title=mod.title,
                description=mod.description,
                display_order=mod.display_order,
                lessons=lesson_summaries,
            )
        )

    completion_percentage = (
        round((completed_lessons / total_lessons) * 100, 2)
        if total_lessons > 0
        else 0.0
    )
    is_completed = (completion_percentage == 100.0 and total_lessons > 0)

    return EnrolledCourseDetailResponse(
        id=course.id,
        slug=course.slug,
        title=course.title,
        description=course.description,
        thumbnail_url=course.thumbnail_url,
        is_free=course.is_free,
        level=course.level,
        status=enrollment.status,
        enrolled_at=enrollment.enrolled_at,
        completion_percentage=completion_percentage,
        is_completed=is_completed,
        modules=module_summaries,
    )


@router.get(
    "/lessons/{lesson_id}",
    response_model=LessonLearnerResponse,
    summary="Access protected lesson content",
)
def get_learner_lesson(
    lesson_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    Retrieve lesson content (including media URLs and article bodies).
    Permitted if:
    - The lesson is marked as preview (and published in a published course), OR
    - The learner is authenticated and enrolled in the course.
    """
    lesson = (
        db.query(Lesson)
        .options(joinedload(Lesson.module).joinedload(CourseModule.course))
        .filter(Lesson.id == lesson_id)
        .first()
    )
    if not lesson or not lesson.is_published:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson not found",
        )

    module = lesson.module
    if not module or not module.is_published:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson not found",
        )

    course = module.course
    if not course or course.status != "published":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson not found",
        )

    can_access, reason = LMSAccessService.can_access_lesson(db, current_user, lesson)
    if not can_access:
        if current_user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to access protected lessons",
                headers={"WWW-Authenticate": "Bearer"},
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: {reason}",
        )

    # Fetch learner's progress on this lesson if authenticated
    prog = None
    if current_user is not None:
        prog = (
            db.query(UserLessonProgress)
            .filter(
                UserLessonProgress.user_id == current_user.id,
                UserLessonProgress.lesson_id == lesson.id,
            )
            .first()
        )

    return LessonLearnerResponse(
        id=lesson.id,
        module_id=lesson.module_id,
        course_id=course.id,
        title=lesson.title,
        description=lesson.description,
        content_type=lesson.content_type,
        content_body=lesson.content_body,
        media_url=lesson.media_url,
        duration_seconds=lesson.duration_seconds,
        display_order=lesson.display_order,
        is_preview=lesson.is_preview,
        is_completed=prog.is_completed if prog else False,
        progress_percentage=prog.progress_percentage if prog else 0,
        last_position_seconds=prog.last_position_seconds if prog else 0,
    )


@router.put(
    "/lessons/{lesson_id}/progress",
    response_model=LessonProgressResponse,
    summary="Update progress for a lesson",
)
def update_lesson_progress(
    lesson_id: int,
    payload: LessonProgressUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update lesson progress for the authenticated learner.
    Enforces lesson access authorization before accepting progress updates.
    """
    lesson = (
        db.query(Lesson)
        .options(joinedload(Lesson.module).joinedload(CourseModule.course))
        .filter(Lesson.id == lesson_id)
        .first()
    )
    if not lesson or not lesson.is_published:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson not found",
        )

    module = lesson.module
    if not module or not module.is_published:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson not found",
        )

    course = module.course
    if not course or course.status != "published":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson not found",
        )

    # Verify authorization
    can_access, reason = LMSAccessService.can_access_lesson(db, current_user, lesson)
    if not can_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot update progress for a lesson you cannot access",
        )

    progress_pct = payload.progress_percentage
    if payload.is_completed is not None:
        is_completed = payload.is_completed
    else:
        is_completed = (progress_pct == 100)

    now = datetime.now(timezone.utc)
    prog = (
        db.query(UserLessonProgress)
        .filter(
            UserLessonProgress.user_id == current_user.id,
            UserLessonProgress.lesson_id == lesson.id,
        )
        .first()
    )

    if not prog:
        prog = UserLessonProgress(
            user_id=current_user.id,
            lesson_id=lesson.id,
            course_id=course.id,
            progress_percentage=progress_pct,
            last_position_seconds=payload.last_position_seconds,
            is_completed=is_completed,
            completed_at=now if is_completed else None,
        )
        db.add(prog)
    else:
        prog.progress_percentage = progress_pct
        prog.last_position_seconds = payload.last_position_seconds
        prog.is_completed = is_completed
        if is_completed and not prog.completed_at:
            prog.completed_at = now
        elif not is_completed:
            prog.completed_at = None

    db.commit()
    db.refresh(prog)
    return prog


@router.get(
    "/courses/{course_id}/progress",
    response_model=CourseProgressResponse,
    summary="Get overall progress for an enrolled course",
)
def get_course_progress(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Calculate and return aggregate course progress for the authenticated learner.
    Returns 0.0% completion if the course has no published lessons.
    """
    course = (
        db.query(Course)
        .filter(Course.id == course_id, Course.status == "published")
        .first()
    )
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found",
        )

    enrollment = LMSAccessService.get_course_enrollment(db, current_user.id, course.id)
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not enrolled in this course",
        )

    published_lessons = (
        db.query(Lesson)
        .join(CourseModule, Lesson.module_id == CourseModule.id)
        .filter(
            CourseModule.course_id == course.id,
            CourseModule.is_published.is_(True),
            Lesson.is_published.is_(True),
        )
        .all()
    )

    total_lessons = len(published_lessons)
    lesson_ids = [l.id for l in published_lessons]

    progress_records = []
    completed_count = 0

    if lesson_ids:
        progress_records = (
            db.query(UserLessonProgress)
            .filter(
                UserLessonProgress.user_id == current_user.id,
                UserLessonProgress.lesson_id.in_(lesson_ids),
            )
            .all()
        )
        completed_count = sum(1 for p in progress_records if p.is_completed)

    completion_percentage = (
        round((completed_count / total_lessons) * 100, 2)
        if total_lessons > 0
        else 0.0
    )
    is_completed = (completion_percentage == 100.0 and total_lessons > 0)

    return CourseProgressResponse(
        course_id=course.id,
        total_lessons=total_lessons,
        completed_lessons=completed_count,
        completion_percentage=completion_percentage,
        is_completed=is_completed,
        lesson_progress=[
            LessonProgressResponse.model_validate(p) for p in progress_records
        ],
    )
