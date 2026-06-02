from __future__ import annotations

from construction_maintenance.db import get_db


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
    assert "操作".encode("utf-8") in response.data
    assert "编辑".encode("utf-8") in response.data


def test_people_page_uploads_employee_id_card(client, app):
    from io import BytesIO

    response = client.post(
        "/people",
        data={
            "name": "李工",
            "id_number": "410000199001019999",
            "id_card_attachment": (BytesIO(b"fake image"), "id-card.jpg"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "预览身份证".encode("utf-8") in response.data
    assert "立即下载身份证".encode("utf-8") in response.data

    with app.app_context():
        person = get_db().execute(
            "select id_card_path from people where id_number = ?",
            ("410000199001019999",),
        ).fetchone()
        stored_path = app.config["UPLOAD_FOLDER"] / person["id_card_path"]

    assert person["id_card_path"]
    assert stored_path.exists()


def test_upload_preview_infers_pdf_type_for_legacy_extensionless_file(client, app):
    legacy_file = app.config["UPLOAD_FOLDER"] / "legacy_pdf"
    legacy_file.write_bytes(b"%PDF-1.4")

    preview = client.get("/uploads/legacy_pdf")
    download = client.get("/uploads/legacy_pdf?download=1")

    assert preview.status_code == 200
    assert preview.mimetype == "application/pdf"
    assert "legacy.pdf" in download.headers["Content-Disposition"]


def test_qualification_page_creates_qualification(client):
    response = client.post(
        "/qualifications",
        data={
            "company_id": "1",
            "name": "建筑业企业资质",
            "certificate_no": "D300000",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "建筑业企业资质".encode("utf-8") in response.data


def test_export_center_downloads_people_workbook(client):
    response = client.get("/exports/people")

    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


def test_batch_upload_creates_pending_item(client):
    from io import BytesIO

    response = client.post(
        "/batch",
        data={
            "item_type": "voucher",
            "files": (BytesIO(b"%PDF-1.4"), "pay.pdf"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "pay.pdf".encode("utf-8") in response.data
    assert "待确认".encode("utf-8") in response.data
    assert "查看文件".encode("utf-8") in response.data
    assert "暂不支持自动识别 PDF，请人工确认".encode("utf-8") in response.data


def test_batch_upload_records_ocr_result(client, monkeypatch):
    from io import BytesIO

    from construction_maintenance.services.ocr import BatchOcrResult

    def fake_recognize_batch_upload(path, item_type):
        return BatchOcrResult(
            status="已识别",
            data={"voucher_type": "材料费用", "amount": 1200},
            confidence=0.91,
        )

    monkeypatch.setattr(
        "construction_maintenance.web.routes.recognize_batch_upload",
        fake_recognize_batch_upload,
    )

    response = client.post(
        "/batch",
        data={
            "item_type": "voucher",
            "files": (BytesIO(b"fake image"), "pay.jpg"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "已识别".encode("utf-8") in response.data
    assert "材料费用".encode("utf-8") in response.data
    assert "1200".encode("utf-8") in response.data


def test_project_vouchers_detail_page(client):
    # 先建立一个项目和一张凭证
    client.post(
        "/projects",
        data={
            "name": "基坑支护工程",
            "status": "进行中",
        },
        follow_redirects=True,
    )
    client.post(
        "/vouchers",
        data={
            "project_id": "1",
            "voucher_date": "2026-05-29",
            "voucher_type": "电费",
            "amount": "800",
            "notes": "临时用电",
        },
        follow_redirects=True,
    )

    # 访问专属项目费用页面
    response = client.get("/projects/1/vouchers")
    assert response.status_code == 200
    assert "基坑支护工程".encode("utf-8") in response.data
    assert "临时用电".encode("utf-8") in response.data
    assert "800.00".encode("utf-8") in response.data


def test_expense_categories_page_manages_active_voucher_types(client, app):
    response = client.get("/expense-categories")
    assert response.status_code == 200
    assert "费用科目管理".encode("utf-8") in response.data

    create_response = client.post(
        "/expense-categories",
        data={"name": "机械租赁", "sort_order": "25"},
        follow_redirects=True,
    )
    assert create_response.status_code == 200
    assert "机械租赁".encode("utf-8") in create_response.data

    with app.app_context():
        category_id = get_db().execute(
            "select id from expense_categories where name = ?",
            ("机械租赁",),
        ).fetchone()["id"]

    update_response = client.post(
        f"/expense-categories/{category_id}/edit",
        data={"name": "机械租赁", "sort_order": "25"},
        follow_redirects=True,
    )
    assert update_response.status_code == 200
    assert "已停用".encode("utf-8") in update_response.data

    vouchers_response = client.get("/vouchers")
    assert "机械租赁".encode("utf-8") not in vouchers_response.data


def test_edit_company_updates_details(client, app):
    with app.app_context():
        from construction_maintenance.db import init_db
        init_db()

    response = client.post(
        "/companies/1/edit",
        data={
            "name": "新修改的测试主公司",
            "credit_code": "91410100MA3X6789X0",
            "legal_person": "张三",
            "phone": "13888888888",
            "notes": "修改后的测试备注",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "新修改的测试主公司".encode("utf-8") in response.data


def test_add_company_creates_new_company(client, app):
    with app.app_context():
        from construction_maintenance.db import init_db
        init_db()

    response = client.post(
        "/companies/add",
        data={
            "name": "全新测试合作公司",
            "credit_code": "91410100MA3XABC123",
            "legal_person": "李四",
            "phone": "13999999999",
            "notes": "新加的公司备注",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "全新测试合作公司".encode("utf-8") in response.data


def test_delete_company_removes_company(client, app):
    with app.app_context():
        from construction_maintenance.db import init_db
        from construction_maintenance.repositories import create_company
        init_db()
        company_id = create_company({
            "name": "待删除测试公司",
            "credit_code": "",
            "legal_person": "",
            "phone": "",
            "notes": "",
            "is_main": 0
        })

    response = client.post(
        f"/companies/{company_id}/delete",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "待删除测试公司".encode("utf-8") not in response.data


def test_delete_main_company_fails(client, app):
    with app.app_context():
        from construction_maintenance.db import init_db
        init_db()

    response = client.post(
        "/companies/1/delete",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "主公司为系统核心单位，不支持删除。".encode("utf-8") in response.data


def test_delete_company_with_dependencies_fails(client, app):
    with app.app_context():
        from construction_maintenance.db import init_db
        from construction_maintenance.repositories import create_company, create_qualification
        init_db()
        
        company_id = create_company({
            "name": "有关联的合作公司",
            "is_main": 0
        })
        create_qualification({
            "company_id": company_id,
            "name": "测试安全许可证",
            "certificate_no": "AQ-112233",
            "issue_date": "",
            "expiry_date": "",
            "is_long_term": 1,
            "attachment_path": "",
            "notes": ""
        })

    response = client.post(
        f"/companies/{company_id}/delete",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "无法删除该单位".encode("utf-8") in response.data


def test_delete_qualification_removes_entry(client, app):
    with app.app_context():
        from construction_maintenance.db import init_db
        from construction_maintenance.repositories import create_qualification
        init_db()
        qual_id = create_qualification({
            "company_id": 1,
            "name": "测试待删除资质",
            "certificate_no": "AQ-MOCK",
            "issue_date": "",
            "expiry_date": "",
            "is_long_term": 1,
            "attachment_path": "",
            "notes": ""
        })

    response = client.post(
        f"/qualifications/{qual_id}/delete",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "测试待删除资质".encode("utf-8") not in response.data


def test_delete_person_removes_entry(client, app):
    with app.app_context():
        from construction_maintenance.db import init_db
        from construction_maintenance.repositories import create_person
        init_db()
        person_id = create_person({
            "name": "待删除测试施工员",
            "id_number": "11010119900101999X",
            "gender": "男",
            "birth_date": "",
            "age": None,
            "phone": "",
            "address": "",
            "job_type": "",
            "bank_card": "",
            "bank_name": "",
            "entry_date": "",
            "notes": "",
            "id_card_path": ""
        })

    response = client.post(
        f"/people/{person_id}/delete",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "待删除测试施工员".encode("utf-8") not in response.data


def test_delete_project_removes_project_and_vouchers(client, app):
    with app.app_context():
        from construction_maintenance.db import init_db
        from construction_maintenance.repositories import create_project, create_voucher
        init_db()
        project_id = create_project({
            "company_id": 1,
            "name": "待删除测试项目",
            "status": "进行中",
            "owner": "",
            "start_date": "",
            "end_date": "",
            "notes": ""
        })
        create_voucher({
            "project_id": project_id,
            "voucher_date": "2026-05-30",
            "voucher_type": "材料费用",
            "amount": 100.0,
            "notes": "测试凭证",
            "entry_user": ""
        })

    response = client.post(
        f"/projects/{project_id}/delete",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "待删除测试项目".encode("utf-8") not in response.data


def test_confirm_batch_voucher_success(client, app):
    with app.app_context():
        from construction_maintenance.repositories import create_batch_item, create_project, get_batch_item
        project_id = create_project({
            "company_id": 1,
            "name": "确认凭证导入测试项目",
            "status": "进行中",
            "owner": "",
            "start_date": "",
            "end_date": "",
            "notes": ""
        })
        item_id = create_batch_item({
            "item_type": "voucher",
            "source_filename": "receipt_test.jpg",
            "stored_path": "uuid_receipt_test.jpg",
            "status": "已识别",
            "recognized_json": '{"voucher_date": "2026-05-15", "voucher_type": "油费", "amount": 250.0, "notes": "AI提取油费", "confidence": 0.95}',
            "confidence": 0.95
        })

    response = client.post(
        f"/batch/{item_id}/confirm",
        data={
            "project_id": str(project_id),
            "voucher_date": "2026-05-15",
            "voucher_type": "油费",
            "amount": "250.00",
            "notes": "核对后的油费备注",
            "entry_user": "核对人"
        },
        follow_redirects=True
    )
    assert response.status_code == 200
    assert "凭证成功导入项目台账！".encode("utf-8") in response.data

    with app.app_context():
        item = get_batch_item(item_id)
        assert item["status"] == "已确认"

        from construction_maintenance.repositories import list_vouchers
        vouchers = list_vouchers(project_id)
        assert len(vouchers) == 1
        assert vouchers[0]["amount"] == 250.0
        assert vouchers[0]["voucher_type"] == "油费"
        assert vouchers[0]["notes"] == "核对后的油费备注"
        assert vouchers[0]["attachment_path"] == "uuid_receipt_test.jpg"


def test_delete_batch_item_success(client, app):
    with app.app_context():
        from construction_maintenance.repositories import create_batch_item, get_batch_item
        item_id = create_batch_item({
            "item_type": "voucher",
            "source_filename": "delete_test.jpg",
            "stored_path": "uuid_delete_test.jpg",
            "status": "待确认",
            "recognized_json": "{}",
            "confidence": None
        })

    response = client.post(
        f"/batch/{item_id}/delete",
        follow_redirects=True
    )
    assert response.status_code == 200
    assert "批量上传记录已成功忽略并删除。".encode("utf-8") in response.data

    with app.app_context():
        item = get_batch_item(item_id)
        assert item is None


def test_confirm_batch_qualification_success_existing_company(client, app):
    with app.app_context():
        from construction_maintenance.repositories import create_batch_item, create_company
        company_id = create_company({
            "name": "测试老公司",
            "credit_code": "91410100MA3X6789X0",
            "legal_person": "老张",
            "phone": "13888888888",
            "notes": "",
            "is_main": 0
        })

        item_id = create_batch_item({
            "item_type": "qualification",
            "source_filename": "license_test.jpg",
            "stored_path": "uuid_license_test.jpg",
            "status": "已识别",
            "recognized_json": '{"name_select": "营业执照", "certificate_no": "91410100MA3X6789X0", "is_long_term": true}',
            "confidence": 0.95
        })

    response = client.post(
        f"/batch/{item_id}/confirm",
        data={
            "company_id": str(company_id),
            "company_name": "",
            "name_select": "营业执照",
            "name_custom": "",
            "certificate_no": "91410100MA3X6789X0",
            "issue_date": "2018-05-10",
            "expiry_date": "",
            "is_long_term": "1",
            "notes": "营业执照核对导入备注"
        },
        follow_redirects=True
    )
    assert response.status_code == 200
    assert "企业资质证书成功导入资质库！".encode("utf-8") in response.data

    with app.app_context():
        from construction_maintenance.repositories import get_batch_item, list_qualifications
        item = get_batch_item(item_id)
        assert item["status"] == "已确认"

        quals = list_qualifications()
        qual = [q for q in quals if q["certificate_no"] == "91410100MA3X6789X0"]
        assert len(qual) == 1
        assert qual[0]["company_id"] == company_id
        assert qual[0]["name"] == "营业执照"
        assert qual[0]["is_long_term"] == 1
        assert qual[0]["notes"] == "营业执照核对导入备注"


def test_confirm_batch_qualification_success_new_company(client, app):
    with app.app_context():
        from construction_maintenance.repositories import create_batch_item
        item_id = create_batch_item({
            "item_type": "qualification",
            "source_filename": "new_license_test.jpg",
            "stored_path": "uuid_new_license_test.jpg",
            "status": "已识别",
            "recognized_json": '{"name_select": "营业执照", "certificate_no": "91410100MA4B4567X1", "is_long_term": true}',
            "confidence": 0.95
        })

    response = client.post(
        f"/batch/{item_id}/confirm",
        data={
            "company_id": "",
            "company_name": "测试新合作公司",
            "name_select": "营业执照",
            "name_custom": "",
            "certificate_no": "91410100MA4B4567X1",
            "issue_date": "2020-03-15",
            "expiry_date": "",
            "is_long_term": "1",
            "credit_code": "91410100MA4B4567X1",
            "legal_person": "李新",
            "phone": "13999999999",
            "notes": "新公司营业执照备注"
        },
        follow_redirects=True
    )
    assert response.status_code == 200
    assert "企业资质证书成功导入资质库！".encode("utf-8") in response.data

    with app.app_context():
        from construction_maintenance.repositories import get_batch_item, list_qualifications, list_companies
        item = get_batch_item(item_id)
        assert item["status"] == "已确认"

        companies = list_companies()
        comp = [c for c in companies if c["name"] == "测试新合作公司"]
        assert len(comp) == 1
        assert comp[0]["credit_code"] == "91410100MA4B4567X1"
        assert comp[0]["legal_person"] == "李新"
        assert comp[0]["phone"] == "13999999999"

        quals = list_qualifications()
        qual = [q for q in quals if q["certificate_no"] == "91410100MA4B4567X1"]
        assert len(qual) == 1
        assert qual[0]["company_id"] == comp[0]["id"]
        assert qual[0]["name"] == "营业执照"
        assert qual[0]["is_long_term"] == 1
        assert qual[0]["notes"] == "新公司营业执照备注"


def test_contract_routes(client, app):
    with app.app_context():
        from construction_maintenance import repositories as repo
        from construction_maintenance.db import init_db
        init_db()
        
        # 1. 访问合同管理页面
        res = client.get("/contracts")
        assert res.status_code == 200
        assert "合同".encode("utf-8") in res.data
        
        # 获取主公司和创建项目
        main_company = repo.get_main_company()
        proj_id = repo.create_project({
            "company_id": main_company["id"],
            "name": "新路由测试项目",
            "status": "进行中"
        })
        
        # 2. 新增合同提交
        res = client.post("/contracts", data={
            "name": "新路由测试合同",
            "project_id": str(proj_id),
            "contract_type": "材料商合同",
            "notes": "路由测试备注"
        }, follow_redirects=True)
        assert res.status_code == 200
        assert "新路由测试合同".encode("utf-8") in res.data
        
        # 获取刚才创建的合同
        contracts = repo.list_contracts(query="新路由测试合同")
        assert len(contracts) > 0
        c_id = contracts[0]["id"]
        
        # 3. 编辑合同
        res = client.post(f"/contracts/{c_id}/edit", data={
            "name": "编辑后路由测试合同",
            "project_id": str(proj_id),
            "contract_type": "总包合同",
            "notes": "编辑备注"
        }, follow_redirects=True)
        assert res.status_code == 200
        assert "编辑后路由测试合同".encode("utf-8") in res.data
        
        # 4. SVG 证书生成测试 (由于没有物理文件，系统应生成 SVG 模拟合同)
        # 先更新合同关联的附件名称为特定值，然后下载它
        repo.update_contract(c_id, {
            "project_id": proj_id,
            "name": "编辑后路由测试合同",
            "contract_type": "总包合同",
            "notes": "编辑备注",
            "attachment_path": "test_contract_file.pdf"
        })
        res = client.get(f"/uploads/test_contract_file.pdf")
        assert res.status_code == 200
        assert b"svg" in res.data
        assert "合同".encode("utf-8") in res.data
        
        # 5. 删除合同
        res = client.post(f"/contracts/{c_id}/delete", follow_redirects=True)
        assert res.status_code == 200
        assert "编辑后路由测试合同".encode("utf-8") not in res.data


