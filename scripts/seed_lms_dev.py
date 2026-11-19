"""Idempotent Development Seed Script for Third EYE LMS

PROPOSED DEVELOPMENT SEED SCRIPT.
DO NOT EXECUTE AUTOMATICALLY AGAINST ACTIVE OR PRODUCTION DATABASES.

Usage:
    python scripts/seed_lms_dev.py [--apply] [--db-url SQLITE_URL]

Features:
- Idempotent: checks for existing categories, courses, modules, and lessons by slug.
- Distinctly tags development items with clear dev prefixes.
- Seeds 2 categories, 1 free published course with preview & protected lessons,
  and 1 paid published course with preview & protected lessons.
"""

import argparse
import sys
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.course import Course, CourseCategory, CourseModule, Lesson


DEV_CATEGORIES = [
    {
        "slug": "third-eye-ajna-dev",
        "name": "Third Eye & Ajna (Dev)",
        "description": "Foundational practices for third eye awakening and intuitive awareness.",
        "display_order": 1,
        "is_active": True,
    },
    {
        "slug": "pranayama-breath-dev",
        "name": "Sacred Breath & Pranayama (Dev)",
        "description": "Ancient yogic breathing practices for energetic balance.",
        "display_order": 2,
        "is_active": True,
    },
]

DEV_COURSES = [
    {
        "category_slug": "third-eye-ajna-dev",
        "slug": "third-eye-awakening-foundations-dev",
        "title": "Third Eye Awakening Foundations (Dev)",
        "description": "A beginner-friendly immersion into the sacred science of Ajna Chakra meditation.",
        "thumbnail_url": "https://media.thirdeye.ai/dev/thumbnails/course_101.jpg",
        "is_free": True,
        "price_amount": 0,
        "currency": "INR",
        "status": "published",
        "level": "beginner",
        "modules": [
            {
                "title": "Module 1: Opening the Inner Vision",
                "description": "Foundational orientation and daily alignment.",
                "display_order": 1,
                "is_published": True,
                "lessons": [
                    {
                        "title": "Lesson 1: The Geometry of Ajna",
                        "description": "Overview of the sixth chakra and subtle energy lines.",
                        "content_type": "video",
                        "content_body": "Introduction to the sacred energy vortex located between the eyebrows.",
                        "media_url": "https://media.thirdeye.ai/dev/lessons/les_301.mp4",
                        "duration_seconds": 620,
                        "display_order": 1,
                        "is_preview": True,
                        "is_published": True,
                    },
                    {
                        "title": "Lesson 2: Trataka Flame Practice",
                        "description": "Candle flame meditation to develop steady concentration.",
                        "content_type": "video",
                        "content_body": "Sit in a comfortable posture with the candle at eye level...",
                        "media_url": "https://media.thirdeye.ai/dev/lessons/les_302.mp4",
                        "duration_seconds": 900,
                        "display_order": 2,
                        "is_preview": False,
                        "is_published": True,
                    },
                ],
            },
        ],
    },
    {
        "category_slug": "third-eye-ajna-dev",
        "slug": "advanced-inner-sanctuary-mastery-dev",
        "title": "Advanced Inner Sanctuary Mastery (Dev)",
        "description": "Deep meditative absorption and advanced inner light contemplation.",
        "thumbnail_url": "https://media.thirdeye.ai/dev/thumbnails/course_102.jpg",
        "is_free": False,
        "price_amount": 499900,  # in paise
        "currency": "INR",
        "status": "published",
        "level": "advanced",
        "modules": [
            {
                "title": "Module 1: High Vibration Thresholds",
                "description": "Transitioning from sensory awareness to deep meditative absorption.",
                "display_order": 1,
                "is_published": True,
                "lessons": [
                    {
                        "title": "Lesson 1: Threshold Overview (Preview)",
                        "description": "Public teaser for the advanced masterclass.",
                        "content_type": "video",
                        "content_body": "Preview of advanced consciousness states.",
                        "media_url": "https://media.thirdeye.ai/dev/lessons/les_303.mp4",
                        "duration_seconds": 240,
                        "display_order": 1,
                        "is_preview": True,
                        "is_published": True,
                    },
                    {
                        "title": "Lesson 2: Non-Dual Meditation (Protected)",
                        "description": "Protected masterclass for certified learners.",
                        "content_type": "video",
                        "content_body": "Protected non-dual instructions.",
                        "media_url": "https://media.thirdeye.ai/dev/lessons/les_304.mp4",
                        "duration_seconds": 1500,
                        "display_order": 2,
                        "is_preview": False,
                        "is_published": True,
                    },
                ],
            },
        ],
    },
]


