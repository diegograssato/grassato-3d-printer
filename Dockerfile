# syntax=docker/dockerfile:1

# ── Stage 1: build Python deps ─────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# gcc + libmysqlclient-dev ficam APENAS no builder (não vão para a imagem final)
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
      default-libmysqlclient-dev \
      pkg-config \
      gcc

# Cache de pip persiste entre builds; poetry instalado uma vez
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install poetry==1.8.3

COPY pyproject.toml poetry.lock* ./
RUN poetry export -f requirements.txt --output requirements.txt --without-hashes --without dev

# Cria venv isolado e instala todas as dependências dentro dele
RUN python -m venv /venv
RUN --mount=type=cache,target=/root/.cache/pip \
    /venv/bin/pip install -r requirements.txt


# ── Stage 2: runtime ───────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings \
    PATH="/venv/bin:$PATH" \
    VIRTUAL_ENV=/venv

WORKDIR /app

# Apenas a lib de runtime (libmariadb3); sem gcc nem compilador
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
      libmariadb3

# Venv pré-compilado vindo do builder — sem recompilação necessária
COPY --from=builder /venv /venv

# Código-fonte por último — invalidar cache só quando o código mudar
COPY . .
RUN chmod +x /app/entrypoint.sh

RUN python manage.py collectstatic --noinput

# Usuário sem privilégios + diretórios graváveis
RUN addgroup --system appgroup && \
    adduser --system --ingroup appgroup appuser && \
    mkdir -p /app/data /app/media && \
    chown -R appuser:appgroup /app/data /app/media /venv
USER appuser

# SQLite default path (sobrescrito por DB_NAME em prod com MySQL)
ENV DB_NAME=/app/data/db.sqlite3

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
