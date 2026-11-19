"""Idempotent Curriculum Seeding Script for Third EYE LMS

Safety Rules:
- Complete preflight validation verifying database path, integrity, and existing audit baseline.
- Aborts on unexpected state, orphaned relations, or duplicate records.
- Truly idempotent: detects existing courses, modules, and lessons.
- Newly inserted parent records are immediately inspected for child modules/lessons.
- Inserts only missing records and preserves all existing content without modification.
- Category assignment: category_id is explicitly set to None (no dev category association).
- Both courses strictly configured with status='draft' (unpublished).
- All modules and lessons strictly configured with is_published=False.
- Pricing unset (price_amount=None, is_free=False, currency='INR').
- Source identifiers (NET-*) preserved in descriptions and content bodies.
- Default execution mode is strictly DRY-RUN with complete transaction rollback.
- Never run with --apply without explicit approval.
"""

import argparse
import os
import sys
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Ensure backend root is on sys.path and load environment
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BACKEND_DIR)
load_dotenv(os.path.join(BACKEND_DIR, ".env"))

from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.database import SessionLocal, engine
from app.models.course import Course, CourseCategory, CourseModule, Lesson

EXPECTED_DB_FILENAME = "thirdeye_recovery.db"
PLACEHOLDER_NOTICE = (
    "Detailed official lesson content will be added after review by the teaching center."
)

