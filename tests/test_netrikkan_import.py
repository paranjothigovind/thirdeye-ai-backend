"""Tests for the idempotent Netrikkan course import and the catalog API it feeds."""
import importlib.util
import json
import os

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.course import Course, CourseEnrollment, CourseModule, Lesson, UserLessonProgress

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "import_netrikkan_course.py")
spec = importlib.util.spec_from_file_location("import_netrikkan_course", SCRIPT)
importer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(importer)

client = TestClient(app)
SOURCE = importer.load_source()
EXTERNAL_ID = SOURCE["course"]["external_id"]


@pytest.fixture
def db(TestingSessionLocal):
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        course = session.query(Course).filter(Course.external_id == EXTERNAL_ID).first()
        if course:
            session.delete(course)
        for other in session.query(Course).filter(Course.slug == "unrelated-course").all():
            session.delete(other)
        session.commit()
        session.close()


def _import(db):
    stats = importer.import_course(db, SOURCE)
    db.commit()
    return stats


def test_import_creates_expected_structure(db):
    stats = _import(db)
    assert stats["courses_created"] == 1
    assert importer.count_course(db, EXTERNAL_ID) == (1, 15, 17)

    course = db.query(Course).filter(Course.external_id == EXTERNAL_ID).one()
    assert course.title == "நெற்றிக்கண் தியானம்"
    assert (course.price_amount, course.currency, course.status) == (99900, "INR", "published")

    modules = db.query(CourseModule).filter_by(course_id=course.id).order_by(CourseModule.display_order).all()
    assert [m.display_order for m in modules] == list(range(1, 16))
    expected_lessons = [(c["title"], l) for c in SOURCE["chapters"] for l in c["lessons"]]
    actual = [
        (m.title, les)
        for m in modules
        for les in db.query(Lesson).filter_by(module_id=m.id).order_by(Lesson.display_order)
    ]
    assert len(actual) == len(expected_lessons) == 17
    for (chapter_title, src), (module_title, les) in zip(expected_lessons, actual):
        assert module_title == chapter_title
        assert les.title == src["title"]
        assert les.media_url == src["youtube"]
        assert les.is_preview == bool(src["include_in_preview"])
        assert les.content_type == "video"
    assert sum(1 for _, les in actual if les.is_preview) == 1


def test_sixth_chapter_uses_title_not_stale_name(db):
    _import(db)
    course = db.query(Course).filter(Course.external_id == EXTERNAL_ID).one()
    sixth = db.query(CourseModule).filter_by(course_id=course.id, display_order=6).one()
    assert sixth.title == "6️⃣ பிரபஞ்ச ஆற்றலை உடலில் நிரப்பும் பயிற்சி"
    assert "முதுகுத்தண்டு" not in sixth.title


def test_import_is_idempotent_and_preserves_unrelated_data(db):
    other = Course(slug="unrelated-course", title="Unrelated", status="published")
    db.add(other)
    db.commit()
    _import(db)
    snapshot = (db.query(Course).count(), db.query(CourseModule).count(), db.query(Lesson).count(),
                db.query(CourseEnrollment).count(), db.query(UserLessonProgress).count())
    stats = _import(db)
    assert stats == {"courses_created": 0, "chapters_created": 0, "chapters_updated": 0,
                     "lessons_created": 0, "lessons_updated": 0}
    assert snapshot == (db.query(Course).count(), db.query(CourseModule).count(),
                        db.query(Lesson).count(), db.query(CourseEnrollment).count(),
                        db.query(UserLessonProgress).count())
    assert db.query(Course).filter_by(slug="unrelated-course").count() == 1


def test_reimport_repairs_drift_without_duplicates(db):
    _import(db)
    lesson = db.query(Lesson).join(CourseModule).join(Course).filter(Course.external_id == EXTERNAL_ID).first()
    lesson.media_url = "https://example.com/changed"
    db.commit()
    stats = _import(db)
    assert stats["lessons_updated"] == 1
    assert importer.count_course(db, EXTERNAL_ID) == (1, 15, 17)


