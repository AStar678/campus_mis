"""选课与智能排课分服务数据库初始化脚本。

该脚本负责创建本服务独立数据库、初始化 cs_ 前缀业务表，并写入演示用课程和时间段数据。
重复执行时会保留已有数据，避免覆盖开发过程中的测试记录。
"""

from datetime import datetime

import pymysql

from app import Course, CourseRequest, CourseSection, DB_HOST, DB_NAME, DB_PASS_RAW, DB_PORT, DB_USER, ScheduleResult, SelectionBatch, TimeSlot, app, db


def create_database():
    """创建选课排课服务数据库。"""

    conn = pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASS_RAW,
        charset="utf8mb4",
    )
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` "
                "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci"
            )
        conn.commit()
    finally:
        conn.close()


def init_tables():
    """根据 SQLAlchemy 模型创建本服务业务表。"""

    with app.app_context():
        db.metadatas[None].create_all(bind=db.engines[None])
        ensure_schema_upgrades()


def column_exists(table_name, column_name):
    """判断当前业务库中指定字段是否存在。"""

    row = db.session.execute(
        db.text(
            """
            SELECT COUNT(*)
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = :schema_name
              AND TABLE_NAME = :table_name
              AND COLUMN_NAME = :column_name
            """
        ),
        {"schema_name": DB_NAME, "table_name": table_name, "column_name": column_name},
    ).scalar()
    return bool(row)


def ensure_schema_upgrades():
    """兼容旧数据库，补充教学班相关字段。"""

    if not column_exists("cs_courses", "credits"):
        db.session.execute(db.text("ALTER TABLE cs_courses ADD COLUMN credits DECIMAL(4,1) NOT NULL DEFAULT 2.0 AFTER capacity"))
        db.session.execute(db.text("UPDATE cs_courses SET credits = hours_per_week WHERE credits IS NULL OR credits <= 0"))
    if not column_exists("cs_courses", "allowed_majors"):
        db.session.execute(db.text("ALTER TABLE cs_courses ADD COLUMN allowed_majors VARCHAR(200) NOT NULL DEFAULT 'all' AFTER preferred_building"))
    if not column_exists("cs_courses", "allowed_grades"):
        db.session.execute(db.text("ALTER TABLE cs_courses ADD COLUMN allowed_grades VARCHAR(100) NOT NULL DEFAULT 'all' AFTER allowed_majors"))
    if not column_exists("cs_courses", "prerequisite_note"):
        db.session.execute(db.text("ALTER TABLE cs_courses ADD COLUMN prerequisite_note VARCHAR(300) NOT NULL DEFAULT '无' AFTER allowed_grades"))
    if not column_exists("cs_course_requests", "section_id"):
        db.session.execute(db.text("ALTER TABLE cs_course_requests ADD COLUMN section_id VARCHAR(30) NULL AFTER course_id"))
        db.session.execute(db.text("CREATE INDEX idx_cs_request_section ON cs_course_requests (section_id)"))
    if not column_exists("cs_course_sections", "required_room_type"):
        db.session.execute(db.text("ALTER TABLE cs_course_sections ADD COLUMN required_room_type VARCHAR(30) NOT NULL DEFAULT '普通教室' AFTER preferred_building"))
    if not column_exists("cs_course_sections", "unavailable_slot_ids"):
        db.session.execute(db.text("ALTER TABLE cs_course_sections ADD COLUMN unavailable_slot_ids VARCHAR(200) NOT NULL DEFAULT '' AFTER required_room_type"))
    if not column_exists("cs_selection_batches", "min_credits"):
        db.session.execute(db.text("ALTER TABLE cs_selection_batches ADD COLUMN min_credits DECIMAL(4,1) NOT NULL DEFAULT 2.0 AFTER max_preferences"))
    if not column_exists("cs_selection_batches", "max_credits"):
        db.session.execute(db.text("ALTER TABLE cs_selection_batches ADD COLUMN max_credits DECIMAL(4,1) NOT NULL DEFAULT 8.0 AFTER min_credits"))
    if not column_exists("cs_schedule_results", "section_id"):
        db.session.execute(db.text("ALTER TABLE cs_schedule_results ADD COLUMN section_id VARCHAR(30) NULL AFTER course_id"))
        db.session.execute(db.text("CREATE INDEX idx_cs_result_section ON cs_schedule_results (section_id)"))
    db.session.commit()


def ensure_default_batch():
    """确保存在默认选课批次配置。"""

    if SelectionBatch.query.filter_by(is_active=True).first():
        return
    db.session.add(
        SelectionBatch(
            term_name="2025-2026 学年第二学期",
            phase="selecting",
            phase_label="正式选课阶段",
            start_at=datetime(2026, 6, 1, 9, 0),
            end_at=datetime(2026, 6, 20, 18, 0),
            max_preferences=3,
            min_credits=2,
            max_credits=8,
            notice="排课结果以管理员发布为准。",
            is_active=True,
        )
    )
    db.session.commit()


def normalize_legacy_request_statuses():
    """归一化历史选课状态，避免旧系统状态污染当前列表和导出。"""

    status_mapping = {
        "pending": "submitted",
        "approved": "scheduled",
        "rejected": "cancelled",
    }
    updated_count = 0
    for old_status, new_status in status_mapping.items():
        updated_count += CourseRequest.query.filter_by(status=old_status).update(
            {"status": new_status},
            synchronize_session=False,
        )
    if updated_count:
        db.session.commit()
    return updated_count


def normalize_duplicate_preferences():
    """清理历史重复意向，保证同一学生每个意向级别只对应一门有效课程。"""

    active_statuses = ("submitted", "scheduled", "waitlisted")
    student_ids = [
        row[0]
        for row in db.session.query(CourseRequest.student_id)
        .filter(CourseRequest.status.in_(active_statuses))
        .distinct()
        .all()
    ]

    adjusted_count = 0
    cancelled_count = 0
    for student_id in student_ids:
        active_requests = (
            CourseRequest.query.filter(
                CourseRequest.student_id == student_id,
                CourseRequest.status.in_(active_statuses),
            )
            .order_by(CourseRequest.preference_level.asc(), CourseRequest.created_at.asc(), CourseRequest.id.asc())
            .all()
        )
        used_levels = set()
        for course_request in active_requests:
            current_level = int(course_request.preference_level)
            if current_level in (1, 2, 3) and current_level not in used_levels:
                used_levels.add(current_level)
                continue

            available_level = next((level for level in (1, 2, 3) if level not in used_levels), None)
            if available_level:
                course_request.preference_level = available_level
                used_levels.add(available_level)
                adjusted_count += 1
            else:
                course_request.status = "cancelled"
                cancelled_count += 1

    if adjusted_count or cancelled_count:
        db.session.commit()
    return adjusted_count, cancelled_count


def cancel_required_course_requests():
    """撤销历史必修课选课意向，必修课由培养方案保障，不参与学生意向排序。"""

    active_statuses = ("submitted", "scheduled", "waitlisted")
    required_courses = Course.query.filter(
        (Course.course_id.like("REQ%"))
        | (Course.course_name.like("%必修%"))
        | (Course.course_name.like("%基础%"))
    ).all()
    required_course_ids = [course.course_id for course in required_courses]
    if not required_course_ids:
        return 0

    updated_count = CourseRequest.query.filter(
        CourseRequest.course_id.in_(required_course_ids),
        CourseRequest.status.in_(active_statuses),
    ).update({"status": "cancelled"}, synchronize_session=False)
    if updated_count:
        db.session.commit()
    return updated_count


def is_required_course(course):
    """判断课程是否为计划内必修课。"""

    return (
        course.course_id.upper().startswith("REQ")
        or "必修" in course.course_name
        or "基础" in course.course_name
    )


def create_missing_sections_for_existing_courses():
    """为历史非必修课程补充默认教学班，避免学生端出现空教学班下拉框。"""

    created_count = 0
    courses = Course.query.order_by(Course.course_id).all()
    for course in courses:
        if is_required_course(course):
            continue
        existing_section = CourseSection.query.filter_by(course_id=course.course_id).first()
        if existing_section:
            continue

        base_section_id = f"{course.course_id}-01"
        section_id = base_section_id
        suffix = 1
        while db.session.get(CourseSection, section_id):
            suffix += 1
            section_id = f"{course.course_id}-{suffix:02d}"

        db.session.add(
            CourseSection(
                section_id=section_id,
                course_id=course.course_id,
                section_name=f"{course.course_name} 01班",
                teacher_id=course.teacher_id,
                capacity=course.capacity,
                preferred_building=course.preferred_building,
                status=course.status,
            )
        )
        created_count += 1

    if created_count:
        db.session.commit()
    return created_count


def attach_missing_sections():
    """为历史选课意向补充教学班，避免旧数据无法参与教学班排课。"""

    active_statuses = ("submitted", "scheduled", "waitlisted")
    updated_count = 0
    requests_without_section = CourseRequest.query.filter(
        CourseRequest.section_id.is_(None),
        CourseRequest.status.in_(active_statuses),
    ).all()
    for course_request in requests_without_section:
        section = (
            CourseSection.query.filter_by(course_id=course_request.course_id, status="open")
            .order_by(CourseSection.section_id.asc())
            .first()
        )
        if section:
            course_request.section_id = section.section_id
            updated_count += 1
        else:
            course_request.status = "cancelled"
            updated_count += 1

    if updated_count:
        db.session.commit()
    return updated_count


def update_initial_section_constraints():
    """同步初始教学班的教室类型和教师不可用时间约束。"""

    constraints = {
        "CS003-01": ("机房", "7"),
        "CS003-02": ("机房", ""),
        "CS006-01": ("机房", ""),
        "CS006-02": ("机房", "2"),
        "PUB002-01": ("体育场馆", ""),
        "PUB002-02": ("体育场馆", ""),
    }
    updated_count = 0
    for section_id, (room_type, unavailable_slots) in constraints.items():
        section = db.session.get(CourseSection, section_id)
        if not section:
            continue
        section.required_room_type = room_type
        section.unavailable_slot_ids = unavailable_slots
        updated_count += 1
    if updated_count:
        db.session.commit()
    return updated_count


def insert_seed_data():
    """写入演示用时间段、课程和学生选课意向数据。"""

    with app.app_context():
        slots = [
            TimeSlot(weekday=1, start_time="08:00", end_time="09:40", label="周一 1-2 节"),
            TimeSlot(weekday=1, start_time="10:00", end_time="11:40", label="周一 3-4 节"),
            TimeSlot(weekday=2, start_time="08:00", end_time="09:40", label="周二 1-2 节"),
            TimeSlot(weekday=2, start_time="14:00", end_time="15:40", label="周二 5-6 节"),
            TimeSlot(weekday=3, start_time="10:00", end_time="11:40", label="周三 3-4 节"),
            TimeSlot(weekday=3, start_time="14:00", end_time="15:40", label="周三 5-6 节"),
            TimeSlot(weekday=4, start_time="08:00", end_time="09:40", label="周四 1-2 节"),
            TimeSlot(weekday=4, start_time="19:00", end_time="20:40", label="周四 9-10 节"),
            TimeSlot(weekday=5, start_time="10:00", end_time="11:40", label="周五 3-4 节"),
        ]
        for slot in slots:
            existing_slot = TimeSlot.query.filter_by(
                weekday=slot.weekday,
                start_time=slot.start_time,
                end_time=slot.end_time,
            ).first()
            if not existing_slot:
                db.session.add(slot)

        courses = [
            Course(
                course_id="REQ-CS001",
                course_name="数据库系统基础",
                teacher_id="1001",
                capacity=45,
                hours_per_week=2,
                preferred_building="1号楼",
            ),
            Course(
                course_id="CS002",
                course_name="人工智能导论",
                teacher_id="1002",
                capacity=40,
                hours_per_week=2,
                preferred_building="2号楼",
            ),
            Course(
                course_id="CS003",
                course_name="软件工程实践",
                teacher_id="1001",
                capacity=35,
                hours_per_week=2,
                preferred_building="1号楼",
            ),
            Course(
                course_id="REQ-CS004",
                course_name="计算机网络基础",
                teacher_id="1003",
                capacity=50,
                hours_per_week=2,
                preferred_building="3号楼",
            ),
            Course(
                course_id="CS005",
                course_name="数据可视化与分析",
                teacher_id="1004",
                capacity=30,
                hours_per_week=2,
                preferred_building="2号楼",
            ),
            Course(
                course_id="CS006",
                course_name="移动应用开发实践",
                teacher_id="1005",
                capacity=32,
                hours_per_week=2,
                preferred_building="4号楼",
            ),
            Course(
                course_id="PUB001",
                course_name="大学英语综合提升",
                teacher_id="1006",
                capacity=60,
                hours_per_week=2,
                preferred_building="公共教学楼",
            ),
            Course(
                course_id="PUB002",
                course_name="体育健康与体能训练",
                teacher_id="1007",
                capacity=45,
                hours_per_week=2,
                preferred_building="体育馆",
            ),
        ]
        print("seeding courses...")
        existing_course_ids = {
            row[0]
            for row in db.session.query(Course.course_id)
            .filter(Course.course_id.in_([course.course_id for course in courses]))
            .all()
        }
        db.session.add_all([course for course in courses if course.course_id not in existing_course_ids])

        sections = [
            CourseSection(section_id="CS002-01", course_id="CS002", section_name="人工智能导论 01班", teacher_id="1002", capacity=35, preferred_building="2号楼"),
            CourseSection(section_id="CS002-02", course_id="CS002", section_name="人工智能导论 02班", teacher_id="1012", capacity=35, preferred_building="3号楼"),
            CourseSection(section_id="CS003-01", course_id="CS003", section_name="软件工程实践 01班", teacher_id="1001", capacity=30, preferred_building="1号楼", required_room_type="机房", unavailable_slot_ids="7"),
            CourseSection(section_id="CS003-02", course_id="CS003", section_name="软件工程实践 02班", teacher_id="1013", capacity=30, preferred_building="4号楼", required_room_type="机房"),
            CourseSection(section_id="CS005-01", course_id="CS005", section_name="数据可视化与分析 01班", teacher_id="1004", capacity=28, preferred_building="2号楼"),
            CourseSection(section_id="CS005-02", course_id="CS005", section_name="数据可视化与分析 02班", teacher_id="1014", capacity=28, preferred_building="1号楼"),
            CourseSection(section_id="CS006-01", course_id="CS006", section_name="移动应用开发实践 01班", teacher_id="1005", capacity=30, preferred_building="4号楼", required_room_type="机房"),
            CourseSection(section_id="CS006-02", course_id="CS006", section_name="移动应用开发实践 02班", teacher_id="1015", capacity=30, preferred_building="2号楼", required_room_type="机房", unavailable_slot_ids="2"),
            CourseSection(section_id="PUB001-01", course_id="PUB001", section_name="大学英语综合提升 01班", teacher_id="1006", capacity=45, preferred_building="公共教学楼"),
            CourseSection(section_id="PUB001-02", course_id="PUB001", section_name="大学英语综合提升 02班", teacher_id="1016", capacity=45, preferred_building="公共教学楼"),
            CourseSection(section_id="PUB002-01", course_id="PUB002", section_name="体育健康与体能训练 01班", teacher_id="1007", capacity=35, preferred_building="体育馆", required_room_type="体育场馆"),
            CourseSection(section_id="PUB002-02", course_id="PUB002", section_name="体育健康与体能训练 02班", teacher_id="1017", capacity=35, preferred_building="体育馆", required_room_type="体育场馆"),
        ]
        print("seeding course sections...")
        existing_section_ids = {
            row[0]
            for row in db.session.query(CourseSection.section_id)
            .filter(CourseSection.section_id.in_([section.section_id for section in sections]))
            .all()
        }
        db.session.add_all([section for section in sections if section.section_id not in existing_section_ids])

        request_rows = [
            ("20240001", "CS002", "CS002-01", 1),
            ("20240001", "CS005", "CS005-02", 2),
            ("20240001", "PUB001", "PUB001-01", 3),
            ("20240002", "CS003", "CS003-01", 1),
            ("20240002", "CS006", "CS006-02", 2),
            ("20240002", "PUB002", "PUB002-01", 3),
            ("20240003", "CS005", "CS005-01", 1),
            ("20240003", "CS002", "CS002-02", 2),
            ("20240003", "PUB001", "PUB001-02", 3),
            ("20240004", "CS002", "CS002-01", 1),
            ("20240004", "CS006", "CS006-01", 2),
            ("20240004", "PUB002", "PUB002-02", 3),
            ("20240005", "CS003", "CS003-02", 1),
            ("20240005", "CS005", "CS005-01", 2),
            ("20240005", "PUB001", "PUB001-01", 3),
            ("20240006", "CS006", "CS006-02", 1),
            ("20240006", "CS005", "CS005-02", 2),
            ("20240006", "PUB002", "PUB002-01", 3),
        ]
        print("seeding course requests...")
        existing_requests = {
            (course_request.student_id, course_request.course_id): course_request
            for course_request in CourseRequest.query.filter(
                CourseRequest.student_id.in_([row[0] for row in request_rows]),
                CourseRequest.course_id.in_([row[1] for row in request_rows]),
            ).all()
        }
        for student_id, course_id, section_id, preference_level in request_rows:
            existing_request = existing_requests.get((student_id, course_id))
            if existing_request is None:
                db.session.add(
                    CourseRequest(
                        student_id=student_id,
                        course_id=course_id,
                        section_id=section_id,
                        preference_level=preference_level,
                    )
                )
            elif not existing_request.section_id and existing_request.status != "cancelled":
                existing_request.section_id = section_id

        print("committing seed data...")
        db.session.commit()
        print("cleaning historical data...")
        created_section_count = create_missing_sections_for_existing_courses()
        normalized_status_count = normalize_legacy_request_statuses()
        required_cancelled_count = cancel_required_course_requests()
        attached_section_count = attach_missing_sections()
        adjusted_count, cancelled_count = normalize_duplicate_preferences()
        section_constraint_count = update_initial_section_constraints()
        ensure_default_batch()
        if created_section_count:
            print(f"created default sections: {created_section_count}")
        if normalized_status_count:
            print(f"normalized legacy request statuses: {normalized_status_count}")
        if required_cancelled_count:
            print(f"cancelled required-course preferences: {required_cancelled_count}")
        if attached_section_count:
            print(f"attached missing sections: {attached_section_count}")
        if adjusted_count or cancelled_count:
            print(f"normalized duplicate preferences: adjusted={adjusted_count}, cancelled={cancelled_count}")
        if section_constraint_count:
            print(f"updated initial section constraints: {section_constraint_count}")


if __name__ == "__main__":
    create_database()
    init_tables()
    insert_seed_data()
    print(f"{DB_NAME} tables initialized")
