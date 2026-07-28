# Gunicorn 生产配置
# 文档：https://docs.gunicorn.org/en/stable/settings.html

import multiprocessing

# ─── 绑定 ─────────────────────────────────────────────────────────────────────
bind = "0.0.0.0:8000"

# ─── Worker 进程 ───────────────────────────────────────────────────────────────
# 公式：CPU 核心数 × 2 + 1（推荐范围 2–8）
workers = min(multiprocessing.cpu_count() * 2 + 1, 8)
worker_class = "sync"          # Flask/SQLite 同步模型适合 sync worker
threads = 1
worker_connections = 1000
timeout = 120                  # 文件上传处理最多等 120 秒
graceful_timeout = 30
keepalive = 5

# ─── 日志 ──────────────────────────────────────────────────────────────────────
accesslog = "-"                # 输出到 stdout，由 Docker 日志系统收集
errorlog  = "-"                # 输出到 stderr
loglevel  = "info"
access_log_format = '%(h)s "%(r)s" %(s)s %(b)s %(D)sµs'

# ─── 进程管理 ──────────────────────────────────────────────────────────────────
preload_app = True             # 主进程预加载 Flask app，节省内存（写时复制）
max_requests = 1000            # 每个 worker 处理 1000 请求后自动重启（防内存泄漏）
max_requests_jitter = 100      # 抖动，避免所有 worker 同时重启

# ─── 安全 ──────────────────────────────────────────────────────────────────────
limit_request_line = 8190
limit_request_fields = 200
forwarded_allow_ips = "*"      # 信任 Nginx 传来的 X-Forwarded-For
