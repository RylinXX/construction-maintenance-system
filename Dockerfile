# ─── Stage 1: 依赖构建层 ────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# 安装构建依赖（pymupdf 需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libmupdf-dev \
    && rm -rf /var/lib/apt/lists/*

# 先复制依赖声明，利用 Docker 层缓存
COPY pyproject.toml ./

# 创建虚拟环境并安装生产依赖（不含 dev/pytest）
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -e "."


# ─── Stage 2: 运行层（精简镜像）───────────────────────────────────────────────
FROM python:3.12-slim AS runtime

LABEL maintainer="YLT Digital" \
      version="0.2.34" \
      description="营力特数字化系统 - 建筑工程运营平台"

# 安装 pymupdf 运行时依赖 + gunicorn
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmupdf-dev \
    && rm -rf /var/lib/apt/lists/*

# 从构建层复制虚拟环境
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 安装 Gunicorn（生产 WSGI 服务器）
RUN pip install --no-cache-dir gunicorn==23.0.0

WORKDIR /app

# 复制应用代码
COPY construction_maintenance/ ./construction_maintenance/
COPY pyproject.toml ./

# 创建运行时需要的持久化目录（将被挂载为 Volume）
RUN mkdir -p /data/instance /data/uploads /data/exports \
    && useradd -r -u 1001 -s /sbin/nologin appuser \
    && chown -R appuser:appuser /app /data

# 切换为非 root 用户运行
USER appuser

# 将数据目录软链接到应用预期路径
# config.py 中：BASE_DIR / "instance"  →  /data/instance
# config.py 中：BASE_DIR / "uploads"   →  /data/uploads
ENV CAM_INSTANCE_DIR=/data/instance \
    CAM_UPLOAD_FOLDER=/data/uploads \
    CAM_EXPORT_FOLDER=/data/exports

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Gunicorn 启动：4 workers，绑定所有接口
CMD ["gunicorn", \
     "--config", "/app/gunicorn.conf.py", \
     "--bind", "0.0.0.0:8000", \
     "construction_maintenance:create_app()"]
