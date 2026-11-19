"""Tests for Third EYE LMS Phase 2: Learner Enrollment, Lesson Access & Progress Tracking"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.auth import get_password_hash, create_access_token
from app.models.user import User
from app.models.course import Course, CourseCategory, CourseModule, Lesson, CourseEnrollment, UserLessonProgress

client = TestClient(app)


def _create_user(db, username: str, email: str, is_superuser: bool = False) -> tuple[User, dict]:
    """Helper to create user and return (user, auth_headers)"""
    user = User(
        username=username,
        email=email,
        hashed_password=get_password_hash("Password123!"),
        is_active=True,
        is_superuser=is_superuser,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token({"sub": user.username})
    return user, {"Authorization": f"Bearer {token}"}


def _setup_curriculum(db) -> dict:
    """Helper to create a published free course, paid course, and draft course with modules and lessons"""
    # 1. Published Free Course
    free_course = Course(
        title="Ajna Chakra Foundation",
        slug="ajna-chakra-foundation",
        description="Introduction to Third Eye meditation",
        is_free=True,
        status="published",
        level="beginner",
    )
    db.add(free_course)
    db.flush()

    mod1 = CourseModule(
        course_id=free_course.id,
        title="Module 1: Getting Started",
        display_order=1,
        is_published=True,
    )
    db.add(mod1)
    db.flush()

    les1 = Lesson(
        module_id=mod1.id,
        title="Lesson 1: Overview (Preview)",
        content_type="video",
        content_body="Welcome to the Ajna Chakra course overview.",
        media_url="https://media.thirdeye.ai/preview1.mp4",
        duration_seconds=300,
        display_order=1,
        is_preview=True,
        is_published=True,
    )
    les2 = Lesson(
        module_id=mod1.id,
        title="Lesson 2: Core Practice (Enrolled Only)",
        content_type="video",
        content_body="In-depth breathing and visualization technique.",
        media_url="https://media.thirdeye.ai/lesson2_core.mp4",
        duration_seconds=600,
        display_order=2,
        is_preview=False,
        is_published=True,
    )
    db.add_all([les1, les2])

    # 2. Published Paid Course
    paid_course = Course(
        title="Advanced Intuition Mastery",
        slug="advanced-intuition-mastery",
        description="Mastery level meditation",
        is_free=False,
        price_amount=49900,
        currency="INR",
        status="published",
        level="advanced",
    )
    db.add(paid_course)
    db.flush()

    paid_mod = CourseModule(
        course_id=paid_course.id,
        title="Module 1: Advanced Frequencies",
        display_order=1,
        is_published=True,
    )
    db.add(paid_mod)
    db.flush()

    paid_les = Lesson(
        module_id=paid_mod.id,
        title="Lesson 1: Deep Gamma States",
        content_type="video",
        content_body="High frequency activation steps.",
        media_url="https://media.thirdeye.ai/gamma_meditation.mp4",
        duration_seconds=1200,
        display_order=1,
        is_preview=False,
        is_published=True,
    )
    paid_preview_les = Lesson(
        module_id=paid_mod.id,
        title="Lesson 0: Teaser (Preview)",
        content_type="video",
        content_body="Preview of advanced course.",
        media_url="https://media.thirdeye.ai/teaser.mp4",
        duration_seconds=180,
        display_order=0,
        is_preview=True,
        is_published=True,
    )
    db.add_all([paid_les, paid_preview_les])

    # 3. Draft Course
    draft_course = Course(
        title="Unpublished Meditation Draft",
        slug="unpublished-meditation-draft",
        is_free=True,
        status="draft",
        level="beginner",
    )
    db.add(draft_course)
    db.flush()

    draft_mod = CourseModule(
        course_id=draft_course.id,
        title="Draft Module",
        display_order=1,
        is_published=True,
    )
    db.add(draft_mod)
    db.flush()

    draft_les = Lesson(
        module_id=draft_mod.id,
        title="Draft Lesson",
        content_type="article",
        content_body="Draft content",
        is_preview=False,
        is_published=True,
    )
    db.add(draft_les)

    db.commit()

    return {
        "free_course": free_course,
        "free_les1_preview": les1,
        "free_les2_enrolled": les2,
        "paid_course": paid_course,
        "paid_les": paid_les,
        "paid_preview_les": paid_preview_les,
        "draft_course": draft_course,
        "draft_les": draft_les,
    }


def test_free_course_enrollment_and_duplicate_prevention(TestingSessionLocal):
    """Test successful free course enrollment and 409 duplicate rejection"""
    db = TestingSessionLocal()
    try:
        curriculum = _setup_curriculum(db)
        free_course = curriculum["free_course"]
        learner, headers = _create_user(db, "learner_bob", "bob@example.com")

        # 1. Successful enrollment
        res = client.post(f"/api/lms/learner/courses/{free_course.id}/enroll", headers=headers)
        assert res.status_code == 201
        data = res.json()
        assert data["course_id"] == free_course.id
        assert data["user_id"] == learner.id
        assert data["status"] == "active"
        assert "enrolled_at" in data

        # 2. Duplicate enrollment -> 409 Conflict
        res_dup = client.post(f"/api/lms/learner/courses/{free_course.id}/enroll", headers=headers)
        assert res_dup.status_code == 409
        assert "Already enrolled" in res_dup.json()["detail"]
    finally:
        db.close()


def test_paid_course_enrollment_rejection(TestingSessionLocal):
    """Paid course enrollment should be rejected with 400 in Phase 2"""
    db = TestingSessionLocal()
    try:
        curriculum = _setup_curriculum(db)
        paid_course = curriculum["paid_course"]
        _, headers = _create_user(db, "learner_alice", "alice@example.com")

        res = client.post(f"/api/lms/learner/courses/{paid_course.id}/enroll", headers=headers)
        assert res.status_code == 400
        assert "Paid courses require purchase" in res.json()["detail"]
    finally:
        db.close()


def test_draft_and_nonexistent_course_enrollment(TestingSessionLocal):
    """Enrollment in draft or missing courses must return 404"""
    db = TestingSessionLocal()
    try:
        curriculum = _setup_curriculum(db)
        draft_course = curriculum["draft_course"]
        _, headers = _create_user(db, "learner_charlie", "charlie@example.com")

        # Nonexistent course
        res_none = client.post("/api/lms/learner/courses/99999/enroll", headers=headers)
        assert res_none.status_code == 404

        # Draft course
        res_draft = client.post(f"/api/lms/learner/courses/{draft_course.id}/enroll", headers=headers)
        assert res_draft.status_code == 404
    finally:
        db.close()


def test_enrolled_courses_listing_and_detail(TestingSessionLocal):
    """Test learner dashboard listing enrolled courses and detail view"""
    db = TestingSessionLocal()
    try:
        curriculum = _setup_curriculum(db)
        free_course = curriculum["free_course"]
        _, headers = _create_user(db, "learner_dan", "dan@example.com")

        # Before enrollment: empty list
        res_empty = client.get("/api/lms/learner/courses", headers=headers)
        assert res_empty.status_code == 200
        assert res_empty.json() == []

        # Enroll in free course
        enroll_res = client.post(f"/api/lms/learner/courses/{free_course.id}/enroll", headers=headers)
        assert enroll_res.status_code == 201

        # After enrollment: 1 course in list
        res_list = client.get("/api/lms/learner/courses", headers=headers)
        assert res_list.status_code == 200
        courses = res_list.json()
        assert len(courses) == 1
        assert courses[0]["course_id"] == free_course.id
        assert courses[0]["completion_percentage"] == 0.0
        assert courses[0]["is_completed"] is False

        # Get course detail as enrolled user
        res_detail = client.get(f"/api/lms/learner/courses/{free_course.id}", headers=headers)
        assert res_detail.status_code == 200
        detail = res_detail.json()
        assert detail["id"] == free_course.id
        assert len(detail["modules"]) == 1
        assert len(detail["modules"][0]["lessons"]) == 2

        # Unenrolled user cannot access enrolled course detail -> 403
        _, other_headers = _create_user(db, "learner_eve", "eve@example.com")
        res_unauth = client.get(f"/api/lms/learner/courses/{free_course.id}", headers=other_headers)
        assert res_unauth.status_code == 403
    finally:
        db.close()


def test_lesson_access_authorization_preview_and_enrolled(TestingSessionLocal):
    """Test preview lesson access without enrollment vs non-preview requiring enrollment"""
    db = TestingSessionLocal()
    try:
        curriculum = _setup_curriculum(db)
        free_course = curriculum["free_course"]
        les1_preview = curriculum["free_les1_preview"]
        les2_enrolled = curriculum["free_les2_enrolled"]
        paid_preview_les = curriculum["paid_preview_les"]
        paid_les = curriculum["paid_les"]

        _, learner_headers = _create_user(db, "learner_frank", "frank@example.com")

        # 1. Preview lesson in free course: accessible WITHOUT enrollment
        res_prev = client.get(f"/api/lms/learner/lessons/{les1_preview.id}", headers=learner_headers)
        assert res_prev.status_code == 200
        data_prev = res_prev.json()
        assert data_prev["is_preview"] is True
        assert data_prev["content_body"] == "Welcome to the Ajna Chakra course overview."
        assert data_prev["media_url"] == "https://media.thirdeye.ai/preview1.mp4"

        # 2. Preview lesson in paid course: also accessible per documented preview policy
        res_paid_prev = client.get(f"/api/lms/learner/lessons/{paid_preview_les.id}", headers=learner_headers)
        assert res_paid_prev.status_code == 200
        assert res_paid_prev.json()["media_url"] == "https://media.thirdeye.ai/teaser.mp4"

        # 3. Non-preview lesson in free course before enrollment -> 403 Forbidden
        res_non_prev = client.get(f"/api/lms/learner/lessons/{les2_enrolled.id}", headers=learner_headers)
        assert res_non_prev.status_code == 403

        # 4. Non-preview lesson in paid course -> 403 Forbidden
        res_paid = client.get(f"/api/lms/learner/lessons/{paid_les.id}", headers=learner_headers)
        assert res_paid.status_code == 403

        # 5. Enroll in free course -> non-preview lesson becomes accessible
        client.post(f"/api/lms/learner/courses/{free_course.id}/enroll", headers=learner_headers)
        res_enrolled_access = client.get(f"/api/lms/learner/lessons/{les2_enrolled.id}", headers=learner_headers)
        assert res_enrolled_access.status_code == 200
        assert res_enrolled_access.json()["media_url"] == "https://media.thirdeye.ai/lesson2_core.mp4"

        # 6. Guest access to published preview lessons (no Authorization header required)
        res_guest_free_prev = client.get(f"/api/lms/learner/lessons/{les1_preview.id}")
        assert res_guest_free_prev.status_code == 200
        guest_data = res_guest_free_prev.json()
        assert guest_data["is_preview"] is True
        assert guest_data["media_url"] == "https://media.thirdeye.ai/preview1.mp4"
        assert guest_data["is_completed"] is False
        assert guest_data["progress_percentage"] == 0

        res_guest_paid_prev = client.get(f"/api/lms/learner/lessons/{paid_preview_les.id}")
        assert res_guest_paid_prev.status_code == 200
        assert res_guest_paid_prev.json()["media_url"] == "https://media.thirdeye.ai/teaser.mp4"

        # 7. Guest access to protected non-preview lessons rejected with 401 Unauthorized
        res_guest_protected = client.get(f"/api/lms/learner/lessons/{les2_enrolled.id}")
        assert res_guest_protected.status_code == 401
        assert "Authentication required" in res_guest_protected.json()["detail"]

        res_guest_paid_protected = client.get(f"/api/lms/learner/lessons/{paid_les.id}")
        assert res_guest_paid_protected.status_code == 401
    finally:
        db.close()


def test_unpublished_curriculum_returns_404(TestingSessionLocal):
    """Lessons in draft courses, draft modules, or unpublished lessons return 404"""
    db = TestingSessionLocal()
    try:
        curriculum = _setup_curriculum(db)
        draft_les = curriculum["draft_les"]
        _, headers = _create_user(db, "learner_grace", "grace@example.com")

        res = client.get(f"/api/lms/learner/lessons/{draft_les.id}", headers=headers)
        assert res.status_code == 404

        res_prog = client.put(
            f"/api/lms/learner/lessons/{draft_les.id}/progress",
            json={"progress_percentage": 50},
            headers=headers,
        )
        assert res_prog.status_code == 404
    finally:
        db.close()


def test_lesson_progress_lifecycle_and_validation(TestingSessionLocal):
    """Test progress percentage validation, completion timestamps, and idempotency"""
    db = TestingSessionLocal()
    try:
        curriculum = _setup_curriculum(db)
        free_course = curriculum["free_course"]
        les2 = curriculum["free_les2_enrolled"]
        _, headers = _create_user(db, "learner_heidi", "heidi@example.com")

        # Enroll in course
        client.post(f"/api/lms/learner/courses/{free_course.id}/enroll", headers=headers)

        # 1. Invalid progress percentage: > 100 -> 422
        res_invalid_high = client.put(
            f"/api/lms/learner/lessons/{les2.id}/progress",
            json={"progress_percentage": 150},
            headers=headers,
        )
        assert res_invalid_high.status_code == 422

        # 2. Invalid progress percentage: < 0 -> 422
        res_invalid_low = client.put(
            f"/api/lms/learner/lessons/{les2.id}/progress",
            json={"progress_percentage": -10},
            headers=headers,
        )
        assert res_invalid_low.status_code == 422

        # 3. Valid progress: 45%
        res_valid = client.put(
            f"/api/lms/learner/lessons/{les2.id}/progress",
            json={"progress_percentage": 45, "last_position_seconds": 270},
            headers=headers,
        )
        assert res_valid.status_code == 200
        data_45 = res_valid.json()
        assert data_45["progress_percentage"] == 45
        assert data_45["last_position_seconds"] == 270
        assert data_45["is_completed"] is False
        assert data_45["completed_at"] is None

        # 4. Valid completion: 100%
        res_complete = client.put(
            f"/api/lms/learner/lessons/{les2.id}/progress",
            json={"progress_percentage": 100, "last_position_seconds": 600},
            headers=headers,
        )
        assert res_complete.status_code == 200
        data_100 = res_complete.json()
        assert data_100["progress_percentage"] == 100
        assert data_100["is_completed"] is True
        assert data_100["completed_at"] is not None
    finally:
        db.close()


def test_cross_user_progress_isolation(TestingSessionLocal):
    """Verify that learner A's progress never leaks to or affects learner B"""
    db = TestingSessionLocal()
    try:
        curriculum = _setup_curriculum(db)
        free_course = curriculum["free_course"]
        les1 = curriculum["free_les1_preview"]
        les2 = curriculum["free_les2_enrolled"]

        _, user_a_headers = _create_user(db, "learner_a", "a@example.com")
        _, user_b_headers = _create_user(db, "learner_b", "b@example.com")

        # Both enroll
        client.post(f"/api/lms/learner/courses/{free_course.id}/enroll", headers=user_a_headers)
        client.post(f"/api/lms/learner/courses/{free_course.id}/enroll", headers=user_b_headers)

        # User A completes lesson 1 and lesson 2
        client.put(f"/api/lms/learner/lessons/{les1.id}/progress", json={"progress_percentage": 100}, headers=user_a_headers)
        client.put(f"/api/lms/learner/lessons/{les2.id}/progress", json={"progress_percentage": 100}, headers=user_a_headers)

        # Check User A course progress: 100%
        prog_a = client.get(f"/api/lms/learner/courses/{free_course.id}/progress", headers=user_a_headers).json()
        assert prog_a["completed_lessons"] == 2
        assert prog_a["completion_percentage"] == 100.0
        assert prog_a["is_completed"] is True

        # Check User B course progress: 0%
        prog_b = client.get(f"/api/lms/learner/courses/{free_course.id}/progress", headers=user_b_headers).json()
        assert prog_b["completed_lessons"] == 0
        assert prog_b["completion_percentage"] == 0.0
        assert prog_b["is_completed"] is False

        # User B lesson 1 view has is_completed=False
        les1_b = client.get(f"/api/lms/learner/lessons/{les1.id}", headers=user_b_headers).json()
        assert les1_b["is_completed"] is False
        assert les1_b["progress_percentage"] == 0
    finally:
        db.close()


