"""选课与智能排课分服务数据库初始化脚本。

该脚本负责创建本服务独立数据库、初始化 cs_ 前缀业务表，并写入演示用课程和时间段数据。
重复执行时会保留已有数据，避免覆盖开发过程中的测试记录。
"""

import pymysql

from app import Course, CourseRequest, DB_HOST, DB_NAME, DB_PASS_RAW, DB_PORT, DB_USER, TimeSlot, app, db


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


def normalize_duplicate_preferences():
    """清理历史重复意向，保证同一学生每个意向级别只对应一门有效课程。"""

    active_statuses = ("submitted", "scheduled")
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

    active_statuses = ("submitted", "scheduled")
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
        for course in courses:
            if not db.session.get(Course, course.course_id):
                db.session.add(course)

        request_rows = [
            ("20240001", "CS002", 1),
            ("20240001", "CS005", 2),
            ("20240001", "PUB001", 3),
            ("20240002", "CS003", 1),
            ("20240002", "CS006", 2),
            ("20240002", "PUB002", 3),
            ("20240003", "CS005", 1),
            ("20240003", "CS002", 2),
            ("20240003", "PUB001", 3),
            ("20240004", "CS002", 1),
            ("20240004", "CS006", 2),
            ("20240004", "PUB002", 3),
            ("20240005", "CS003", 1),
            ("20240005", "CS005", 2),
            ("20240005", "PUB001", 3),
            ("20240006", "CS006", 1),
            ("20240006", "CS005", 2),
            ("20240006", "PUB002", 3),
        ]
        for student_id, course_id, preference_level in request_rows:
            existing_request = CourseRequest.query.filter_by(
                student_id=student_id,
                course_id=course_id,
            ).first()
            if not existing_request:
                db.session.add(
                    CourseRequest(
                        student_id=student_id,
                        course_id=course_id,
                        preference_level=preference_level,
                    )
                )

        db.session.commit()
        required_cancelled_count = cancel_required_course_requests()
        adjusted_count, cancelled_count = normalize_duplicate_preferences()
        if required_cancelled_count:
            print(f"cancelled required-course preferences: {required_cancelled_count}")
        if adjusted_count or cancelled_count:
            print(f"normalized duplicate preferences: adjusted={adjusted_count}, cancelled={cancelled_count}")


if __name__ == "__main__":
    create_database()
    init_tables()
    insert_seed_data()
    print(f"{DB_NAME} tables initialized")
