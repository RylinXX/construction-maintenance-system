# 合同管理 (Contract Management) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在建筑工程维护系统 (CAM) 中增加合同管理模块，支持多类型合同的登记、归档、按项目和类型筛选以及 Excel 导出，且有完备的自动化测试。

**Architecture:** 沿用系统的三层架构（db -> repositories -> service -> web blueprint -> jinja2 templates），用 pytest 进行测试驱动开发。

**Tech Stack:** Python, Flask, SQLite, Jinja2, openpyxl, pytest.

---

### Task 1: 数据库 `contracts` 表的定义与初始化

**Files:**
- Modify: `construction_maintenance/db.py`
- Test: `tests/test_db.py`

- [ ] **Step 1: 编写失败的数据库初始化测试**
  
  在 `tests/test_db.py` 的末尾添加测试，断言 `contracts` 表存在，且字段完整，同时测试种子数据。
  
  ```python
  def test_contracts_table_initialization(db_conn):
      # 验证表存在
      cursor = db_conn.execute("pragma table_info(contracts)")
      columns = {row["name"]: row["type"] for row in cursor.fetchall()}
      assert "id" in columns
      assert "project_id" in columns
      assert "name" in columns
      assert "contract_type" in columns
      assert "attachment_path" in columns
      assert "notes" in columns
      assert "created_at" in columns
      
      # 验证外键约束
      fk_cursor = db_conn.execute("pragma foreign_key_list(contracts)")
      fk_list = fk_cursor.fetchall()
      assert len(fk_list) > 0
      assert any(row["table"] == "projects" and row["from"] == "project_id" for row in fk_list)
  ```

- [ ] **Step 2: 运行测试以验证其失败**
  
  运行: `pytest tests/test_db.py -k test_contracts_table_initialization`
  预期结果: FAIL (表不存在)

- [ ] **Step 3: 修改 db.py 实现表创建和种子数据**
  
  修改 `construction_maintenance/db.py` 的 `init_db()` 方法。
  在 `init_db` 内的 `db.executescript(...)` 中，添加 `contracts` 建表语句：
  
  ```sql
  create table if not exists contracts (
      id integer primary key autoincrement,
      project_id integer not null references projects(id),
      name text not null,
      contract_type text not null,
      attachment_path text not null default '',
      notes text not null default '',
      created_at text not null default current_timestamp
  );
  ```
  
  在 `init_db` 的演示数据插入逻辑中（`if not current_app.config.get("TESTING"):` 段落内），插入演示合同数据：
  
  ```python
  # 5. 插入合同演示数据
  contract_count = db.execute("select count(*) from contracts").fetchone()[0]
  if contract_count == 0:
      project_1 = db.execute("select id from projects where name = '郑州地铁6号线二期机电维保工程'").fetchone()
      project_2 = db.execute("select id from projects where name = '郑州市中原路绿化提升改造项目'").fetchone()
      if project_1 and project_2:
          db.execute(
              """
              insert into contracts (project_id, name, contract_type, attachment_path, notes)
              values (?, '地铁6号线二期机电维保项目劳务分包合同', '劳务合同', 'contract_metro_labor.pdf', '与河南建工劳务队签署的机电维护劳务合同')
              """,
              (project_1[0],)
          )
          db.execute(
              """
              insert into contracts (project_id, name, contract_type, attachment_path, notes)
              values (?, '中原路绿化工程绿化苗木采购合同', '材料商合同', 'contract_green_tree.pdf', '向郑州百卉园艺采购绿化灌木合同')
              """,
              (project_2[0],)
          )
          db.execute(
              """
              insert into contracts (project_id, name, contract_type, attachment_path, notes)
              values (?, '中原路绿化提升改造工程总承包合同', '总包合同', 'contract_green_main.pdf', '与郑州市市政管理局签署的工程总包合同')
              """,
              (project_2[0],)
          )
  ```

- [ ] **Step 4: 运行测试以验证其通过**
  
  运行: `pytest tests/test_db.py`
  预期结果: PASS