def seed_database(db_url: str, apply_changes: bool = False):
    """Seed categories and courses idempotently into target database"""
    print(f"Target Database URL: {db_url}")
    if not apply_changes:
        print("[DRY RUN] No changes will be written. Pass --apply to persist changes.")
        return

    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # 1. Seed categories
        category_map = {}
        for cat_data in DEV_CATEGORIES:
            slug = cat_data["slug"]
            cat = session.query(CourseCategory).filter(CourseCategory.slug == slug).first()
            if not cat:
                cat = CourseCategory(**cat_data)
                session.add(cat)
                session.flush()
                print(f"[CREATED] Category: {cat.name} ({slug})")
            else:
                print(f"[EXISTS] Category: {cat.name} ({slug})")
            category_map[slug] = cat.id

        # 2. Seed courses, modules, lessons
        for course_data in DEV_COURSES:
            c_slug = course_data["slug"]
            modules_data = course_data.get("modules", [])
            cat_id = category_map.get(course_data["category_slug"])

            course = session.query(Course).filter(Course.slug == c_slug).first()
            if not course:
                course = Course(
                    category_id=cat_id,
                    slug=c_slug,
                    title=course_data["title"],
                    description=course_data["description"],
                    thumbnail_url=course_data["thumbnail_url"],
                    is_free=course_data["is_free"],
                    price_amount=course_data["price_amount"],
                    currency=course_data["currency"],
                    status=course_data["status"],
                    level=course_data["level"],
                )
                session.add(course)
                session.flush()
                print(f"[CREATED] Course: {course.title} ({c_slug})")
            else:
                print(f"[EXISTS] Course: {course.title} ({c_slug})")

            # Modules
            for mod_data in modules_data:
                lessons_data = mod_data.get("lessons", [])
                mod = (
                    session.query(CourseModule)
                    .filter(
                        CourseModule.course_id == course.id,
                        CourseModule.title == mod_data["title"],
                    )
                    .first()
                )
                if not mod:
                    mod = CourseModule(
                        course_id=course.id,
                        title=mod_data["title"],
                        description=mod_data.get("description"),
                        display_order=mod_data.get("display_order", 1),
                        is_published=mod_data.get("is_published", True),
                    )
                    session.add(mod)
                    session.flush()
                    print(f"  [CREATED] Module: {mod.title}")
                else:
                    print(f"  [EXISTS] Module: {mod.title}")

                # Lessons
                for les_data in lessons_data:
                    les = (
                        session.query(Lesson)
                        .filter(
                            Lesson.module_id == mod.id,
                            Lesson.title == les_data["title"],
                        )
                        .first()
                    )
                    if not les:
                        les = Lesson(
                            module_id=mod.id,
                            title=les_data["title"],
                            description=les_data.get("description"),
                            content_type=les_data.get("content_type", "video"),
                            content_body=les_data.get("content_body"),
                            media_url=les_data.get("media_url"),
                            duration_seconds=les_data.get("duration_seconds", 0),
                            display_order=les_data.get("display_order", 1),
                            is_preview=les_data.get("is_preview", False),
                            is_published=les_data.get("is_published", True),
                        )
                        session.add(les)
                        print(f"    [CREATED] Lesson: {les.title} (preview={les.is_preview})")
                    else:
                        print(f"    [EXISTS] Lesson: {les.title}")

        session.commit()
        print("\n[SUCCESS] Idempotent development seed completed successfully.")
    except Exception as e:
        session.rollback()
        print(f"\n[ERROR] Seed aborted: {e}", file=sys.stderr)
        raise
    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed development LMS data")
    parser.add_argument("--apply", action="store_true", help="Apply changes to the database (defaults to dry-run)")
    parser.add_argument("--db-url", type=str, default="", help="Target database URL")
    args = parser.parse_args()

    target_url = args.db_url
    if not target_url:
        from app.core.config import settings
        target_url = settings.DATABASE_URL

    seed_database(target_url, apply_changes=args.apply)

