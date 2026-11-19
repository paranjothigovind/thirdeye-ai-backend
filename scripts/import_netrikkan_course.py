"""Idempotent import of the Netrikkan LMS course (chapters + YouTube lessons).

Source: scripts/data/netrikkan_course.json (trimmed export of the course).

Mapping onto the existing LMS tables:
    course   -> courses        (external_id is the stable import key)
    chapter  -> course_modules (idx -> display_order)
    lesson   -> lessons        (YouTube URL -> media_url, order in chapter -> display_order,
                                include_in_preview -> is_preview, content_type "video")

Safety:
- Default is a DRY RUN (everything is rolled back). Pass --apply to persist.
- Matches rows by natural keys, so re-running never duplicates:
  course by external_id, chapter by (course, position), lesson by (chapter, position).
- Existing chapters/lessons are synced to the source; nothing is deleted.
- Unrelated courses, enrollments and learner progress are never touched.
- Course description/thumbnail/price are set only when the course is first created,
  so later admin edits are preserved.

Usage:
    python scripts/import_netrikkan_course.py [--apply] [--db-url URL]
"""
import argparse
import json
import os
import re
import sys
from typing import Dict, Tuple

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BACKEND_DIR)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.course import Course, CourseModule, Lesson

DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "netrikkan_course.json")
YOUTUBE_RE = re.compile(r"^https://www\.youtube\.com/watch\?v=[A-Za-z0-9_-]{11}$")


def load_source(path: str = DATA_FILE) -> dict:
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)

    positions = [chapter["idx"] for chapter in data["chapters"]]
    if positions != sorted(set(positions)):
        raise ValueError("Chapter idx values must be unique and ascending")
    for chapter in data["chapters"]:
        if not chapter["title"].strip() or not chapter["lessons"]:
            raise ValueError(f"Chapter {chapter['idx']} needs a title and at least one lesson")
        for lesson in chapter["lessons"]:
            if not YOUTUBE_RE.match(lesson["youtube"]):
                raise ValueError(f"Unexpected YouTube URL in chapter {chapter['idx']}: {lesson['youtube']}")
    return data


def import_course(session, data: dict) -> Dict[str, int]:
    """Create or sync the course. Returns counters; caller commits or rolls back."""
    spec = data["course"]
    stats = {"courses_created": 0, "chapters_created": 0, "chapters_updated": 0,
             "lessons_created": 0, "lessons_updated": 0}

    course = session.query(Course).filter(Course.external_id == spec["external_id"]).first()
    if course is None:
        clash = session.query(Course).filter(Course.slug == spec["slug"]).first()
        if clash is not None:
            raise RuntimeError(
                f"Slug '{spec['slug']}' already belongs to course id={clash.id} "
                f"(external_id={clash.external_id!r}); refusing to adopt or overwrite it"
            )
        course = Course(
            external_id=spec["external_id"],
            slug=spec["slug"],
            title=spec["title"],
            description=spec.get("description"),
            thumbnail_url=spec.get("thumbnail_url"),
            is_free=spec["price"] == 0,
            price_amount=int(spec["price"]) * 100,  # stored in minor units (paise)
            currency=spec["currency"],
            status="published" if spec["published"] else "draft",
            level="all_levels",
        )
        session.add(course)
        session.flush()
        stats["courses_created"] = 1

    for chapter_spec in data["chapters"]:
        module = (
            session.query(CourseModule)
            .filter(CourseModule.course_id == course.id,
                    CourseModule.display_order == chapter_spec["idx"])
            .first()
        )
        if module is None:
            module = CourseModule(course_id=course.id, title=chapter_spec["title"],
                                  display_order=chapter_spec["idx"], is_published=True)
            session.add(module)
            session.flush()
            stats["chapters_created"] += 1
        elif module.title != chapter_spec["title"]:
            module.title = chapter_spec["title"]
            stats["chapters_updated"] += 1

        for position, lesson_spec in enumerate(chapter_spec["lessons"], start=1):
            wanted = {
                "title": lesson_spec["title"],
                "media_url": lesson_spec["youtube"],
                "is_preview": bool(lesson_spec["include_in_preview"]),
                "content_type": "video",
            }
            lesson = (
                session.query(Lesson)
                .filter(Lesson.module_id == module.id, Lesson.display_order == position)
                .first()
            )
            if lesson is None:
                session.add(Lesson(module_id=module.id, display_order=position,
                                   is_published=True, **wanted))
                stats["lessons_created"] += 1
            elif any(getattr(lesson, key) != value for key, value in wanted.items()):
                for key, value in wanted.items():
                    setattr(lesson, key, value)
                stats["lessons_updated"] += 1

    session.flush()
    return stats


def count_course(session, external_id: str) -> Tuple[int, int, int]:
    course = session.query(Course).filter(Course.external_id == external_id).first()
    if course is None:
        return 0, 0, 0
    modules = session.query(CourseModule).filter(CourseModule.course_id == course.id)
    lessons = (session.query(Lesson).join(CourseModule, Lesson.module_id == CourseModule.id)
               .filter(CourseModule.course_id == course.id))
    return 1, modules.count(), lessons.count()


def main() -> None:
    parser = argparse.ArgumentParser(description="Import the Netrikkan LMS course")
    parser.add_argument("--apply", action="store_true", help="Persist changes (default is a dry run)")
    parser.add_argument("--db-url", default="", help="Target database URL (default: DATABASE_URL setting)")
    args = parser.parse_args()

    db_url = args.db_url
    if not db_url:
        from app.core.config import settings
        db_url = settings.DATABASE_URL

    data = load_source()
    engine = create_engine(db_url)
    session = sessionmaker(bind=engine)()
    try:
        stats = import_course(session, data)
        courses, chapters, lessons = count_course(session, data["course"]["external_id"])
        print(f"Changes: {stats}")
        print(f"Course now has: courses={courses} chapters={chapters} lessons={lessons}")
        if args.apply:
            session.commit()
            print("[APPLIED] Import committed.")
        else:
            session.rollback()
            print("[DRY RUN] Rolled back. Pass --apply to persist.")
    except Exception as error:
        session.rollback()
        print(f"[ERROR] Import aborted, nothing written: {error}", file=sys.stderr)
        raise
    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":
    main()
