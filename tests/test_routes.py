from __future__ import annotations

from datetime import date
from datetime import timedelta

from construction_maintenance import repositories as repo


def test_dashboard_route_renders(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "建筑工程维护系统".encode("utf-8") in response.data
    assert "项目支出".encode("utf-8") in response.data


def test_project_and_voucher_flow(app, client):
    project_response = client.post(
        "/projects",
        data={
            "name": "土方工程",
            "status": "进行中",
            "owner": "张三",
            "start_date": "2026-05-29",
            "end_date": "",
            "notes": "",
        },
        follow_redirects=True,
    )
    assert project_response.status_code == 200
    assert "土方工程".encode("utf-8") in project_response.data

    with app.app_context():
        project_id = repo.list_projects()[0]["id"]

    voucher_response = client.post(
        "/vouchers",
        data={
            "project_id": str(project_id),
            "voucher_date": "2026-05-29",
            "voucher_type": "材料费用",
            "amount": "2300",
            "notes": "购买材料",
            "entry_user": "财务",
        },
        follow_redirects=True,
    )
    assert voucher_response.status_code == 200
    assert "购买材料".encode("utf-8") in voucher_response.data
    assert "2,300.00".encode("utf-8") in voucher_response.data


def test_project_requires_name(client):
    response = client.post(
        "/projects",
        data={
            "name": "",
            "status": "进行中",
            "owner": "",
            "start_date": "",
            "end_date": "",
            "notes": "",
        },
    )

    assert response.status_code == 400
    assert "项目名称不能为空".encode("utf-8") in response.data


def test_voucher_requires_valid_project_id(client):
    response = client.post(
        "/vouchers",
        data={
            "project_id": "abc",
            "voucher_date": "2026-05-29",
            "voucher_type": "材料费用",
            "amount": "2300",
            "notes": "",
            "entry_user": "",
        },
    )

    assert response.status_code == 400
    assert "项目必须是有效编号".encode("utf-8") in response.data


def test_voucher_rejects_missing_project(app, client):
    with app.app_context():
        missing_project_id = 999

    response = client.post(
        "/vouchers",
        data={
            "project_id": str(missing_project_id),
            "voucher_date": "2026-05-29",
            "voucher_type": "材料费用",
            "amount": "2300",
            "notes": "",
            "entry_user": "",
        },
    )

    assert response.status_code == 400
    assert "项目不存在".encode("utf-8") in response.data


def test_voucher_shows_amount_validation(app, client):
    with app.app_context():
        main_company = repo.get_main_company()
        project_id = repo.create_project(
            {
                "company_id": main_company["id"],
                "name": "土方工程",
                "status": "进行中",
                "owner": "",
                "start_date": "",
                "end_date": "",
                "notes": "",
            }
        )

    response = client.post(
        "/vouchers",
        data={
            "project_id": str(project_id),
            "voucher_date": "2026-05-29",
            "voucher_type": "材料费用",
            "amount": "abc",
            "notes": "",
            "entry_user": "",
        },
    )

    assert response.status_code == 400
    assert "金额必须是数字".encode("utf-8") in response.data


def test_voucher_requires_amount(app, client):
    with app.app_context():
        main_company = repo.get_main_company()
        project_id = repo.create_project(
            {
                "company_id": main_company["id"],
                "name": "土方工程",
                "status": "进行中",
                "owner": "",
                "start_date": "",
                "end_date": "",
                "notes": "",
            }
        )

    response = client.post(
        "/vouchers",
        data={
            "project_id": str(project_id),
            "voucher_date": "2026-05-29",
            "voucher_type": "材料费用",
            "amount": "",
            "notes": "",
            "entry_user": "",
        },
    )

    assert response.status_code == 400
    assert "金额不能为空".encode("utf-8") in response.data


def test_dashboard_month_metrics_exclude_prior_month(app, client):
    today = date.today()
    first_day_of_month = today.replace(day=1)
    prior_month_day = first_day_of_month - timedelta(days=1)

    with app.app_context():
        main_company = repo.get_main_company()
        project_id = repo.create_project(
            {
                "company_id": main_company["id"],
                "name": "土方工程",
                "status": "进行中",
                "owner": "",
                "start_date": "",
                "end_date": "",
                "notes": "",
            }
        )
        for voucher_date, amount in (
            (today.isoformat(), "100"),
            (prior_month_day.isoformat(), "200"),
        ):
            repo.create_voucher(
                {
                    "project_id": project_id,
                    "voucher_date": voucher_date,
                    "voucher_type": "材料费用",
                    "amount": amount,
                    "notes": "",
                    "attachment_path": "",
                    "entry_user": "",
                }
            )

    response = client.get("/")

    assert response.status_code == 200
    assert "¥100.00".encode("utf-8") in response.data
    assert "¥300.00".encode("utf-8") in response.data
    assert b"<strong>1</strong>" in response.data