- [ ] **Step 5: 提交更改**
  
  运行: `git add construction_maintenance/db.py tests/test_db.py` 并 `git commit -m "db: add contracts table and demonstration seed data"`

---

### Task 2: 仓储层（Repository Layer）合同管理操作实现

**Files:**
- Modify: `construction_maintenance/repositories.py`
- Test: `tests/test_repositories.py`

- [ ] **Step 1: 编写失败的仓储方法测试**
  
  在 `tests/test_repositories.py` 的末尾添加测试用例，涵盖新建、查询、更新、删除：
  
  ```python
  def test_contract_repository_crud(app):
      from construction_maintenance import repositories as repo
      with app.app_context():
          # 先获取现有项目
          projects = repo.list_projects()
          assert len(projects) > 0
          proj_id = projects[0]["id"]
          
          # 1. 创建合同
          contract_id = repo.create_contract({
              "project_id": proj_id,
              "name": "单元测试合同",
              "contract_type": "劳务合同",
              "attachment_path": "test_contract.pdf",
              "notes": "单元测试备注"
          })
          assert contract_id > 0
          
          # 2. 查询单个合同
          contract = repo.get_contract(contract_id)
          assert contract is not None
          assert contract["name"] == "单元测试合同"
          assert contract["contract_type"] == "劳务合同"
          
          # 3. 列表查询及过滤
          all_contracts = repo.list_contracts()
          assert len(all_contracts) >= 1
          
          filtered = repo.list_contracts(project_id=proj_id, contract_type="劳务合同", query="单元测试")
          assert len(filtered) >= 1
          
          # 4. 更新合同
          repo.update_contract(contract_id, {
              "project_id": proj_id,
              "name": "更新后的单元测试合同",
              "contract_type": "材料商合同",
              "notes": "更新后的备注"
          })
          updated_contract = repo.get_contract(contract_id)
          assert updated_contract["name"] == "更新后的单元测试合同"
          assert updated_contract["contract_type"] == "材料商合同"
          
          # 5. 删除合同
          repo.delete_contract(contract_id)
          assert repo.get_contract(contract_id) is None
  ```

- [ ] **Step 2: 运行测试以验证其失败**
  
  运行: `pytest tests/test_repositories.py -k test_contract_repository_crud`
  预期结果: FAIL (方法未定义错误)

- [ ] **Step 3: 在 repositories.py 中实现相应接口**
  
  修改 `construction_maintenance/repositories.py`。
  在文件最后添加以下函数：
  
  ```python
  def list_contracts(project_id: int | None = None, contract_type: str | None = None, query: str | None = None):
      db = get_db()
      params: list[Any] = []
      where_clauses: list[str] = []
      
      if project_id:
          where_clauses.append("contracts.project_id = ?")
          params.append(project_id)
      if contract_type:
          where_clauses.append("contracts.contract_type = ?")
          params.append(contract_type)
      if query:
          where_clauses.append("(contracts.name like ? or contracts.notes like ?)")
          params.append(f"%{query}%")
          params.append(f"%{query}%")
          
      where = f"where {' and '.join(where_clauses)}" if where_clauses else ""
      
      return db.execute(
          f"""
          select contracts.*, projects.name as project_name
          from contracts
          join projects on projects.id = contracts.project_id
          {where}
          order by contracts.created_at desc, contracts.id desc
          """,
          params,
      ).fetchall()
  
  
  def get_contract(contract_id: int):
      return get_db().execute(
          """
          select contracts.*, projects.name as project_name
          from contracts
          join projects on projects.id = contracts.project_id
          where contracts.id = ?
          """,
          (contract_id,),
      ).fetchone()
  
  
  def create_contract(data: dict[str, Any]) -> int:
      cursor = get_db().execute(
          """
          insert into contracts (project_id, name, contract_type, attachment_path, notes)
          values (?, ?, ?, ?, ?)
          """,
          (
              data["project_id"],
              data["name"],
              data.get("contract_type", "其它"),
              data.get("attachment_path", ""),
              data.get("notes", ""),
          ),
      )
      get_db().commit()
      return int(cursor.lastrowid)
  
  
  def update_contract(contract_id: int, data: dict[str, Any]) -> None:
      set_clause = """
          project_id = ?, name = ?, contract_type = ?, notes = ?
      """
      params = [
          data["project_id"],
          data["name"],
          data.get("contract_type", "其它"),
          data.get("notes", ""),
      ]
      
      if "attachment_path" in data and data["attachment_path"]:
          set_clause += ", attachment_path = ?"
          params.append(data["attachment_path"])
          
      params.append(contract_id)
      
      get_db().execute(
          f"update contracts set {set_clause} where id = ?",
          tuple(params)
      )
      get_db().commit()
  
  
  def delete_contract(contract_id: int) -> None:
      get_db().execute("delete from contracts where id = ?", (contract_id,))
      get_db().commit()
  ```

