#!/bin/sh
set -e

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

echo "==> Starting Gunicorn..."
exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-2}" \
  --threads "${GUNICORN_THREADS:-4}" \
  --timeout 60 \
  --access-logfile - \
  --error-logfile -
