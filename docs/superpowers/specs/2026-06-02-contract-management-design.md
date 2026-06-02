# 合同管理模块设计规格书 (Contract Management Specification)

本文档旨在为建筑工程维护系统 (CAM) 增加“合同管理”功能，负责整理和归档所有项目的合同，例如跟总包、劳务队、材料商、施工人员签署的各类合同，支持上传附件、模糊搜索、多条件筛选以及一键导出 Excel。

---

## 1. 数据库设计 (Database Schema)

在 `construction_maintenance/db.py` 中新增 `contracts` 表：

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

### 字段说明：
* `project_id`: 关联的工程项目 ID（外键关联 `projects.id`）。
* `name`: 合同名称（如 `郑州地铁6号线机电工程总包合同`）。
* `contract_type`: 合同分类，枚举值包括：
  * `总包合同`
  * `劳务合同`
  * `材料商合同`
  * `人员合同`
  * `其它`
* `attachment_path`: 附件的文件名，上传后存放在 `uploads/` 目录下。
* `notes`: 备注信息。

---

## 2. 仓储层设计 (Repository Layer)

在 `construction_maintenance/repositories.py` 中增加对合同的 CRUD 操作：

* `list_contracts(project_id: int | None = None, contract_type: str | None = None, query: str | None = None) -> list[sqlite3.Row]`:
  支持按项目 ID、合同类型、名称/备注模糊检索，按创建时间倒序排列。
* `create_contract(data: dict[str, Any]) -> int`:
  创建新合同，并返回其 ID。
* `update_contract(contract_id: int, data: dict[str, Any]) -> None`:
  更新合同的名称、类型、项目、备注等信息（如提供新附件则更新附件路径）。
* `delete_contract(contract_id: int) -> None`:
  删除合同记录。
* `get_contract(contract_id: int) -> sqlite3.Row | None`:
  获取单条合同记录。

---

## 3. 控制器与路由设计 (Web & Controller Layer)

在 `construction_maintenance/web/routes.py` 中新增以下路由：

* `GET /contracts`:
  展示合同管理主页面。查询所有的项目列表（用于下拉筛选及表单新增），并根据 URL 查询参数 `project_id`、`contract_type`、`query` 过滤合同列表。
* `POST /contracts`:
  处理合同新增表单。接收并验证 `name`、`project_id`、`contract_type`、`notes` 字段，若有 `attachment` 文件则调用 `_save_form_upload` 保存，最后创建记录并重定向。
* `POST /contracts/<int:contract_id>/edit`:
  编辑并保存合同。
* `POST /contracts/<int:contract_id>/delete`:
  删除合同。
* `GET /exports/contracts`:
  调用导出服务，生成并下载包含合同台账的 Excel 报表。
* `GET /uploads/<path:filename>`:
  针对合同附件的下载与预览。若附件文件在物理上缺失，则根据合同详情动态生成精美的 SVG 模拟合同证书，以便演示。

---

## 4. 业务服务层设计 (Services Layer)

### 4.1 Excel 导出设计 (`construction_maintenance/services/exports.py`)
新增 `build_contract_workbook(output_path: Path) -> Path`：
* 从数据库中提取所有合同数据，关联项目名称。
* 使用 `openpyxl` 库生成 Excel 报表。
* 样式应符合系统的 **“深邃翠绿主题（Premium Emerald Theme）”**：
  * 表头使用深绿背景色（如 `#0f766e`），白色粗体字。
  * 斑马纹交替行背景。
  * 自动调整列宽，边框清晰。

---

## 5. 前端界面设计 (UI/UX Templates)

### 5.1 侧边栏导航更新 (`templates/base.html`)
在主导航菜单中增加“合同管理”入口，并使用契合的 SVG 图标：
```html
<a href="{{ url_for('web.contracts') }}" class="nav-item {% if request.endpoint == 'web.contracts' %}active{% endif %}">
  <span class="nav-icon" aria-hidden="true">{{ icon('contract') }}</span>
  <span class="nav-label">合同管理</span>
</a>
```
并在 `templates/_icons.html` 中新增 `'contract'` 图标定义。

### 5.2 合同管理主页 (`templates/contracts.html`)
采用与系统风格高度一致的 Premium 响应式页面结构：
1. **统计卡片区**：
   * 合同总数
   * 总包合同数量
   * 劳务合同数量
   * 材料/人员/其它合同数量
2. **筛选操作区**：
   * 输入框：按合同名称模糊查询。
   * 下拉选择框：按归属项目筛选。
   * 下拉选择框：按合同类型筛选。
   * 按钮：新增合同（触发弹窗模态框）。
3. **合同列表表格**：
   * 包含：合同名称、合同类型、归属项目、合同附件（带图标下载/预览链接）、备注、操作按钮（编辑/删除）。
   * 表格应用翡翠绿主题。
4. **新增/编辑模态框**：
   * 包含：合同名称（必填）、归属项目（必选）、合同类型（必选）、附件上传（可选）、备注（可选）。

### 5.3 导出中心更新 (`templates/exports.html`)
在导出中心中增加“合同台账 Excel”下载卡片，展示翡翠绿导出的入口。

---

## 6. 测试方案 (Testing Plan)

在 `tests/` 下添加或补充单元测试：
* 验证 `db.py` 中 `contracts` 表能够正确初始化，并插入种子数据。
* 单元测试仓储层：测试 `create_contract`、`list_contracts`、`update_contract` 和 `delete_contract` 的正确性。
* 单元测试导出功能：运行 `build_contract_workbook` 检查 Excel 是否正常生成及样式规范。
* 单元测试 Web 路由：测试 `GET /contracts` 加载、表单提交新增、删除以及附件下载。
