import pymysql

from app import Course, DB_HOST, DB_NAME, DB_PASS_RAW, DB_PORT, DB_USER, TimeSlot, app, db


def create_database():
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
    with app.app_context():
        db.metadatas[None].create_all(bind=db.engines[None])


def insert_seed_data():
    with app.app_context():
        if not TimeSlot.query.first():
            slots = [
                TimeSlot(weekday=1, start_time="08:00", end_time="09:40", label="周一 1-2 节"),
                TimeSlot(weekday=1, start_time="10:00", end_time="11:40", label="周一 3-4 节"),
                TimeSlot(weekday=2, start_time="08:00", end_time="09:40", label="周二 1-2 节"),
                TimeSlot(weekday=2, start_time="14:00", end_time="15:40", label="周二 5-6 节"),
                TimeSlot(weekday=3, start_time="10:00", end_time="11:40", label="周三 3-4 节"),
            ]
            db.session.add_all(slots)

        if not Course.query.first():
            courses = [
                Course(
                    course_id="CS001",
                    course_name="数据库系统",
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
            ]
            db.session.add_all(courses)

        db.session.commit()


if __name__ == "__main__":
    create_database()
    init_tables()
    insert_seed_data()
    print(f"{DB_NAME} tables initialized")