def test_import_refuses_to_adopt_conflicting_slug(db):
    db.add(Course(slug=SOURCE["course"]["slug"], title="Someone else's course", status="draft"))
    db.commit()
    try:
        with pytest.raises(RuntimeError, match="refusing to adopt"):
            importer.import_course(db, SOURCE)
    finally:
        db.rollback()
        db.query(Course).filter(Course.slug == SOURCE["course"]["slug"]).delete()
        db.commit()


def test_catalog_api_returns_course_in_order(db):
    _import(db)
    listing = client.get("/api/lms/catalog/courses", params={"search": "நெற்றிக்கண்"}).json()
    assert [c["title"] for c in listing["items"]] == ["நெற்றிக்கண் தியானம்"]

    detail = client.get(f"/api/lms/catalog/courses/{SOURCE['course']['slug']}").json()
    assert [m["display_order"] for m in detail["modules"]] == list(range(1, 16))
    assert sum(len(m["lessons"]) for m in detail["modules"]) == 17
    assert [len(m["lessons"]) for m in detail["modules"]][13] == 3
    for module in detail["modules"]:
        assert [l["display_order"] for l in module["lessons"]] == sorted(l["display_order"] for l in module["lessons"])
        for les in module["lessons"]:
            assert "media_url" not in les  # protected URL is never in the public syllabus


def test_lesson_by_id_preview_open_protected_locked(db):
    _import(db)
    detail = client.get(f"/api/lms/catalog/courses/{SOURCE['course']['slug']}").json()
    lessons = [l for m in detail["modules"] for l in m["lessons"]]
    preview = next(l for l in lessons if l["is_preview"])
    protected = next(l for l in lessons if not l["is_preview"])

    ok = client.get(f"/api/lms/learner/lessons/{preview['id']}")
    assert ok.status_code == 200
    assert ok.json()["media_url"] == "https://www.youtube.com/watch?v=96I1bCQej-w"

    locked = client.get(f"/api/lms/learner/lessons/{protected['id']}")
    assert locked.status_code == 401
    assert "youtube" not in locked.text


def test_source_data_has_no_progress_or_lock_fields():
    text = json.dumps(SOURCE)
    assert "is_complete" not in text and "is_locked" not in text


def _user_headers(db, name):
    from app.core.auth import create_access_token, get_password_hash
    from app.models.user import User
    user = User(username=name, email=f"{name}@example.com",
                hashed_password=get_password_hash("Secret123!"), is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user, {"Authorization": f"Bearer {create_access_token({'sub': user.username})}"}


def test_paid_lessons_stay_protected_for_authenticated_users(db):
    from app.models.user import User
    _import(db)
    course = db.query(Course).filter(Course.external_id == EXTERNAL_ID).one()
    lessons = (db.query(Lesson).join(CourseModule).filter(CourseModule.course_id == course.id).all())
    protected = [l for l in lessons if not l.is_preview]
    assert len(protected) == 16

    plain, plain_headers = _user_headers(db, "nk_plain")
    enrolled, enrolled_headers = _user_headers(db, "nk_enrolled")
    db.add(CourseEnrollment(user_id=enrolled.id, course_id=course.id, status="active"))
    db.commit()
    try:
        for les in protected:
            anon = client.get(f"/api/lms/learner/lessons/{les.id}")
            assert anon.status_code == 401
            for headers in (plain_headers, enrolled_headers):  # no payment path exists
                res = client.get(f"/api/lms/learner/lessons/{les.id}", headers=headers)
                assert res.status_code == 403
                assert "youtube" not in res.text and les.media_url not in res.text
    finally:
        db.query(CourseEnrollment).filter_by(course_id=course.id).delete()
        db.query(User).filter(User.username.in_(["nk_plain", "nk_enrolled"])).delete(synchronize_session=False)
        db.commit()


def test_no_youtube_url_in_public_responses_except_preview_lesson(db):
    _import(db)
    for path in ("/api/lms/catalog/courses", f"/api/lms/catalog/courses/{SOURCE['course']['slug']}"):
        assert "youtube" not in client.get(path).text.lower()


def test_external_id_is_unique(db):
    from sqlalchemy.exc import IntegrityError
    _import(db)
    db.add(Course(slug="dup-external", title="Dup", external_id=EXTERNAL_ID))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
