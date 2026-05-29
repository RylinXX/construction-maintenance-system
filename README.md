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