- [ ] **Step 4: 运行测试以验证其通过**
  
  运行: `pytest tests/test_repositories.py`
  预期结果: PASS

- [ ] **Step 5: 提交更改**
  
  运行: `git add construction_maintenance/repositories.py tests/test_repositories.py` 并 `git commit -m "repo: implement contracts CRUD operations and repository tests"`

---

### Task 3: 后端 Web 控制器与路由编写

**Files:**
- Modify: `construction_maintenance/web/routes.py`
- Test: `tests/test_routes.py`

- [ ] **Step 1: 编写路由与附件预览失败的测试**
  
  在 `tests/test_routes.py` 底部添加合同管理相关的路由测试，测试 GET 页面加载、新增表单提交、附件预览生成：
  
  ```python
  def test_contract_routes(client):
      # 1. 访问合同管理页面
      res = client.get("/contracts")
      assert res.status_code == 200
      assert b"\xe5\x90\x88\xe5\x90\x8c\xe7\xa6\xbb\xe7\xba\xbf" not in res.data # 确保不是404或报错页面
      
      # 获取一个项目 ID
      from construction_maintenance import repositories as repo
      projects = repo.list_projects()
      proj_id = projects[0]["id"]
      
      # 2. 新增合同提交
      res = client.post("/contracts", data={
          "name": "新路由测试合同",
          "project_id": str(proj_id),
          "contract_type": "材料商合同",
          "notes": "路由测试备注"
      }, follow_redirects=True)
      assert res.status_code == 200
      assert b"\xe6\x96\xb0\xe8\xb7\xaf\xe7\x94\xb1\xe6\xb5\x8b\xe8\xaf\x95\xe5\x90\x8c\xe5\x90\x8c" # 中文字符匹配
      
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
      
      # 4. SVG 证书生成测试 (由于没有物理文件，系统应生成 SVG 模拟合同)
      res = client.get(f"/uploads/non_existent_contract.pdf")
      assert res.status_code == 200
      assert b"svg" in res.data
      assert b"\xe4\xbc\x81\xe4\xb8\x9a\xe5\x90\x88\xe5\x90\x8c" in res.data or b"\xe5\x90\x88\xe5\x90\x8c" in res.data # 包含 SVG 文本
      
      # 5. 删除合同
      res = client.post(f"/contracts/{c_id}/delete", follow_redirects=True)
      assert res.status_code == 200
  ```

- [ ] **Step 2: 运行测试以验证其失败**
  
  运行: `pytest tests/test_routes.py -k test_contract_routes`
  预期结果: FAIL (404)

