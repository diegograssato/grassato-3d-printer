from pathlib import Path
from decouple import config
from django.contrib.messages import constants as msg_constants

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY', default='django-insecure-grassato-3d-dev-key')
DEBUG = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = config(
    'ALLOWED_HOSTS',
    default='localhost,127.0.0.1',
    cast=lambda v: [s.strip() for s in v.split(',')]
)
CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS',
    default='http://localhost:8000,http://127.0.0.1:8000',
    cast=lambda v: [s.strip() for s in v.split(',')]
)

# Necessário quando Django está atrás de um proxy reverso (nginx)
USE_X_FORWARDED_HOST = config('USE_X_FORWARDED_HOST', default=False, cast=bool)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Local apps
    'estoque.apps.EstoqueConfig',
    'vendas.apps.VendasConfig',
    'caixa.apps.CaixaConfig',
    'dashboard.apps.DashboardConfig',
    'integracoes.apps.IntegracoesConfig',
    'importexport.apps.ImportExportConfig',
    'auditoria.apps.AuditoriaConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'auditoria.middleware.AuditoriaMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'auditoria.context_processors.admin_group',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

_db_engine = config('DB_ENGINE', default='sqlite3')
if _db_engine == 'mysql':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': config('DB_NAME', default='grassato3d'),
            'USER': config('DB_USER', default='grassato'),
            'PASSWORD': config('DB_PASSWORD', default=''),
            'HOST': config('DB_HOST', default='127.0.0.1'),
            'PORT': config('DB_PORT', default='3306'),
            'OPTIONS': {
                'charset': 'utf8mb4',
                'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            },
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': config('DB_NAME', default=str(BASE_DIR / 'db.sqlite3')),
        }
    }

_redis_url = config('REDIS_URL', default='')
if _redis_url:
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': _redis_url,
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                'IGNORE_EXCEPTIONS': True,
            },
            'KEY_PREFIX': 'grassato3d',
        }
    }
    SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
    SESSION_CACHE_ALIAS = 'default'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# URL base pública usada para gerar links absolutos das imagens (ex.: para o ML)
# Em dev usa a URL do ngrok; em prod usa o domínio real.
SITE_URL = config('SITE_URL', default='http://localhost:8000').rstrip('/')
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── Autenticação ─────────────────────────────────────────────────────────────
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

MESSAGE_TAGS = {
    msg_constants.DEBUG: 'secondary',
    msg_constants.INFO: 'info',
    msg_constants.SUCCESS: 'success',
    msg_constants.WARNING: 'warning',
    msg_constants.ERROR: 'danger',
}

# ── Celery ────────────────────────────────────────────────────────────────────
_celery_broker = config('CELERY_BROKER_URL', default='redis://localhost:6379/1')
_celery_backend = config('CELERY_RESULT_BACKEND', default='redis://localhost:6379/1')

CELERY_BROKER_URL = _celery_broker
CELERY_RESULT_BACKEND = _celery_backend
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 300        # 5 min — hard limit por task
CELERY_TASK_SOFT_TIME_LIMIT = 240   # 4 min — raise SoftTimeLimitExceeded antes do hard limit
CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # evita starvation de filas lentas

# Em DEBUG=True (dev local) executa tasks inline sem broker/Redis
if DEBUG:
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True   # exceções das tasks sobem normalmente
    CELERY_RESULT_BACKEND = 'cache+memory://'  # sem Redis em dev

# Roteamento de filas por domínio
CELERY_TASK_ROUTES = {
    'integracoes.tasks.processar_oauth_ml': {'queue': 'ml_oauth'},
    'integracoes.tasks.processar_pedido_ml': {'queue': 'ml_orders'},
    'integracoes.tasks.processar_status_ml': {'queue': 'ml_status'},
}

CELERY_TASK_DEFAULT_QUEUE = 'default'
