from __future__ import annotations

import json
from construction_maintenance.db import get_db
from construction_maintenance import repositories as repo


def test_attendance_page_renders(client):
    # 访问考勤主页面，检验是否渲染
    response = client.get("/attendance")
    assert response.status_code == 200
    assert "施工人员月度考勤表".encode("utf-8") in response.data
    assert "当前月份".encode("utf-8") in response.data


def test_attendance_update_api_workflow(client, app):
    with app.app_context():
        # 1. 先在数据库里创建一个测试人员
        person_id = repo.create_person({
            "name": "铁柱",
            "id_number": "410000199001017777",
            "gender": "男"
        })

    # 2. 正常更新考勤为白班
    response = client.post(
        "/attendance/update",
        data=json.dumps({
            "person_id": person_id,
            "date": "2026-06-05",
            "shift_type": "白班"
        }),
        content_type="application/json"
    )
    assert response.status_code == 200
    res_data = json.loads(response.data.decode("utf-8"))
    assert res_data["status"] == "success"

    # 3. 校验数据库中考勤确实存入
    with app.app_context():
        records = repo.list_attendance_by_month("2026-06")
        assert len(records) == 1
        assert records[0]["person_id"] == person_id
        assert records[0]["work_date"] == "2026-06-05"
        assert records[0]["shift_type"] == "白班"

    # 4. 更新考勤为夜班
    response = client.post(
        "/attendance/update",
        data=json.dumps({
            "person_id": person_id,
            "date": "2026-06-05",
            "shift_type": "夜班"
        }),
        content_type="application/json"
    )
    assert response.status_code == 200
    
    # 5. 校验数据库中考勤确实变更为夜班
    with app.app_context():
        records = repo.list_attendance_by_month("2026-06")
        assert len(records) == 1
        assert records[0]["shift_type"] == "夜班"

    # 5b. 更新考勤为请假
    response = client.post(
        "/attendance/update",
        data=json.dumps({
            "person_id": person_id,
            "date": "2026-06-05",
            "shift_type": "请假"
        }),
        content_type="application/json"
    )
    assert response.status_code == 200

    # 5c. 校验数据库中考勤确实变更为请假
    with app.app_context():
        records = repo.list_attendance_by_month("2026-06")
        assert len(records) == 1
        assert records[0]["shift_type"] == "请假"

    # 6. 发送空或 null 以取消出勤
    response = client.post(
        "/attendance/update",
        data=json.dumps({
            "person_id": person_id,
            "date": "2026-06-05",
            "shift_type": None
        }),
        content_type="application/json"
    )
    assert response.status_code == 200

    # 7. 校验数据库中考勤已被物理删除
    with app.app_context():
        records = repo.list_attendance_by_month("2026-06")
        assert len(records) == 0


def test_attendance_update_api_bad_request(client):
    # 8. 缺省关键参数请求，应返回400
    response = client.post(
        "/attendance/update",
        data=json.dumps({
            "date": "2026-06-05",
            "shift_type": "白班"
        }),
        content_type="application/json"
    )
    assert response.status_code == 400
    res_data = json.loads(response.data.decode("utf-8"))
    assert res_data["status"] == "error"


def test_attendance_settings_workflow(client, app):
    with app.app_context():
        # 1. 建立两个测试人
        person_a = repo.create_person({"name": "参与考勤张", "id_number": "410000199001015555"})
        person_b = repo.create_person({"name": "内勤不考勤李", "id_number": "410000199001016666"})
        
    # 2. 批量将内勤不考勤李设置为不参与考勤 (0)
    response = client.post(
        "/attendance/settings/update",
        data=json.dumps({
            "is_attendance_map": {
                str(person_a): 1,
                str(person_b): 0
            }
        }),
        content_type="application/json"
    )
    assert response.status_code == 200
    res_data = json.loads(response.data.decode("utf-8"))
    assert res_data["status"] == "success"

    # 3. 校验数据库中的 is_attendance 标记状态
    with app.app_context():
        people = repo.list_people()
        pa = next(p for p in people if p["id"] == person_a)
        pb = next(p for p in people if p["id"] == person_b)
        assert pa["is_attendance"] == 1
        assert pb["is_attendance"] == 0

    # 4. 访问考勤大表，确认只显示参与考勤张，不显示内勤不考勤李在表格主体中
    page_res = client.get("/attendance")
    assert page_res.status_code == 200
    
    html_content = page_res.data.decode("utf-8")
    assert 'class="p-name">参与考勤张</span>' in html_content
    assert 'class="p-name">内勤不考勤李</span>' not in html_content


