from __future__ import annotations

import pytest

from construction_maintenance import repositories as repo


def create_project_with_voucher(
    company_id: int,
    project_name: str,
    amount: int,
) -> tuple[int, int]:
    project_id = repo.create_project(
        {
            "company_id": company_id,
            "name": project_name,
            "status": "\u8fdb\u884c\u4e2d",
            "owner": "",
            "start_date": "2026-05-29",
            "end_date": "",
            "notes": "",
        }
    )
    voucher_id = repo.create_voucher(
        {
            "project_id": project_id,
            "voucher_date": "2026-05-29",
            "voucher_type": "\u6750\u6599\u8d39\u7528",
            "amount": amount,
            "notes": "",
            "attachment_path": "",
            "entry_user": "",
        }
    )
    return project_id, voucher_id


def test_create_project_and_voucher(app):
    with app.app_context():
        main_company = repo.get_main_company()
        project_id = repo.create_project(
            {
                "company_id": main_company["id"],
                "name": "\u571f\u65b9\u5de5\u7a0b",
                "status": "\u8fdb\u884c\u4e2d",
                "owner": "\u5f20\u4e09",
                "start_date": "2026-05-29",
                "end_date": "",
                "notes": "",
            }
        )
        voucher_id = repo.create_voucher(
            {
                "project_id": project_id,
                "voucher_date": "2026-05-29",
                "voucher_type": "\u6750\u6599\u8d39\u7528",
                "amount": 2300,
                "notes": "\u8d2d\u4e70\u6750\u6599",
                "attachment_path": "",
                "entry_user": "\u8d22\u52a1",
            }
        )
        vouchers = repo.list_vouchers(project_id=project_id)

    assert voucher_id > 0
    assert vouchers[0]["project_name"] == "\u571f\u65b9\u5de5\u7a0b"
    assert vouchers[0]["amount"] == 2300


def test_voucher_amount_validation():
    with pytest.raises(ValueError, match="\u91d1\u989d\u5fc5\u987b\u5927\u4e8e 0"):
        repo.normalize_amount("0")


def test_list_vouchers_returns_all_without_project_id(app):
    with app.app_context():
        main_company = repo.get_main_company()
        create_project_with_voucher(main_company["id"], "\u571f\u65b9\u5de5\u7a0b", 100)
        create_project_with_voucher(main_company["id"], "\u6c34\u7535\u5de5\u7a0b", 200)

        vouchers = repo.list_vouchers()

    assert len(vouchers) == 2
    assert {voucher["project_name"] for voucher in vouchers} == {
        "\u571f\u65b9\u5de5\u7a0b",
        "\u6c34\u7535\u5de5\u7a0b",
    }


def test_list_vouchers_filters_by_project_id(app):
    with app.app_context():
        main_company = repo.get_main_company()
        project_id, voucher_id = create_project_with_voucher(
            main_company["id"], "\u571f\u65b9\u5de5\u7a0b", 100
        )
        create_project_with_voucher(main_company["id"], "\u6c34\u7535\u5de5\u7a0b", 200)

        vouchers = repo.list_vouchers(project_id=project_id)

    assert [voucher["id"] for voucher in vouchers] == [voucher_id]
    assert vouchers[0]["project_name"] == "\u571f\u65b9\u5de5\u7a0b"


def test_list_vouchers_project_id_zero_returns_empty(app):
    with app.app_context():
        main_company = repo.get_main_company()
        create_project_with_voucher(main_company["id"], "\u571f\u65b9\u5de5\u7a0b", 100)

        vouchers = repo.list_vouchers(project_id=0)

    assert vouchers == []


def test_voucher_amount_must_be_numeric():
    with pytest.raises(ValueError, match="\u91d1\u989d\u5fc5\u987b\u662f\u6570\u5b57"):
        repo.normalize_amount("abc")


@pytest.mark.parametrize("value", ["inf", "nan"])
def test_voucher_amount_must_be_finite(value):
    with pytest.raises(ValueError, match="\u91d1\u989d\u5fc5\u987b\u662f\u6570\u5b57"):
        repo.normalize_amount(value)