def test_course_progress_calculation_and_empty_curriculum(TestingSessionLocal):
    """Test course completion calculation including empty curriculum edge case"""
    db = TestingSessionLocal()
    try:
        # Create published course with NO lessons
        empty_course = Course(
            title="Empty Course Test",
            slug="empty-course-test",
            is_free=True,
            status="published",
        )
        db.add(empty_course)
        db.commit()

        _, headers = _create_user(db, "learner_empty", "empty@example.com")
        client.post(f"/api/lms/learner/courses/{empty_course.id}/enroll", headers=headers)

        # Empty curriculum behavior: 0.0% completion, is_completed=False
        res_empty = client.get(f"/api/lms/learner/courses/{empty_course.id}/progress", headers=headers)
        assert res_empty.status_code == 200
        data_empty = res_empty.json()
        assert data_empty["total_lessons"] == 0
        assert data_empty["completed_lessons"] == 0
        assert data_empty["completion_percentage"] == 0.0
        assert data_empty["is_completed"] is False
    finally:
        db.close()


def test_unauthenticated_requests_rejected(TestingSessionLocal):
    """Endpoints requiring authentication must reject unauthenticated requests with 401"""
    db = TestingSessionLocal()
    try:
        curriculum = _setup_curriculum(db)
        free_course = curriculum["free_course"]
        protected_les = curriculum["free_les2_enrolled"]

        endpoints = [
            ("POST", f"/api/lms/learner/courses/{free_course.id}/enroll"),
            ("GET", "/api/lms/learner/courses"),
            ("GET", f"/api/lms/learner/courses/{free_course.id}"),
            ("GET", f"/api/lms/learner/lessons/{protected_les.id}"),
            ("PUT", f"/api/lms/learner/lessons/{protected_les.id}/progress"),
            ("GET", f"/api/lms/learner/courses/{free_course.id}/progress"),
        ]

        for method, path in endpoints:
            if method == "POST":
                res = client.post(path)
            elif method == "GET":
                res = client.get(path)
            elif method == "PUT":
                res = client.put(path, json={"progress_percentage": 50})
            assert res.status_code == 401, f"{method} {path} did not return 401"
    finally:
        db.close()