def test_quick_fill_person_attendance(client, app):
    with app.app_context():
        # 1. 创建测试人
        person_id = repo.create_person({
            "name": "快速填报测试人",
            "id_number": "410000199001018888",
            "gender": "男"
        })

    # 2. 正常快捷填报：白班10天，夜班2天，请假1天，工作日优先（2026-06月，共30天，工作日有22天）
    response = client.post(
        "/attendance/quick-fill-person",
        data=json.dumps({
            "person_id": person_id,
            "month": "2026-06",
            "day_shifts": 10,
            "night_shifts": 2,
            "leave_shifts": 1,
            "skip_weekends": True
        }),
        content_type="application/json"
    )
    assert response.status_code == 200
    res_data = json.loads(response.data.decode("utf-8"))
    assert res_data["status"] == "success"

    # 3. 校验数据库中的打卡明细是否为13天，且周末（6月6日、6月7日）应不被填入
    with app.app_context():
        db = repo.get_db()
        records = db.execute(
            "select work_date, shift_type from attendance where person_id = ? order by work_date asc",
            (person_id,),
        ).fetchall()
        
        assert len(records) == 13
        # 6月1日-6月5日（5天工作日）应当有打卡
        # 6月6日、6月7日是周末，应当没有打卡
        filled_dates = [r["work_date"] for r in records]
        assert "2026-06-01" in filled_dates
        assert "2026-06-05" in filled_dates
        assert "2026-06-06" not in filled_dates
        assert "2026-06-07" not in filled_dates
        # 6月8日-6月12日（5天工作日）应当有打卡
        assert "2026-06-08" in filled_dates
        assert "2026-06-12" in filled_dates

    # 4. 自然日顺延平铺：白班3天，夜班2天，自然日顺延（不跳过周末）
    response = client.post(
        "/attendance/quick-fill-person",
        data=json.dumps({
            "person_id": person_id,
            "month": "2026-06",
            "day_shifts": 3,
            "night_shifts": 2,
            "leave_shifts": 0,
            "skip_weekends": False
        }),
        content_type="application/json"
    )
    assert response.status_code == 200
    
    # 5. 校验之前的记录已被清除，共5天，且周末（6月6日周六）也应被填入
    # 因为 6月1日(周一)、6月2日(周二)、6月3日(周三)、6月4日(周四)、6月5日(周五)，一共就只填5天，所以刚好到6月5日。
    # 为了测试填入周末，我们多填一些，例如 8天
    response = client.post(
        "/attendance/quick-fill-person",
        data=json.dumps({
            "person_id": person_id,
            "month": "2026-06",
            "day_shifts": 5,
            "night_shifts": 3,
            "leave_shifts": 0,
            "skip_weekends": False
        }),
        content_type="application/json"
    )
    assert response.status_code == 200
    
    with app.app_context():
        db = repo.get_db()
        records = db.execute(
            "select work_date, shift_type from attendance where person_id = ? order by work_date asc",
            (person_id,),
        ).fetchall()
        assert len(records) == 8
        # 6月1日-6月8日（共8天，包含6月6、7日周末）
        filled_dates = [r["work_date"] for r in records]
        assert "2026-06-06" in filled_dates
        assert "2026-06-07" in filled_dates

    # 6. 异常边界：总天数超出当月天数（35天）
    response = client.post(
        "/attendance/quick-fill-person",
        data=json.dumps({
            "person_id": person_id,
            "month": "2026-06",
            "day_shifts": 30,
            "night_shifts": 5,
            "leave_shifts": 1,
            "skip_weekends": False
        }),
        content_type="application/json"
    )
    assert response.status_code == 400
    res_data = json.loads(response.data.decode("utf-8"))
    assert "超过了当月的总天数" in res_data["message"]
