import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('grassato3d')

# Lê configurações com prefixo CELERY_ do settings.py do Django
app.config_from_object('django.conf:settings', namespace='CELERY')

# Descobre tasks automaticamente nos INSTALLED_APPS
app.autodiscover_tasks()
