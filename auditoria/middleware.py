"""
Thread-local storage para capturar o usuário atual da request dentro dos signals.
Também expõe funções para definir contexto de integração (tasks Celery).
"""
import threading

_thread_locals = threading.local()


# ── Leitores ──────────────────────────────────────────────────────────────────

def get_current_user():
    """Retorna o usuário Django da request atual, ou None."""
    return getattr(_thread_locals, 'user', None)


def get_current_plataforma():
    """Retorna o código da plataforma de integração ativa ('ML', 'SHOPEE', etc.)."""
    return getattr(_thread_locals, 'plataforma', '')


def get_usuario_nome_override():
    """Retorna um nome de usuário customizado definido pelo contexto de integração."""
    return getattr(_thread_locals, 'usuario_nome_override', '')


# ── Definidores (usados por tasks Celery) ────────────────────────────────────

def set_integration_context(plataforma: str, nome: str = ''):
    """
    Define o contexto de integração para auditoria em tasks Celery.

    Args:
        plataforma: código da plataforma ('ML', 'SHOPEE', 'TIKTOK')
        nome: nome descritivo a usar como usuário (ex: 'MercadoLivre — Minha loja')
    """
    _thread_locals.user = None
    _thread_locals.plataforma = plataforma
    _thread_locals.usuario_nome_override = nome or plataforma


def clear_integration_context():
    """Limpa o contexto de integração após a task."""
    _thread_locals.user = None
    _thread_locals.plataforma = ''
    _thread_locals.usuario_nome_override = ''


# ── Middleware ────────────────────────────────────────────────────────────────

class AuditoriaMiddleware:
    """
    Middleware que injeta o usuário autenticado no thread-local para uso
    pelos signal handlers de auditoria.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _thread_locals.user = getattr(request, 'user', None)
        _thread_locals.plataforma = ''
        _thread_locals.usuario_nome_override = ''
        response = self.get_response(request)
        return response
