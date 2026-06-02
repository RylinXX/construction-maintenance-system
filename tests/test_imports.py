from __future__ import annotations

from io import BytesIO

from werkzeug.datastructures import FileStorage

from construction_maintenance.services.imports import save_upload


def test_save_upload_preserves_extension_for_chinese_pdf_name(tmp_path):
    file = FileStorage(
        stream=BytesIO(b"%PDF-1.4"),
        filename="身份证.pdf",
        content_type="application/pdf",
    )

    stored = save_upload(tmp_path, file)

    assert stored.suffix == ".pdf"
    assert stored.exists()


def test_import_attendance_workbook(app, tmp_path):
    from openpyxl import Workbook
    from construction_maintenance import repositories as repo
    with app.app_context():
        # 1. 预先创建一名参与考勤的人员
        person_id = repo.create_person(
            {
                "name": "张小丽",
                "id_number": "410000199001018888",
                "is_attendance": 1,
            }
        )
        
        # 2. 内存构造符合格式的导入 Excel 工作簿
        wb = Workbook()
        ws = wb.active
        ws.title = "2026-06 考勤表"
        
        headers = ["姓名", "身份证号"]
        for d in range(1, 31):
            headers.append(f"{d}日")
        headers.extend(["出勤天数", "请假天数"])
        ws.append(headers)
        
        # 预设张小丽的打卡行数据，C列(1日)填 "白"，D列(2日)填 "夜"，E列(3日)填 "假"
        row = ["张小丽", "410000199001018888"]
        row.extend(["白", "夜", "假"])
        row.extend([""] * 27)  # 4日至30日留空
        row.extend([2, 1])     # 统计值
        ws.append(row)
        
        file_path = tmp_path / "import_test.xlsx"
        wb.save(file_path)
        
        # 3. 调用导入函数
        from construction_maintenance.services.imports import import_attendance_workbook
        res = import_attendance_workbook(file_path, "2026-06")
        
        # 确认无错导入
        assert res["status"] == "success"
        
        # 4. 从数据库查询导入的结果
        records = repo.list_attendance_by_month("2026-06")
        assert len(records) == 3
        
        # 校验 1日白班、2日夜班、3日请假
        rec_1 = next(r for r in records if r["work_date"] == "2026-06-01")
        assert rec_1["shift_type"] == "白班"
        
        rec_2 = next(r for r in records if r["work_date"] == "2026-06-02")
        assert rec_2["shift_type"] == "夜班"
        
        rec_3 = next(r for r in records if r["work_date"] == "2026-06-03")
        assert rec_3["shift_type"] == "请假"

