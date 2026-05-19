# Garante que o app Celery é carregado quando o Django inicia
from .celery import app as celery_app

__all__ = ('celery_app',)