CURRICULUM_SPECIFICATIONS: List[Dict] = [
    {
        "slug": "third-eye-awakening-foundations",
        "title": "Third Eye Awakening Foundations (நெற்றிக்கண் தொடக்கப் பயிற்சி)",
        "description": "Foundational curriculum exploring the Netrikkan meditation tradition, Meiyunervu (inner awareness), and safe observational practice as recorded in source documents.",
        "category_id": None,  # Explicitly unset / no dev category association
        "level": "beginner",
        "status": "draft",
        "is_free": False,
        "price_amount": None,
        "currency": "INR",
        "modules": [
            {
                "title": "Module 1: Introduction and Foundations (அறிமுகம் மற்றும் அடித்தளங்கள்)",
                "description": "Historical orientation, Guru Govindar tradition, and core inner awareness principles.",
                "display_order": 1,
                "lessons": [
                    {
                        "title": "Lesson 1: Introduction to Netrikkan Meditation Center",
                        "sources": ["NET-ORG-001", "NET-ORG-003"],
                        "description": "Source reference: [NET-ORG-001, NET-ORG-003]. Background on the meditation center established in Polichalur, Chennai.",
                        "content_type": "article",
                        "display_order": 1,
                    },
                    {
                        "title": "Lesson 2: Introduction to Guru Govindar and the Tradition",
                        "sources": ["NET-ORG-004"],
                        "description": "Source reference: [NET-ORG-004]. Biographical notes and spiritual lineage background.",
                        "content_type": "article",
                        "display_order": 2,
                    },
                    {
                        "title": "Lesson 3: Understanding Meiyunervu",
                        "sources": ["NET-TERM-002"],
                        "description": "Source reference: [NET-TERM-002]. Exploring the concept of true inner awareness and realization.",
                        "content_type": "article",
                        "display_order": 3,
                    },
                    {
                        "title": "Lesson 4: Understanding Uyir Energy",
                        "sources": ["NET-TERM-003"],
                        "description": "Source reference: [NET-TERM-003]. Traditional concept of life-force and subtle vital energy.",
                        "content_type": "article",
                        "display_order": 4,
                    },
                ],
            },
            {
                "title": "Module 2: First-stage Netrikkan Practice (நெற்றிக்கண் முதல்படிப் பயிற்சி)",
                "description": "Available first-stage practice outlines, sensory witnessing, and eye safety guidelines.",
                "display_order": 2,
                "lessons": [
                    {
                        "title": "Lesson 1: Introduction to the Available First-Stage Practice Outline",
                        "sources": ["NET-PRACTICE-001"],
                        "description": "Source reference: [NET-PRACTICE-001]. Overview of the 10-day initial observation framework recorded in source material.",
                        "content_type": "article",
                        "display_order": 1,
                    },
                    {
                        "title": "Lesson 2: Understanding Nose-Tip Focus as Described in the Source",
                        "sources": ["NET-PRACTICE-001", "NET-TERM-010"],
                        "description": "Source reference: [NET-PRACTICE-001, NET-TERM-010]. Gentle Nasikagra Drishti instructions without forceful eye strain.",
                        "content_type": "article",
                        "display_order": 2,
                    },
                    {
                        "title": "Lesson 3: Observing Sensations Without Inventing Interpretations",
                        "sources": ["NET-PRACTICE-001", "NET-APP-002"],
                        "description": "Source reference: [NET-PRACTICE-001, NET-APP-002]. Witnessing natural throbbing or pulse without subjective embellishment.",
                        "content_type": "article",
                        "display_order": 3,
                    },
                    {
                        "title": "Lesson 4: Eye Safety and Physical Precautions",
                        "sources": ["NET-SAFETY-001"],
                        "description": "Source reference: [NET-SAFETY-001]. Essential safety rules: immediately cease practice if experiencing headache, double vision, or pain.",
                        "content_type": "article",
                        "display_order": 4,
                    },
                ],
            },
            {
                "title": "Module 3: Daily Practice and Discipline (தினசரி சாதனை மற்றும் ஒழுக்கம்)",
                "description": "Traditional lifestyle guidance, digestive rhythm, and routine continuity.",
                "display_order": 3,
                "lessons": [
                    {
                        "title": "Lesson 1: Introduction to Traditional Lifestyle Guidance",
                        "sources": ["NET-PRACTICE-003"],
                        "description": "Source reference: [NET-PRACTICE-003]. General principles of moderation and daily balance.",
                        "content_type": "article",
                        "display_order": 1,
                    },
                    {
                        "title": "Lesson 2: Traditional Food and Discipline Notes",
                        "sources": ["NET-PRACTICE-003"],
                        "description": "Source reference: [NET-PRACTICE-003]. Traditional digestive proportions (half food, quarter water, quarter empty) and dietary notes.",
                        "content_type": "article",
                        "display_order": 2,
                    },
                    {
                        "title": "Lesson 3: Building a Consistent Learning and Practice Routine",
                        "sources": ["NET-APP-001"],
                        "description": "Source reference: [NET-APP-001]. Cultivating steady daily continuity in personal sadhana.",
                        "content_type": "article",
                        "display_order": 3,
                    },
                ],
            },
        ],
    },
    {
        "slug": "the-sacred-triad-centers",
        "title": "The Sacred Triad Centers (நெற்றிக்கண், உச்சிக்கண் மற்றும் பிடரிக்கண்)",
        "description": "Intermediate and advanced curriculum exploring the three subtle vision and consciousness centers: Netrikkan, Ucchi Kann, and Pidari Kann.",
        "category_id": None,  # Explicitly unset / no dev category association
        "level": "advanced",
        "status": "draft",
        "is_free": False,
        "price_amount": None,
        "currency": "INR",
        "modules": [
            {
                "title": "Module 1: Understanding the Three Centers (மூன்று மையங்களைப் புரிந்துகொள்ளுதல்)",
                "description": "Exploration of the forehead, crown, and occipital awareness centers and energy pathways.",
                "display_order": 1,
                "lessons": [
                    {
                        "title": "Lesson 1: Introduction to Netrikkan",
                        "sources": ["NET-TERM-001", "NET-TERM-005"],
                        "description": "Source reference: [NET-TERM-001, NET-TERM-005]. The forehead center between the eyebrows.",
                        "content_type": "article",
                        "display_order": 1,
                    },
                    {
                        "title": "Lesson 2: Understanding Ucchi Kann",
                        "sources": ["NET-TERM-006"],
                        "description": "Source reference: [NET-TERM-006]. The crown center associated with Sahasrara.",
                        "content_type": "article",
                        "display_order": 2,
                    },
                    {
                        "title": "Lesson 3: Understanding Pidari Kann",
                        "sources": ["NET-TERM-007"],
                        "description": "Source reference: [NET-TERM-007]. The occipital center at the back of the head.",
                        "content_type": "article",
                        "display_order": 3,
                    },
                    {
                        "title": "Lesson 4: Introduction to Sushumna Nadi and Muladhara",
                        "sources": ["NET-TERM-008", "NET-TERM-009"],
                        "description": "Source reference: [NET-TERM-008, NET-TERM-009]. The central subtle energy pathway and the root foundation.",
                        "content_type": "article",
                        "display_order": 4,
                    },
                ],
            },
            {
                "title": "Module 2: Deepening Understanding (ஆழ்ந்த புரிதல் மற்றும் தெளிவு)",
                "description": "Cultivating Dharana, witnessing natural stillness, and distinguishing spiritual concepts from clinical science.",
                "display_order": 2,
                "lessons": [
                    {
                        "title": "Lesson 1: Understanding Dharana",
                        "sources": ["NET-TERM-010"],
                        "description": "Source reference: [NET-TERM-010]. The discipline of steady, unwavering observational focus.",
                        "content_type": "article",
                        "display_order": 1,
                    },
                    {
                        "title": "Lesson 2: Natural Stillness and Focused Attention",
                        "sources": ["NET-TERM-010", "NET-PRACTICE-002"],
                        "description": "Source reference: [NET-TERM-010, NET-PRACTICE-002]. Deepening effortless attention without mental strain or visualization.",
                        "content_type": "article",
                        "display_order": 2,
                    },
                    {
                        "title": "Lesson 3: Understanding Spiritual Experiences Within the Tradition",
                        "sources": ["NET-TERM-002", "NET-TERM-011"],
                        "description": "Source reference: [NET-TERM-002, NET-TERM-011]. Traditional interpretations of light, vibration, and subtle awareness.",
                        "content_type": "article",
                        "display_order": 3,
                    },
                    {
                        "title": "Lesson 4: Distinguishing Traditional Concepts from Medical Claims",
                        "sources": ["NET-SAFETY-002"],
                        "description": "Source reference: [NET-SAFETY-002]. Clear boundary: spiritual experiences must never be represented as medical diagnoses or cures.",
                        "content_type": "article",
                        "display_order": 4,
                    },
                ],
            },
        ],
    },
]


