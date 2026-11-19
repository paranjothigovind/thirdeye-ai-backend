"""LMS Access and Entitlement Authorization Service

Handles course and lesson access authorization for learners.
Designed to support future extensions (paid course purchases and
LMS subscription memberships) without rewriting existing authorization logic.
"""
from typing import Tuple, Optional
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.course import Course, CourseModule, Lesson, CourseEnrollment
from app.models.payment import Payment


class LMSAccessService:
    """Service governing learner access to courses and curriculum lessons"""

    @staticmethod
    def get_course_enrollment(
        db: Session, user_id: int, course_id: int
    ) -> Optional[CourseEnrollment]:
        """Fetch active enrollment for user in course"""
        return (
            db.query(CourseEnrollment)
            .filter(
                CourseEnrollment.user_id == user_id,
                CourseEnrollment.course_id == course_id,
                CourseEnrollment.status == "active",
            )
            .first()
        )

    @staticmethod
    def can_access_course(db: Session, user: User, course: Course) -> Tuple[bool, str]:
        """
        Check if user is entitled to access a course.
        Returns (is_entitled, reason).

        Rules:
        1. Course must be published.
        2. Free courses: user must be actively enrolled.
        3. Paid courses: requires verified purchase or active LMS membership.
           (Payment integration is out of scope for Phase 2, so paid courses
           cannot be accessed in this phase).
        """
        if course.status != "published":
            return False, "Course is not published"

        enrollment = LMSAccessService.get_course_enrollment(db, user.id, course.id)
        if not enrollment:
            return False, "User is not enrolled in this course"

        if course.is_free:
            return True, "Enrolled in free course"

        # Paid course: needs the active enrollment AND a captured payment for this user.
        # Authorized, failed or merely created payments never unlock content.
        purchased = (
            db.query(Payment.id)
            .filter(Payment.user_id == user.id, Payment.course_id == course.id,
                    Payment.status == "captured")
            .first()
        )
        if purchased:
            return True, "Purchased course"
        return False, "Paid course access requires verified purchase"

    @staticmethod
    def can_access_lesson(
        db: Session, user: Optional[User], lesson: Lesson
    ) -> Tuple[bool, str]:
        """
        Check if user is entitled to access a specific lesson.
        Returns (is_entitled, reason).

        Preview Policy:
        - If a lesson has is_preview=True, AND its parent module is published,
          AND the course is published, any seeker (authenticated or unauthenticated guest)
          can access it without requiring course enrollment.

        Enrollment Policy:
        - For non-preview lessons: the parent module and course must be published,
          and the learner must be authenticated with valid course entitlement (active enrollment in free course).
        """
        if not lesson.is_published:
            return False, "Lesson is not published"

        module = lesson.module
        if not module or not module.is_published:
            return False, "Lesson module is not published"

        course = module.course
        if not course or course.status != "published":
            return False, "Course is not published"

        # Explicit Preview Policy:
        if lesson.is_preview:
            return True, "Public preview lesson"

        # Non-preview lessons strictly require authenticated user with course entitlement
        if user is None:
            return False, "Authentication required for protected lessons"

        return LMSAccessService.can_access_course(db, user, course)
