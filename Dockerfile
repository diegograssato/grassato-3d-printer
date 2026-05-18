# ── Stage 1: export requirements via Poetry ────────────────────────────────
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1
WORKDIR /build

RUN pip install poetry==1.8.3

COPY pyproject.toml poetry.lock* ./
# Exporta sem deps de dev e sem hashes para pip install posterior
RUN poetry export -f requirements.txt --output requirements.txt --without-hashes --without dev


# ── Stage 2: runtime ───────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings

WORKDIR /app

# Dependências de sistema para mysqlclient
# gcc/pkg-config são necessários para compilar o cliente; libmariadb3 fica no runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
      default-libmysqlclient-dev \
      libmariadb3 \
      pkg-config \
      gcc \
    && rm -rf /var/lib/apt/lists/*

# Instala dependências Python
COPY --from=builder /build/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código-fonte
COPY . .

# Coleta arquivos estáticos
RUN python manage.py collectstatic --noinput

# Entrypoint script (migrate + gunicorn)
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Usuário sem privilégios + diretório gravável para SQLite (dev/CI)
RUN addgroup --system appgroup && \
    adduser --system --ingroup appgroup appuser && \
    mkdir -p /app/data && \ 
    chown -R appuser:appgroup /app/data
USER appuser

# SQLite default path (sobrescrito por DB_NAME em prod com MySQL)
ENV DB_NAME=/app/data/db.sqlite3

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