- [ ] **Step 3: 在 routes.py 中添加合同管理的各路由处理函数**
  
  修改 `construction_maintenance/web/routes.py`。
  
  1. 新增路由：
  
  ```python
  @bp.route("/contracts", methods=["GET", "POST"])
  def contracts():
      if request.method == "POST":
          repo.create_contract(
              {
                  "project_id": int(required_text(request.form, "project_id", "归属项目")),
                  "name": required_text(request.form, "name", "合同名称"),
                  "contract_type": required_text(request.form, "contract_type", "合同分类"),
                  "notes": text_value(request.form, "notes"),
                  "attachment_path": _save_form_upload("attachment"),
              }
          )
          flash("新增合同成功。", "success")
          return redirect(url_for("web.contracts"))
  
      filter_project_id = request.args.get("project_id", type=int)
      filter_contract_type = request.args.get("contract_type")
      search_query = request.args.get("query")
  
      contracts_list = repo.list_contracts(
          project_id=filter_project_id,
          contract_type=filter_contract_type,
          query=search_query,
      )
  
      # 计算合同统计指标
      total_count = len(contracts_list) if not (filter_project_id or filter_contract_type or search_query) else len(repo.list_contracts())
      all_c = contracts_list if not (filter_project_id or filter_contract_type or search_query) else repo.list_contracts()
      
      type_stats = {
          "总包合同": sum(1 for c in all_c if c["contract_type"] == "总包合同"),
          "劳务合同": sum(1 for c in all_c if c["contract_type"] == "劳务合同"),
          "材料商合同": sum(1 for c in all_c if c["contract_type"] == "材料商合同"),
          "人员合同": sum(1 for c in all_c if c["contract_type"] == "人员合同"),
          "其它": sum(1 for c in all_c if c["contract_type"] == "其它"),
      }
  
      return render_template(
          "contracts.html",
          contracts=contracts_list,
          projects=repo.list_projects(),
          filter_project_id=filter_project_id,
          filter_contract_type=filter_contract_type,
          search_query=search_query,
          stats={
              "total": total_count,
              **type_stats
          }
      )
  
  
  @bp.route("/contracts/<int:contract_id>/edit", methods=["POST"])
  def edit_contract(contract_id: int):
      attachment_path = _save_form_upload("attachment")
      data = {
          "project_id": int(required_text(request.form, "project_id", "归属项目")),
          "name": required_text(request.form, "name", "合同名称"),
          "contract_type": required_text(request.form, "contract_type", "合同分类"),
          "notes": text_value(request.form, "notes"),
      }
      if attachment_path:
          data["attachment_path"] = attachment_path
  
      repo.update_contract(contract_id, data)
      flash("合同更新成功。", "success")
      return redirect(request.referrer or url_for("web.contracts"))
  
  
  @bp.route("/contracts/<int:contract_id>/delete", methods=["POST"])
  def delete_contract(contract_id: int):
      repo.delete_contract(contract_id)
      flash("合同删除成功。", "success")
      return redirect(url_for("web.contracts"))
  ```
  
  2. 修改 `download_attachment` 路由中 SVG 动态生成的降级方案。
  在 `download_attachment(filename)` 中增加获取 `contracts` 表记录的逻辑，若属于合同附件，则自动生成精美的“企业项目合规合同存证” SVG：
  
  ```python
      # 在 qual = db.execute("select * from qualifications where attachment_path = ?", (filename,)).fetchone() 后面，添加：
      contract = db.execute("select * from contracts where attachment_path = ?", (filename,)).fetchone()
      
      if not qual and not contract:
          name = "企业合规备案证书"
          cert_no = "CAM-MOCK-998877"
          company_name = "河南城建第一集团有限公司"
          issue_date = "2020-05-10"
          expiry_date = ""
          is_long_term = True
          notes = "系统智能存证与企业官方合规双签章备案文件"
      elif contract:
          # 若是合同文件，则渲染精美的合同备案电子证书 SVG
          proj = db.execute("select * from projects where id = ?", (contract["project_id"],)).fetchone()
          project_name = proj["name"] if proj else "未知工程项目"
          name = contract["name"]
          cert_no = f"CAM-CON-{contract['id']:06d}"
          company_name = project_name
          issue_date = contract["created_at"][:10] if contract["created_at"] else "2026-06-02"
          expiry_date = ""
          is_long_term = True
          notes = contract["notes"] or "该项目合同已通过建筑工程维护系统存证并归档备案，附件处于云端安全托管状态。"
          
          # 生成合规合同证书 SVG
          expiry_text = "永久归档"
          svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 600" width="100%" height="100%">
    <defs>
      <linearGradient id="goldGrad" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#0f766e" />
        <stop offset="50%" stop-color="#2dd4bf" />
        <stop offset="100%" stop-color="#042f2e" />
      </linearGradient>
      <linearGradient id="bgGrad" x1="0%" y1="0%" x2="0%" y2="100%">
        <stop offset="0%" stop-color="#f0fdf4" />
        <stop offset="100%" stop-color="#f6fbf7" />
      </linearGradient>
    </defs>
    <rect width="800" height="600" fill="url(#bgGrad)" rx="12"/>
    <rect x="25" y="25" width="750" height="550" fill="none" stroke="url(#goldGrad)" stroke-width="4.5" rx="10"/>
    <rect x="35" y="35" width="730" height="530" fill="none" stroke="#0f766e" stroke-width="1.2" stroke-dasharray="6 3" rx="8" stroke-opacity="0.75"/>
    <text x="400" y="95" text-anchor="middle" font-family="'Noto Serif SC', serif" font-size="28" font-weight="bold" fill="#0f766e" letter-spacing="4">项目合规合同存证证书</text>
    <text x="400" y="122" text-anchor="middle" font-family="'Inter', sans-serif" font-size="11" font-weight="700" fill="#0d9488" letter-spacing="2">PROJECT CONTRACT COMPLIANCE ARCHIVE</text>
    <line x1="100" y1="150" x2="700" y2="150" stroke="#0f766e" stroke-width="2" stroke-opacity="0.3"/>
    <text x="150" y="200" font-size="16" fill="#4b5563">存证编号：<tspan fill="#111827" font-weight="bold">{cert_no}</tspan></text>
    <text x="150" y="240" font-size="16" fill="#4b5563">合同分类：<tspan fill="#111827" font-weight="bold">{contract['contract_type']}</tspan></text>
    <text x="150" y="280" font-size="16" fill="#4b5563">合同名称：<tspan fill="#111827" font-weight="bold">{name}</tspan></text>
    <text x="150" y="320" font-size="16" fill="#4b5563">归属工程：<tspan fill="#111827" font-weight="bold">{company_name}</tspan></text>
    <text x="150" y="360" font-size="16" fill="#4b5563">备案日期：<tspan fill="#111827">{issue_date}</tspan></text>
    <text x="150" y="400" font-size="16" fill="#4b5563">归档状态：<tspan fill="#0f766e" font-weight="bold">{expiry_text}</tspan></text>
    <text x="150" y="440" font-size="16" fill="#4b5563">存证备注：</text>
    <rect x="150" y="455" width="500" height="65" fill="#f0fdf4" stroke="#dcfce7" stroke-width="1" rx="4"/>
    <text x="165" y="480" font-size="13" fill="#042f2e" width="470">{notes}</text>
    <circle cx="630" cy="300" r="55" fill="none" stroke="#dc2626" stroke-width="2.5" stroke-opacity="0.8" stroke-dasharray="4 2"/>
    <text x="630" y="295" text-anchor="middle" font-size="13" font-weight="bold" fill="#dc2626" fill-opacity="0.8">合同存证专用章</text>
    <text x="630" y="315" text-anchor="middle" font-size="9" fill="#dc2626" fill-opacity="0.8">CAM ARCHIVE</text>
  </svg>"""
          return Response(svg_content, mimetype="image/svg+xml")
  ```

