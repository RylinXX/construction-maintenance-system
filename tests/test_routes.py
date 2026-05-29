from __future__ import annotations


def test_dashboard_route_renders(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "建筑工程维护系统".encode("utf-8") in response.data
    assert "项目支出".encode("utf-8") in response.data


def test_project_and_voucher_flow(client):
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

    voucher_response = client.post(
        "/vouchers",
        data={
            "project_id": "1",
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


def test_people_page_creates_person(client):
    response = client.post(
        "/people",
        data={
            "name": "王小明",
            "id_number": "410000199001011234",
            "phone": "13800000000",
            "job_type": "普工",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "王小明".encode("utf-8") in response.data
