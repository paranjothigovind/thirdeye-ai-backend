"""Tests for LMS Course Catalog and Admin APIs"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.auth import get_password_hash, create_access_token
from app.models.user import User
from app.models.course import Course, CourseCategory, CourseModule, Lesson

client = TestClient(app)


def _create_user(db, username: str, email: str, is_superuser: bool = False) -> tuple[User, dict]:
    """Helper to create a user and return (user, auth_headers)"""
    user = User(
        username=username,
        email=email,
        hashed_password=get_password_hash("Secret123!"),
        is_active=True,
        is_superuser=is_superuser,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token({"sub": user.username})
    return user, {"Authorization": f"Bearer {token}"}


def test_admin_auth_guards(TestingSessionLocal):
    """Verify 401 for unauthenticated and 403 for non-superuser requests"""
    db = TestingSessionLocal()
    try:
        _, user_headers = _create_user(db, "normal_learner", "learner@example.com", is_superuser=False)
        _, admin_headers = _create_user(db, "super_admin", "admin@example.com", is_superuser=True)

        course_payload = {
            "title": "Third Eye Awakening",
            "slug": "third-eye-awakening",
            "is_free": True,
        }

        # 1. Unauthenticated request -> 401
        res_no_auth = client.post("/api/lms/admin/courses", json=course_payload)
        assert res_no_auth.status_code == 401

        # 2. Authenticated non-admin request -> 403
        res_user = client.post("/api/lms/admin/courses", json=course_payload, headers=user_headers)
        assert res_user.status_code == 403
        assert res_user.json()["detail"] == "Admin privileges required"

        # 3. Superuser request -> 201 Created
        res_admin = client.post("/api/lms/admin/courses", json=course_payload, headers=admin_headers)
        assert res_admin.status_code == 201
        data = res_admin.json()
        assert data["slug"] == "third-eye-awakening"
        assert data["status"] == "draft"
    finally:
        db.close()


def test_admin_course_crud_and_slug_validation(TestingSessionLocal):
    """Verify course creation, updating, and duplicate slug validation"""
    db = TestingSessionLocal()
    try:
        _, admin_headers = _create_user(db, "catalog_admin", "catalog_admin@example.com", is_superuser=True)

        # 1. Create category
        cat = CourseCategory(name="Meditation Basics", slug="meditation-basics", display_order=1, is_active=True)
        db.add(cat)
        db.commit()
        db.refresh(cat)

        # 2. Create Course
        course_payload = {
            "title": "Chakra Fundamentals",
            "slug": "chakra-fundamentals",
            "description": "Introductory guide to seven chakras",
            "category_id": cat.id,
            "is_free": False,
            "price_amount": 199900,
            "currency": "INR",
            "level": "beginner",
        }
        res = client.post("/api/lms/admin/courses", json=course_payload, headers=admin_headers)
        assert res.status_code == 201
        course_data = res.json()
        course_id = course_data["id"]

        # 3. Duplicate slug validation -> 400
        dup_res = client.post("/api/lms/admin/courses", json=course_payload, headers=admin_headers)
        assert dup_res.status_code == 400
        assert "already exists" in dup_res.json()["detail"]

        # 4. Update Course
        update_payload = {
            "title": "Chakra Fundamentals (Updated)",
            "price_amount": 149900,
        }
        update_res = client.put(f"/api/lms/admin/courses/{course_id}", json=update_payload, headers=admin_headers)
        assert update_res.status_code == 200
        assert update_res.json()["title"] == "Chakra Fundamentals (Updated)"
        assert update_res.json()["price_amount"] == 149900

        # 5. Update nonexistent course -> 404
        missing_res = client.put("/api/lms/admin/courses/99999", json=update_payload, headers=admin_headers)
        assert missing_res.status_code == 404
    finally:
        db.close()


def test_admin_curriculum_authoring_and_publishing(TestingSessionLocal):
    """Verify module and lesson authoring and publishing workflow"""
    db = TestingSessionLocal()
    try:
        _, admin_headers = _create_user(db, "author_admin", "author@example.com", is_superuser=True)

        # 1. Create Course
        res_c = client.post(
            "/api/lms/admin/courses",
            json={"title": "Pranayama Mastery", "slug": "pranayama-mastery", "is_free": True},
            headers=admin_headers,
        )
        assert res_c.status_code == 201
        course_id = res_c.json()["id"]

        # 2. Create Module
        res_m = client.post(
            f"/api/lms/admin/courses/{course_id}/modules",
            json={"title": "Module 1: Breathwork Foundations", "display_order": 1},
            headers=admin_headers,
        )
        assert res_m.status_code == 201
        module_id = res_m.json()["id"]

        # 3. Create Lesson with protected media and body
        res_l = client.post(
            f"/api/lms/admin/modules/{module_id}/lessons",
            json={
                "title": "Lesson 1.1: Nadi Shodhana",
                "content_type": "video",
                "media_url": "https://secure-blob.internal/videos/nadi_shodhana.mp4",
                "content_body": "Detailed private instructor transcript.",
                "duration_seconds": 600,
                "display_order": 1,
                "is_preview": True,
            },
            headers=admin_headers,
        )
        assert res_l.status_code == 201
        lesson_data = res_l.json()
        assert lesson_data["media_url"] == "https://secure-blob.internal/videos/nadi_shodhana.mp4"
        assert lesson_data["is_preview"] is True
        lesson_id = lesson_data["id"]

        # 4. Update Lesson
        res_l_update = client.put(
            f"/api/lms/admin/lessons/{lesson_id}",
            json={"duration_seconds": 720},
            headers=admin_headers,
        )
        assert res_l_update.status_code == 200
        assert res_l_update.json()["duration_seconds"] == 720

        # 5. Course initially in draft -> publish it
        pub_res = client.post(f"/api/lms/admin/courses/{course_id}/publish", headers=admin_headers)
        assert pub_res.status_code == 200
        assert pub_res.json()["status"] == "published"
    finally:
        db.close()


def test_public_catalog_filtering_and_pagination(TestingSessionLocal):
    """Verify public catalog listing, category filtering, search, and pagination"""
    db = TestingSessionLocal()
    try:
        _, admin_headers = _create_user(db, "seeder_admin", "seeder@example.com", is_superuser=True)

        # Categories: one active, one inactive
        cat_active = CourseCategory(name="Meditation", slug="meditation", is_active=True, display_order=1)
        cat_inactive = CourseCategory(name="Archived", slug="archived", is_active=False, display_order=2)
        db.add_all([cat_active, cat_inactive])
        db.commit()

        # Public categories endpoint should only return active
        res_cats = client.get("/api/lms/catalog/categories")
        assert res_cats.status_code == 200
        cat_slugs = [c["slug"] for c in res_cats.json()]
        assert "meditation" in cat_slugs
        assert "archived" not in cat_slugs

        # Seed courses:
        # 1. Free, published, beginner
        c1 = Course(
            title="Mindful Breathing",
            slug="mindful-breathing",
            description="Learn breath awareness",
            category_id=cat_active.id,
            is_free=True,
            level="beginner",
            status="published",
        )
        # 2. Paid, published, intermediate
        c2 = Course(
            title="Deep Meditation",
            slug="deep-meditation",
            description="Advance your concentration",
            category_id=cat_active.id,
            is_free=False,
            price_amount=49900,
            level="intermediate",
            status="published",
        )
        # 3. Draft (unpublished)
        c3 = Course(
            title="Secret Techniques",
            slug="secret-techniques",
            description="Draft course",
            category_id=cat_active.id,
            is_free=True,
            level="advanced",
            status="draft",
        )
        db.add_all([c1, c2, c3])
        db.commit()

        # 1. Listing should exclude draft course c3
        list_res = client.get("/api/lms/catalog/courses")
        assert list_res.status_code == 200
        data = list_res.json()
        assert data["total"] == 2
        slugs = [c["slug"] for c in data["items"]]
        assert "mindful-breathing" in slugs
        assert "deep-meditation" in slugs
        assert "secret-techniques" not in slugs

        # 2. Filter by free status
        free_res = client.get("/api/lms/catalog/courses?is_free=true")
        assert free_res.status_code == 200
        free_data = free_res.json()
        assert free_data["total"] == 1
        assert free_data["items"][0]["slug"] == "mindful-breathing"

        # 3. Filter by level
        level_res = client.get("/api/lms/catalog/courses?level=intermediate")
        assert level_res.status_code == 200
        assert level_res.json()["items"][0]["slug"] == "deep-meditation"

        # 4. Search filter
        search_res = client.get("/api/lms/catalog/courses?search=breathing")
        assert search_res.status_code == 200
        assert len(search_res.json()["items"]) == 1
        assert search_res.json()["items"][0]["slug"] == "mindful-breathing"

        # 5. Pagination
        page_res = client.get("/api/lms/catalog/courses?limit=1&page=1")
        assert page_res.status_code == 200
        page_data = page_res.json()
        assert len(page_data["items"]) == 1
        assert page_data["pages"] == 2
        assert page_data["total"] == 2
    finally:
        db.close()


def test_public_course_detail_and_protected_media_masking(TestingSessionLocal):
    """Verify course detail retrieval and ensure protected media URLs are never exposed in public catalog"""
    db = TestingSessionLocal()
    try:
        # Create published course with module and lesson
        course = Course(
            title="Trataka Gazing Meditation",
            slug="trataka-gazing-meditation",
            description="Ancient technique of fixed gaze",
            is_free=False,
            price_amount=29900,
            status="published",
        )
        db.add(course)
        db.commit()
        db.refresh(course)

        mod = CourseModule(course_id=course.id, title="Module 1: Candle Practice", display_order=1, is_published=True)
        db.add(mod)
        db.commit()
        db.refresh(mod)

        lesson = Lesson(
            module_id=mod.id,
            title="1.1 Setting up your candle",
            description="Proper candle distance and eye level",
            content_type="video",
            media_url="https://secret-cdn.example.com/protected/lesson1.mp4",
            content_body="Confidential step-by-step instructions.",
            duration_seconds=420,
            display_order=1,
            is_preview=True,
            is_published=True,
        )
        db.add(lesson)
        db.commit()

        # Also create an unpublished draft course
        draft_course = Course(title="Unpublished Esoteric Secrets", slug="unpub-secrets", status="draft")
        db.add(draft_course)
        db.commit()

        # 1. Retrieve published course by slug
        res_slug = client.get("/api/lms/catalog/courses/trataka-gazing-meditation")
        assert res_slug.status_code == 200
        detail = res_slug.json()
        assert detail["title"] == "Trataka Gazing Meditation"
        assert len(detail["modules"]) == 1
        public_lessons = detail["modules"][0]["lessons"]
        assert len(public_lessons) == 1
        l = public_lessons[0]
        assert l["title"] == "1.1 Setting up your candle"
        assert l["is_preview"] is True

        # CRITICAL SECURITY CHECK: Protected fields must NOT be present in public response
        assert "media_url" not in l
        assert "content_body" not in l

        # 2. Retrieve by numeric ID
        res_id = client.get(f"/api/lms/catalog/courses/{course.id}")
        assert res_id.status_code == 200
        assert res_id.json()["slug"] == "trataka-gazing-meditation"

        # 3. Draft course retrieval should return 404 for public users
        res_draft = client.get(f"/api/lms/catalog/courses/{draft_course.id}")
        assert res_draft.status_code == 404

        # 4. Nonexistent slug should return 404
        res_missing = client.get("/api/lms/catalog/courses/does-not-exist")
        assert res_missing.status_code == 404
    finally:
        db.close()


def test_admin_endpoint_authorization_matrix(TestingSessionLocal):
    """Verify that EVERY admin endpoint rejects unauthenticated (401) and non-superuser (403) requests"""
    db = TestingSessionLocal()
    try:
        _, user_headers = _create_user(db, "unprivileged_user", "unprivileged@example.com", is_superuser=False)

        endpoints = [
            ("GET", "/api/lms/admin/courses", None),
            ("POST", "/api/lms/admin/courses", {"title": "X", "is_free": True}),
            ("PUT", "/api/lms/admin/courses/1", {"title": "X"}),
            ("POST", "/api/lms/admin/courses/1/modules", {"title": "M1"}),
            ("POST", "/api/lms/admin/modules/1/lessons", {"title": "L1"}),
            ("PUT", "/api/lms/admin/lessons/1", {"title": "L1"}),
            ("POST", "/api/lms/admin/courses/1/publish", None),
        ]

        for method, url, payload in endpoints:
            # 1. Unauthenticated -> 401
            if method == "GET":
                res_unauth = client.get(url)
            elif method == "POST":
                res_unauth = client.post(url, json=payload or {})
            elif method == "PUT":
                res_unauth = client.put(url, json=payload or {})
            assert res_unauth.status_code == 401, f"{method} {url} expected 401 for unauthenticated, got {res_unauth.status_code}"

            # 2. Non-superuser -> 403
            if method == "GET":
                res_user = client.get(url, headers=user_headers)
            elif method == "POST":
                res_user = client.post(url, json=payload or {}, headers=user_headers)
            elif method == "PUT":
                res_user = client.put(url, json=payload or {}, headers=user_headers)
            assert res_user.status_code == 403, f"{method} {url} expected 403 for non-superuser, got {res_user.status_code}"
    finally:
        db.close()


def test_invalid_price_and_category_handling(TestingSessionLocal):
    """Verify validation for paid course pricing and invalid category references"""
    db = TestingSessionLocal()
    try:
        _, admin_headers = _create_user(db, "price_admin", "price_admin@example.com", is_superuser=True)

        # 1. Paid course with price_amount = None -> 400
        res1 = client.post(
            "/api/lms/admin/courses",
            json={"title": "Paid Course No Price", "is_free": False},
            headers=admin_headers,
        )
        assert res1.status_code == 400
        assert "price_amount greater than zero" in res1.json()["detail"]

        # 2. Paid course with price_amount = 0 -> 400
        res2 = client.post(
            "/api/lms/admin/courses",
            json={"title": "Paid Course Zero Price", "is_free": False, "price_amount": 0},
            headers=admin_headers,
        )
        assert res2.status_code == 400
        assert "price_amount greater than zero" in res2.json()["detail"]

        # 3. Create valid free course, then attempt to update to paid with zero price -> 400
        res_valid = client.post(
            "/api/lms/admin/courses",
            json={"title": "Valid Free Course", "is_free": True},
            headers=admin_headers,
        )
        assert res_valid.status_code == 201
        course_id = res_valid.json()["id"]

        res_update_invalid = client.put(
            f"/api/lms/admin/courses/{course_id}",
            json={"is_free": False, "price_amount": 0},
            headers=admin_headers,
        )
        assert res_update_invalid.status_code == 400
        assert "price_amount greater than zero" in res_update_invalid.json()["detail"]

        # 4. Invalid category ID -> 400
        res_bad_cat = client.post(
            "/api/lms/admin/courses",
            json={"title": "Course Bad Category", "is_free": True, "category_id": 99999},
            headers=admin_headers,
        )
        assert res_bad_cat.status_code == 400
        assert "Category ID 99999 not found" in res_bad_cat.json()["detail"]
    finally:
        db.close()


def test_publishing_validation_rules(TestingSessionLocal):
    """Verify sensible publishing rules: cannot publish course without published curriculum"""
    db = TestingSessionLocal()
    try:
        _, admin_headers = _create_user(db, "pub_admin", "pub_admin@example.com", is_superuser=True)

        # 1. Create empty course
        res = client.post(
            "/api/lms/admin/courses",
            json={"title": "Empty Course Draft", "is_free": True},
            headers=admin_headers,
        )
        course_id = res.json()["id"]

        # 2. Attempt to publish empty course -> 400
        res_pub_empty = client.post(f"/api/lms/admin/courses/{course_id}/publish", headers=admin_headers)
        assert res_pub_empty.status_code == 400
        assert "Cannot publish a course without at least one published module and lesson" in res_pub_empty.json()["detail"]

        # 3. Add module with unpublished lesson
        res_mod = client.post(
            f"/api/lms/admin/courses/{course_id}/modules",
            json={"title": "Module 1", "is_published": True},
            headers=admin_headers,
        )
        module_id = res_mod.json()["id"]

        client.post(
            f"/api/lms/admin/modules/{module_id}/lessons",
            json={"title": "Draft Lesson", "is_published": False},
            headers=admin_headers,
        )

        # Attempting to publish when lesson is unpublished -> 400
        res_pub_unpub_lesson = client.post(f"/api/lms/admin/courses/{course_id}/publish", headers=admin_headers)
        assert res_pub_unpub_lesson.status_code == 400

        # 4. Add published lesson -> now publishing succeeds -> 200
        client.post(
            f"/api/lms/admin/modules/{module_id}/lessons",
            json={"title": "Published Lesson", "is_published": True},
            headers=admin_headers,
        )

        res_pub_success = client.post(f"/api/lms/admin/courses/{course_id}/publish", headers=admin_headers)
        assert res_pub_success.status_code == 200
        assert res_pub_success.json()["status"] == "published"
    finally:
        db.close()


def test_unpublished_curriculum_exclusion_in_catalog(TestingSessionLocal):
    """Verify that unpublished modules and lessons are never exposed in public course detail"""
    db = TestingSessionLocal()
    try:
        # Create published course
        course = Course(
            title="Mindfulness In Depth",
            slug="mindfulness-in-depth",
            is_free=True,
            status="published",
        )
        db.add(course)
        db.commit()
        db.refresh(course)

        # Module 1: Published, contains 1 published lesson and 1 draft lesson
        m1 = CourseModule(course_id=course.id, title="Published Module", display_order=1, is_published=True)
        # Module 2: Unpublished
        m2 = CourseModule(course_id=course.id, title="Secret Unpublished Module", display_order=2, is_published=False)
        db.add_all([m1, m2])
        db.commit()
        db.refresh(m1)
        db.refresh(m2)

        l1 = Lesson(module_id=m1.id, title="Public Lesson 1", display_order=1, is_published=True)
        l2 = Lesson(module_id=m1.id, title="Hidden Draft Lesson 2", display_order=2, is_published=False)
        l3 = Lesson(module_id=m2.id, title="Hidden Module Lesson 3", display_order=1, is_published=True)
        db.add_all([l1, l2, l3])
        db.commit()

        # Query public course detail
        res = client.get(f"/api/lms/catalog/courses/{course.slug}")
        assert res.status_code == 200
        data = res.json()

        # Only published module m1 should be in modules
        modules = data["modules"]
        assert len(modules) == 1
        assert modules[0]["title"] == "Published Module"

        # Only published lesson l1 should be in lessons
        lessons = modules[0]["lessons"]
        assert len(lessons) == 1
        assert lessons[0]["title"] == "Public Lesson 1"
        assert all(lesson["title"] != "Hidden Draft Lesson 2" for lesson in lessons)
    finally:
        db.close()

