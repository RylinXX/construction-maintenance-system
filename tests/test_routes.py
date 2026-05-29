from __future__ import annotations


def test_dashboard_route_renders(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "建筑工程维护系统".encode("utf-8") in response.data
    assert "项目支出".encode("utf-8") in response.data