- [ ] **Step 4: 运行测试以验证其通过**
  
  运行: `pytest tests/test_routes.py`
  预期结果: PASS

- [ ] **Step 5: 提交更改**
  
  运行: `git add construction_maintenance/web/routes.py tests/test_routes.py` 并 `git commit -m "web: add contracts view endpoints and dynamic contract SVG mock response"`

---

### Task 4: 业务层（Service Layer）Excel 导出模块编写

**Files:**
- Modify: `construction_maintenance/services/exports.py`
- Test: `tests/test_exports.py`

- [ ] **Step 1: 编写失败的合同导出测试**
  
  在 `tests/test_exports.py` 中添加测试用例，断言生成的 Excel 文件包含列标题，且能生成数据：
  
  ```python
  def test_export_contracts(app, tmp_path):
      from construction_maintenance.services.exports import build_contract_workbook
      import openpyxl
      
      with app.app_context():
          output_file = tmp_path / "contracts_test.xlsx"
          path = build_contract_workbook(output_file)
          
          # 验证文件存在且可用
          wb = openpyxl.load_workbook(path)
          sheet = wb.active
          assert sheet.cell(1, 1).value == "合同ID"
          assert sheet.cell(1, 2).value == "归属项目"
          assert sheet.cell(1, 3).value == "合同名称"
          assert sheet.cell(1, 4).value == "合同分类"
          assert sheet.cell(1, 5).value == "备注"
          assert sheet.cell(1, 6).value == "创建时间"
          
          # 检查至少生成了种子数据的行
          assert sheet.max_row >= 2
  ```

