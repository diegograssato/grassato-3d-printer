#!/bin/sh
set -e

# Garante que /app/media existe e é gravável pelo processo atual
# (o volume Docker pode ser montado como root na primeira execução)
mkdir -p /app/media

# Migrações e superusuário apenas no processo principal (app), não no worker
if [ "$1" != "celery" ]; then
    echo "==> Collecting static files..."
    python manage.py collectstatic --noinput

    echo "==> Applying database migrations..."
    python manage.py migrate --noinput

    echo "==> Creating superuser (if not exists)..."
    python manage.py shell -c "
from django.contrib.auth import get_user_model
import os
User = get_user_model()
username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
email    = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@grassato.local')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'admin123')
if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username, email, password)
    print(f'Superuser \"{username}\" created.')
else:
    print(f'Superuser \"{username}\" already exists — skipping.')
"
fi

# Se argumentos foram passados (ex: celery -A config worker ...), executa-os
if [ $# -gt 0 ]; then
    echo "==> Executing: $*"
    exec "$@"
fi

echo "==> Starting Gunicorn..."

exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:"${GUNICORN_PORT:-8000}" \
    --workers "${GUNICORN_WORKERS:-4}" \
    --worker-class gthread \
    --threads "${GUNICORN_THREADS:-2}" \
    --worker-tmp-dir /dev/shm \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    --timeout 120 \
    --graceful-timeout 30 \
    --keep-alive 5 \
    --access-logfile - \
    --error-logfile - \
    --log-level info  
