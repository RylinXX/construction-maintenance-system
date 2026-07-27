from __future__ import annotations

from construction_maintenance.db import get_db


def test_category_management_routes_and_delete(client, app):
    # Test viewing category management page
    res = client.get("/expense-categories")
    assert res.status_code == 200
    assert "费用科目管理".encode("utf-8") in res.data
    assert "全部收支".encode("utf-8") in res.data
    assert "搜索分类名称...".encode("utf-8") in res.data

    # Create a custom primary category (explicitly pass parent_id="" for root category)
    res = client.post(
        "/expense-categories",
        data={
            "name": "测试一级分类",
            "parent_id": "",
            "transaction_scope": "支出",
            "sort_order": "999",
        },
        follow_redirects=True,
    )
    assert res.status_code == 200
    assert "费用科目已成功添加。".encode("utf-8") in res.data

    with app.app_context():
        root = get_db().execute(
            "select * from expense_categories where name = '测试一级分类'"
        ).fetchone()
        assert root is not None
        root_id = root["id"]
        assert root["parent_id"] is None

    # Create a subcategory under root_id
    res = client.post(
        "/expense-categories",
        data={
            "name": "测试二级分类",
            "parent_id": str(root_id),
            "transaction_scope": "支出",
            "sort_order": "10",
        },
        follow_redirects=True,
    )
    assert res.status_code == 200
    assert "费用科目已成功添加。".encode("utf-8") in res.data

    with app.app_context():
        leaf = get_db().execute(
            "select * from expense_categories where name = '测试二级分类'"
        ).fetchone()
        assert leaf is not None
        leaf_id = leaf["id"]
        assert leaf["parent_id"] == root_id

    # Try deleting root category when it still has child -> Should fail with message
    res = client.post(
        f"/expense-categories/{root_id}/delete",
        follow_redirects=True,
    )
    assert res.status_code == 200
    assert "一级分类仍有二级分类".encode("utf-8") in res.data

    # Delete the unused leaf category -> Should succeed
    res = client.post(
        f"/expense-categories/{leaf_id}/delete",
        follow_redirects=True,
    )
    assert res.status_code == 200
    assert "费用科目已成功删除。".encode("utf-8") in res.data

    with app.app_context():
        leaf_after = get_db().execute(
            "select * from expense_categories where id = ?", (leaf_id,)
        ).fetchone()
        assert leaf_after is None

    # Now delete the root category -> Should succeed
    res = client.post(
        f"/expense-categories/{root_id}/delete",
        follow_redirects=True,
    )
    assert res.status_code == 200
    assert "费用科目已成功删除。".encode("utf-8") in res.data

    with app.app_context():
        root_after = get_db().execute(
            "select * from expense_categories where id = ?", (root_id,)
        ).fetchone()
        assert root_after is None