class DuplicateRecordError(Exception):
    """Raised when an unexpected duplicate record is detected."""
    pass


class PreflightValidationError(Exception):
    """Raised when preflight database checks fail."""
    pass


def run_preflight_validation(db: Session, expected_db_path: str):
    """
    Validates the exact live SQLAlchemy SQLite connection via PRAGMA database_list,
    verifying it matches the active recovery database and is not thirdeye.db, a test DB,
    or an alternate copy.
    """
    print("=" * 68)
    print("PREFLIGHT VALIDATION: Live Connection & Database Baseline")
    print("=" * 68)

    # 1. Dialect Verification
    dialect_name = engine.dialect.name
    if dialect_name != "sqlite":
        raise PreflightValidationError(
            f"Expected SQLite dialect, but live connection is using: '{dialect_name}'"
        )
    print(f"  [OK] Dialect confirmed: {dialect_name}")

    # 2. PRAGMA database_list Inspection through live SessionLocal
    db_list_rows = db.execute(text("PRAGMA database_list;")).fetchall()
    if not db_list_rows:
        raise PreflightValidationError("PRAGMA database_list returned no databases!")

    main_db_rows = [r for r in db_list_rows if r[1] == "main"]
    if len(main_db_rows) != 1:
        raise PreflightValidationError(
            f"Ambiguous database configuration. Expected 1 'main' database, found: {db_list_rows}"
        )

    live_db_file = main_db_rows[0][2]
    if not live_db_file:
        raise PreflightValidationError("Main SQLite database is in-memory or unnamed! Aborting.")

    # 3. Path Resolution & Comparison
    live_resolved_path = os.path.abspath(os.path.realpath(live_db_file))
    expected_resolved_path = os.path.abspath(os.path.realpath(expected_db_path))

    print(f"  [LIVE CONNECTION DB]:     {live_resolved_path}")
    print(f"  [EXPECTED TARGET DB]:     {expected_resolved_path}")

    live_lower = live_resolved_path.lower()
    expected_lower = expected_resolved_path.lower()

    if live_lower != expected_lower:
        raise PreflightValidationError(
            f"Connection mismatch! Live connection is pointing to:\n  '{live_resolved_path}'\n"
            f"but expected target is:\n  '{expected_resolved_path}'"
        )

    # Explicit safeguard against thirdeye.db or test databases
    filename = os.path.basename(live_resolved_path).lower()
    if filename == "thirdeye.db":
        raise PreflightValidationError(
            "CRITICAL SAFEGUARD: Live connection is attached to 'thirdeye.db', NOT 'thirdeye_recovery.db'! Aborting immediately."
        )
    if "test" in filename and "recovery" not in filename:
        raise PreflightValidationError(
            f"CRITICAL SAFEGUARD: Live connection appears to be a test database ('{filename}')! Aborting."
        )
    if not filename.endswith(EXPECTED_DB_FILENAME.lower()):
        raise PreflightValidationError(
            f"CRITICAL SAFEGUARD: Live database file '{filename}' does not end with '{EXPECTED_DB_FILENAME}'! Aborting."
        )

    print("  [OK] Live database file strictly verified as 'thirdeye_recovery.db'")

    # 4. SQLite Low-level Integrity Check
    integrity_result = db.execute(text("PRAGMA integrity_check;")).scalar()
    if integrity_result != "ok":
        raise PreflightValidationError(f"Database integrity check failed: {integrity_result}")
    print(f"  [OK] SQLite PRAGMA integrity_check passed: {integrity_result}")

    # 5. Known Development Baseline Validation
    dev_course_1 = db.query(Course).filter(Course.id == 1).first()
    if not dev_course_1 or dev_course_1.slug != "third-eye-awakening-foundations-dev":
        raise PreflightValidationError(
            f"Baseline Course ID 1 missing or corrupted: {dev_course_1}"
        )

    dev_course_2 = db.query(Course).filter(Course.id == 2).first()
    if not dev_course_2 or dev_course_2.slug != "advanced-inner-sanctuary-mastery-dev":
        raise PreflightValidationError(
            f"Baseline Course ID 2 missing or corrupted: {dev_course_2}"
        )
    print("  [OK] Baseline development courses confirmed: IDs [1, 2] intact")

    from app.models.course import CourseEnrollment
    baseline_enrollment = (
        db.query(CourseEnrollment)
        .filter(CourseEnrollment.user_id == 6, CourseEnrollment.course_id == 1)
        .first()
    )
    if not baseline_enrollment:
        raise PreflightValidationError(
            "Baseline enrollment missing: expected User 6 on Course 1"
        )
    print("  [OK] Baseline enrollment verified: User 6 on Course 1 (active)")

    # 6. General Relational State Validation
    slug_dupes = db.execute(
        text("SELECT slug, count(*) FROM courses GROUP BY slug HAVING count(*) > 1;")
    ).fetchall()
    if slug_dupes:
        raise PreflightValidationError(f"Duplicate course slugs detected in database: {slug_dupes}")
    print("  [OK] No duplicate course slugs in database")

    mod_dupes = db.execute(
        text("SELECT course_id, title, count(*) FROM course_modules GROUP BY course_id, title HAVING count(*) > 1;")
    ).fetchall()
    if mod_dupes:
        raise PreflightValidationError(f"Duplicate module titles detected in database: {mod_dupes}")
    print("  [OK] No duplicate module titles per course")

    les_dupes = db.execute(
        text("SELECT module_id, title, count(*) FROM lessons GROUP BY module_id, title HAVING count(*) > 1;")
    ).fetchall()
    if les_dupes:
        raise PreflightValidationError(f"Duplicate lesson titles detected in database: {les_dupes}")
    print("  [OK] No duplicate lesson titles per module")

    orphaned_mods = db.execute(
        text("SELECT count(*) FROM course_modules WHERE course_id NOT IN (SELECT id FROM courses);")
    ).scalar()
    if orphaned_mods > 0:
        raise PreflightValidationError(f"Found {orphaned_mods} orphaned course modules!")

    orphaned_lessons = db.execute(
        text("SELECT count(*) FROM lessons WHERE module_id NOT IN (SELECT id FROM course_modules);")
    ).scalar()
    if orphaned_lessons > 0:
        raise PreflightValidationError(f"Found {orphaned_lessons} orphaned lessons!")
    print("  [OK] Relational integrity verified: 0 orphaned modules, 0 orphaned lessons")

    total_courses = db.query(Course).count()
    total_enrollments = db.query(CourseEnrollment).count()
    print(f"  [INFO] Current database totals: {total_courses} courses, {total_enrollments} enrollments")
    print("=" * 68)
    print("PREFLIGHT VALIDATION PASSED: Database connection & baseline 100% verified.\n")


