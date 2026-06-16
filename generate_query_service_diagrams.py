#!/usr/bin/env python3
"""查询服务时序图与类图（精简版）"""

timing = """\
sequenceDiagram
    participant 前端 as 前端
    participant QS as 查询服务 :5005
    participant MS as 主服务 :5001
    participant DS as DeepSeek

    rect rgb(245,245,255)
    Note over 前端,MS: ═══ SSO 认证（三端统一）═══
    前端->>QS: 任意 API（含 token）
    QS->>MS: GET /api/verify-token
    MS-->>QS: { user_id, user_type }
    alt 无效 / 无权限
        QS-->>前端: 401 / 403
    end
    end

    rect rgb(255,250,240)
    Note over 前端,QS: ═══ 学生端 ═══
    前端->>QS: GET /student/grades
    QS->>QS: main_database.course_grades
    QS->>QS: classroom_database.courses（跨库补名）
    QS-->>前端: { 课程名, 成绩, 学期 }
    end

    rect rgb(240,255,240)
    Note over 前端,QS: ═══ 教师端 ═══
    前端->>QS: GET /teacher/grades
    QS->>QS: classroom_database.courses（本人授课）
    QS->>QS: classroom_database.course_students
    QS->>QS: users_database.students（补姓名）
    QS-->>前端: { 学生名, 成绩, 课程 }
    end

    rect rgb(255,240,245)
    Note over 前端,DS: ═══ 管理员端：Agent 智能问答 ═══
    前端->>QS: POST /agent { question }
    QS->>QS: build_agent_system_prompt(admin)
    QS->>DS: Chat（system_prompt + 问题）
    DS-->>QS: AI 回复（含 SQL）
    QS->>QS: execute_safe_sql（6 层安全校验）
    QS->>DS: Chat（查询结果 + 解读指令）
    DS-->>QS: 中文自然语言总结
    QS-->>前端: { answer, sql_executed }
    end
"""

klass = """\
classDiagram
    direction TB

    namespace API层 {
        class SSO验证 {
            <<认证>>
            +verify_token_with_main_service()
        }
        class require_auth {
            <<装饰器>>
            +student / teacher / admin
        }
        class 学生查询 {
            +GET /me
            +GET /student/grades
            +GET /student/courses
            +GET /student/schedule
        }
        class 教师查询 {
            +GET /teacher/courses
            +GET /teacher/grades
            +GET /teacher/schedule
        }
        class 管理员查询 {
            +GET /admin/students
            +GET /admin/teachers
            +GET /admin/grades
        }
        class Agent问答 {
            +POST /agent
            +build_agent_system_prompt()
            +call_deepseek_api()
            +execute_safe_sql()
        }
    }

    namespace 数据模型 {
        class CourseGrade {
            main_database
            +student_id +course_id
            +score +comment
        }
        class Course {
            classroom_database
            +name +teacher_id
            +credits +course_type
        }
        class CourseStudent {
            classroom_database
            +student_id +course_id
            +final_grade
        }
        class Student {
            users_database
            +student_id +name
            +grade +major
        }
        class Teacher {
            users_database
            +teacher_id +name
            +college +title
        }
        class CsScheduleResult {
            course_schedule_database
            +slot_id +classroom_id
            +is_published
        }
    }

    class DeepSeek {
        <<external>>
        deepseek-chat
    }

    学生查询 ..> require_auth : 装饰
    教师查询 ..> require_auth : 装饰
    管理员查询 ..> require_auth : 装饰
    Agent问答 ..> require_auth : 装饰
    require_auth --> SSO验证 : 调用主服务

    学生查询 --> CourseGrade
    学生查询 --> Course
    教师查询 --> CourseStudent
    教师查询 --> Student
    管理员查询 --> Student
    管理员查询 --> Teacher
    管理员查询 --> CourseGrade
    Agent问答 --> DeepSeek
    Agent问答 --> CourseGrade
    Agent问答 --> CourseStudent
"""

print("时序图 (Mermaid)")
print("-" * 50)
print(timing)
print()
print("类图 (Mermaid)")
print("-" * 50)
print(klass)