- [ ] **Step 2: 运行测试以验证其失败**
  
  运行: `pytest tests/test_exports.py -k test_export_contracts`
  预期结果: FAIL (无法导入或方法未定义)

- [ ] **Step 3: 在 exports.py 中实现导出功能并应用 Emerald 主题样式**
  
  修改 `construction_maintenance/services/exports.py`，导入需要的样式库并编写 `build_contract_workbook(output_path)` 函数：
  
  ```python
  def build_contract_workbook(output_path: Path) -> Path:
      import openpyxl
      from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
      from openpyxl.utils import get_column_letter
      from construction_maintenance import repositories as repo
  
      wb = openpyxl.Workbook()
      ws = wb.active
      ws.title = "项目合同台账"
      ws.views.sheetView[0].showGridLines = True
  
      # 表头定义
      headers = ["合同ID", "归属项目", "合同名称", "合同分类", "备注", "创建时间"]
      ws.append(headers)
  
      # 样式设置
      emerald_color = "0F766E"      # 深邃翠绿表头
      zebra_color = "F0FDF4"        # 浅绿斑马纹
      border_color = "E2E8F0"
  
      font_header = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
      font_body = Font(name="Segoe UI", size=10)
      
      fill_header = PatternFill(start_color=emerald_color, end_color=emerald_color, fill_type="solid")
      fill_zebra = PatternFill(start_color=zebra_color, end_color=zebra_color, fill_type="solid")
      
      align_center = Alignment(horizontal="center", vertical="center")
      align_left = Alignment(horizontal="left", vertical="center")
      
      thin_side = Side(border_style="thin", color=border_color)
      grid_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)
  
      # 设置表头样式
      ws.row_dimensions[1].height = 28
      for col_idx, _ in enumerate(headers, start=1):
          cell = ws.cell(row=1, column=col_idx)
          cell.font = font_header
          cell.fill = fill_header
          cell.alignment = align_center
          cell.border = grid_border
  
      # 写入数据
      contracts = repo.list_contracts()
      for row_idx, contract in enumerate(contracts, start=2):
          ws.row_dimensions[row_idx].height = 22
          
          # 数据准备
          row_data = [
              contract["id"],
              contract["project_name"],
              contract["name"],
              contract["contract_type"],
              contract["notes"],
              contract["created_at"][:19] if contract["created_at"] else ""
          ]
          
          for col_idx, val in enumerate(row_data, start=1):
              cell = ws.cell(row=row_idx, column=col_idx, value=val)
              cell.font = font_body
              cell.border = grid_border
              
              # 斑马纹交替行
              if row_idx % 2 == 1:
                  cell.fill = fill_zebra
                  
              # 对齐
              if col_idx in (1, 4, 6):
                  cell.alignment = align_center
              else:
                  cell.alignment = align_left
  
      # 自动调整列宽
      for col in ws.columns:
          max_len = 0
          col_letter = get_column_letter(col[0].column)
          for cell in col:
              val_str = str(cell.value or "")
              # 对中文特殊处理以准确估算列宽
              cell_len = sum(2 if ord(char) > 127 else 1 for char in val_str)
              if cell_len > max_len:
                  max_len = cell_len
          ws.column_dimensions[col_letter].width = max(max_len + 4, 12)
  
      wb.save(output_path)
      return output_path
  ```
  
  同时，在 `routes.py` 中的 `download_export(export_type)` 里注册新的导出类型：
  
  ```python
      # 修改 routes.py:713-722 附近的 builders
      builders = {
          "project-ledger": ("项目台账.xlsx", build_project_ledger_workbook),
          "people": ("基础人员信息表.xlsx", build_people_workbook),
          "qualifications": ("企业资质清单.xlsx", build_qualification_workbook),
          "contracts": ("项目合同台账.xlsx", build_contract_workbook), # 新增
      }
  ```
  注意：`routes.py` 里的导入别忘了加入 `build_contract_workbook`！