def seed_curriculum_draft(apply_changes: bool = False, db_path: Optional[str] = None):
    target_path = db_path or os.path.abspath(r"C:\Projects\thirdeye-ai-backend\thirdeye_recovery.db")
    db = SessionLocal()

    planned_inserts = {"courses": 0, "modules": 0, "lessons": 0}
    preserved_records = {"courses": 0, "modules": 0, "lessons": 0}

    try:
        # Step 1: Preflight
        run_preflight_validation(db, target_path)

        mode_header = "[APPLY EXECUTION MODE]" if apply_changes else "[DRY-RUN INSPECTION MODE]"
        print("=" * 68)
        print(f"SEEDING PLAN: {mode_header}")
        print("=" * 68)

        for course_spec in CURRICULUM_SPECIFICATIONS:
            slug = course_spec["slug"]
            matching_courses = db.query(Course).filter(Course.slug == slug).all()

            if len(matching_courses) > 1:
                raise DuplicateRecordError(
                    f"Fatal: Found {len(matching_courses)} courses matching slug '{slug}'! Refusing to pick arbitrary record."
                )

            if matching_courses:
                course = matching_courses[0]
                preserved_records["courses"] += 1
                print(f"[PRESERVED] Course exists: ID={course.id} | Slug='{course.slug}' | Title='{course.title}'")
            else:
                planned_inserts["courses"] += 1
                course = Course(
                    category_id=None,  # Explicitly unset / no dev category
                    slug=slug,
                    title=course_spec["title"],
                    description=course_spec["description"],
                    thumbnail_url=None,
                    is_free=False,  # Unset/protected
                    price_amount=None,  # Unset
                    currency="INR",  # Schema requirement
                    status="draft",  # Unpublished
                    level=course_spec["level"],
                )
                db.add(course)
                # Flush inside the transaction to generate course.id for child relationship verification
                db.flush()
                print(f"[PLANNED INSERT] Course: ID={course.id} | Title='{course.title}' (slug='{slug}', category_id=NULL, status='draft')")

            # Always inspect modules for this course (whether course pre-existed or was newly inserted)
            for mod_spec in course_spec["modules"]:
                mod_title = mod_spec["title"]
                matching_mods = (
                    db.query(CourseModule)
                    .filter(CourseModule.course_id == course.id, CourseModule.title == mod_title)
                    .all()
                )

                if len(matching_mods) > 1:
                    raise DuplicateRecordError(
                        f"Fatal: Found {len(matching_mods)} duplicate modules with title '{mod_title}' in Course ID {course.id}!"
                    )

                if matching_mods:
                    module = matching_mods[0]
                    preserved_records["modules"] += 1
                    print(f"  [PRESERVED] Module exists: ID={module.id} | Title='{module.title}' (Parent Course ID: {course.id})")
                else:
                    planned_inserts["modules"] += 1
                    module = CourseModule(
                        course_id=course.id,
                        title=mod_title,
                        description=mod_spec["description"],
                        display_order=mod_spec["display_order"],
                        is_published=False,  # Unpublished
                    )
                    db.add(module)
                    # Flush inside the transaction to generate module.id for lesson relationship verification
                    db.flush()
                    print(f"  [PLANNED INSERT] Module: ID={module.id} | Title='{mod_title}' (Parent Course ID: {course.id}, is_published=False)")

                # Always inspect lessons for this module (whether module pre-existed or was newly inserted)
                for les_spec in mod_spec["lessons"]:
                    les_title = les_spec["title"]
                    matching_lessons = (
                        db.query(Lesson)
                        .filter(Lesson.module_id == module.id, Lesson.title == les_title)
                        .all()
                    )

                    if len(matching_lessons) > 1:
                        raise DuplicateRecordError(
                            f"Fatal: Found {len(matching_lessons)} duplicate lessons with title '{les_title}' in Module ID {module.id}!"
                        )

                    if matching_lessons:
                        lesson = matching_lessons[0]
                        preserved_records["lessons"] += 1
                        print(f"    [PRESERVED] Lesson exists: ID={lesson.id} | Title='{lesson.title}' (Parent Module ID: {module.id})")
                    else:
                        planned_inserts["lessons"] += 1
                        sources_tag = ", ".join(les_spec.get("sources", []))
                        structured_body = (
                            f"[Source References: {sources_tag}]\n"
                            f"[Status: Preliminary Outline]\n\n"
                            f"{PLACEHOLDER_NOTICE}"
                        )
                        lesson = Lesson(
                            module_id=module.id,
                            title=les_title,
                            description=les_spec["description"],
                            content_type=les_spec["content_type"],
                            content_body=structured_body,
                            media_url=None,
                            duration_seconds=0,
                            display_order=les_spec["display_order"],
                            is_preview=False,
                            is_published=False,  # Unpublished
                        )
                        db.add(lesson)
                        db.flush()
                        print(f"    [PLANNED INSERT] Lesson: ID={lesson.id} | Title='{les_title}' (Parent Module ID: {module.id}, sources: [{sources_tag}], is_published=False)")

        total_planned = sum(planned_inserts.values())
        total_preserved = sum(preserved_records.values())

        print("\n" + "=" * 68)
        print("SUMMARY OF OPERATIONS")
        print("=" * 68)
        print(f"  Proposed Inserts:   {planned_inserts['courses']} Courses, {planned_inserts['modules']} Modules, {planned_inserts['lessons']} Lessons ({total_planned} total)")
        print(f"  Preserved Records:  {preserved_records['courses']} Courses, {preserved_records['modules']} Modules, {preserved_records['lessons']} Lessons ({total_preserved} total)")
        print(f"  Updates or Deletes: 0 (Strictly zero existing records modified)")

        if apply_changes:
            db.commit()
            print("\n[SUCCESS] Transaction committed. All proposed records saved to active database.")
        else:
            db.rollback()
            print("\n[DRY-RUN COMPLETE] Transaction explicitly rolled back.")
            print("[ZERO MUTATION CONFIRMED] Exactly 0 mutations were written to disk.")

    except Exception as e:
        db.rollback()
        print(f"\n[FATAL ABORT] Database transaction rolled back: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed draft curriculum into Third EYE LMS")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default is dry-run)")
    parser.add_argument("--db-path", type=str, default=None, help="Path to SQLite database file")
    args = parser.parse_args()
    seed_curriculum_draft(apply_changes=args.apply, db_path=args.db_path)
