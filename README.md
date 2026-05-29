# 建筑工程维护系统

一个独立的轻量 Web 系统，用于建筑工程公司的项目凭证台账、人员基础信息、企业资质和 Excel 导出。

## 本地运行

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
flask --app construction_maintenance run --debug
```

打开 `http://127.0.0.1:5000`。

## 当前进度

当前开发分支：`codex/implementation`

已完成并通过实现审查：

- Task 1：Flask 独立项目骨架、首页看板基础页、基础样式和首个路由测试。
- Task 2：SQLite 数据库连接、核心表结构、主公司种子数据。
- Task 3：公司、项目、凭证仓储层和表单基础校验。
- Task 4：项目台账页面、凭证录入页面、基础表单错误处理和本月看板统计。

已实现并通过测试，等待继续复审：

- Task 5：人员基础档案、人员花名册页面、基础人员信息表 Excel 导出。
- Task 5 已修复重复身份证号、负年龄、导出字段映射等审查问题。

尚未开始：

- Task 6：企业资质管理页面和资质清单导出。
- Task 7：批量上传/待确认队列。
- Task 8：完整看板指标和导出中心下载入口。
- Task 9：最终 README、人工网页验证和收尾检查。

## 已有页面

- `/`：看板
- `/projects`：项目台账
- `/vouchers`：凭证录入
- `/people`：人员花名册

## 当前测试

```powershell
pytest -q
```

当前进度下最近一次完整测试结果：`24 passed`。

## 设计文档

- `docs/superpowers/specs/2026-05-29-construction-maintenance-system-design.md`
- `docs/superpowers/plans/2026-05-29-construction-maintenance-system.md`