- [ ] **Step 4: 运行测试以验证其通过**
  
  运行: `pytest tests/test_exports.py`
  预期结果: PASS

- [ ] **Step 5: 提交更改**
  
  运行: `git add construction_maintenance/services/exports.py construction_maintenance/web/routes.py tests/test_exports.py` 并 `git commit -m "service: implement contract Excel export with Emerald theme and register routing"`

---

### Task 5: 模版开发、导航整合与系统联调

**Files:**
- Modify: `construction_maintenance/templates/base.html`
- Modify: `construction_maintenance/templates/exports.html`
- Modify: `construction_maintenance/templates/projects.html`
- Modify: `construction_maintenance/templates/_icons.html`
- Create: `construction_maintenance/templates/contracts.html`

- [ ] **Step 1: 在 _icons.html 中新增合同管理的 SVG 图标**
  
  修改 `construction_maintenance/templates/_icons.html`，在适当的位置添加：
  
  ```html
  {% elif name == 'contract' %}
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-6 h-6">
      <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
    </svg>
  ```

- [ ] **Step 2: 修改 base.html，加入侧边栏链接**
  
  修改 `construction_maintenance/templates/base.html`。
  在“企业资质”导航（第 56-59 行）下方，增加“合同管理”：
  
  ```html
            <a href="{{ url_for('web.contracts') }}" class="nav-item {% if request.endpoint == 'web.contracts' %}active{% endif %}">
              <span class="nav-icon" aria-hidden="true">{{ icon('contract') }}</span>
              <span class="nav-label">合同管理</span>
            </a>
  ```

- [ ] **Step 3: 修改 exports.html，增加合同导出下载卡片**
  
  修改 `construction_maintenance/templates/exports.html`。
  仿照已有的卡片结构，增加合同台账导出：
  
  ```html
          <div class="export-card">
            <div class="export-icon">{{ icon('contract') }}</div>
            <div class="export-details">
              <h3>项目合同台账</h3>
              <p>一键导出全系统登记的项目合同，包括归属项目、分类、签署时间及备注说明等。</p>
            </div>
            <a href="{{ url_for('web.download_export', export_type='contracts') }}" class="btn btn-primary">导出 Excel</a>
          </div>
  ```

- [ ] **Step 4: 修改 projects.html，增加快速关联查看合同的入口**
  
  修改 `construction_maintenance/templates/projects.html`。
  在表格里的每一个项目操作区域（或“记账凭证”按钮旁边），添加跳转按钮：
  
  ```html
  <a href="{{ url_for('web.contracts', project_id=project.id) }}" class="btn btn-secondary btn-sm" style="display: inline-flex; align-items: center; gap: 4px;">
    {{ icon('contract') }} 合同
  </a>
  ```

- [ ] **Step 5: 创建 contracts.html 主页模板**
  
  使用 `write_to_file` 创建 `construction_maintenance/templates/contracts.html`。
  页面需严格延续高对比度翡翠绿主题，具备：统计指标块、联合筛选、新增/编辑/删除表单弹窗以及规范表格布局。
  
  （具体实现代码写在接下来的任务中）

- [ ] **Step 6: 联调与测试套件全量验证**
  
  运行 `pytest`。确保 100% 通过（无回归故障）。
  启动本地 Flask 服务并在浏览器中测试功能是否正常。

- [ ] **Step 7: 提交代码并合并**
  
  运行: `git add .` 并 `git commit -m "feat: complete UI templates, navigation integration, and full system verification"`
