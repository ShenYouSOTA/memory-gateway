# ---- Builder stage: install dependencies with uv ----
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_NO_DEV=1
ENV UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# 先复制依赖文件，利用 Docker 缓存
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project

# 复制源码并安装项目本身
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

# ---- Runtime stage: slim image without uv ----
FROM python:3.12-slim-bookworm

# 非 root 用户
RUN groupadd --system --gid 999 nonroot \
 && useradd --system --gid 999 --uid 999 --create-home nonroot

# 从 builder 复制应用和虚拟环境
COPY --from=builder --chown=nonroot:nonroot /app /app

# 让 venv 中的可执行文件优先于系统 Python
ENV PATH="/app/.venv/bin:$PATH"

USER nonroot
WORKDIR /app

# Render 等平台通过 PORT 环境变量分配端口
ENV PORT=8000

CMD ["python", "main.py"]
