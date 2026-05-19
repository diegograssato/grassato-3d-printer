"""
Conecta sinais de pre_save / post_save / post_delete a todos os modelos
auditáveis para registrar automaticamente eventos de CRUD no AuditLog.
"""
import logging
from decimal import Decimal

from django.apps import apps
from django.db.models.signals import post_delete, post_save, pre_save

logger = logging.getLogger(__name__)

# ── Modelos auditados ─────────────────────────────────────────────────────────
AUDITED_MODELS = [
    'estoque.Fornecedor',
    'estoque.Filamento',
    'estoque.Produto',
    'vendas.Venda',
    'caixa.MovimentacaoCaixa',
    'integracoes.Integracao',
    'integracoes.ProdutoIntegracao',
]

# ── Campos ignorados (timestamps automáticos, gerados pelo sistema) ───────────
IGNORED_FIELDS = frozenset({
    'criado_em', 'atualizado_em', 'sku',
})

# ── Campos sensíveis (mascarados no log) ──────────────────────────────────────
SENSITIVE_FIELDS = frozenset({
    'client_secret', 'access_token', 'refresh_token',
})


# ── Utilitários ───────────────────────────────────────────────────────────────

def _serialize_value(value):
    """Converte qualquer valor para tipo JSON-serializável."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, 'pk'):  # FK instance
        return str(value.pk)
    return str(value)


def _get_model_label(model_class):
    meta = model_class._meta
    return f'{meta.app_label}.{meta.object_name}'


def _get_field_snapshot(instance):
    """Retorna {field_name: serialized_value} para todos os campos auditáveis."""
    result = {}
    for field in instance._meta.concrete_fields:
        name = field.name
        if name in IGNORED_FIELDS:
            continue
        if name in SENSITIVE_FIELDS:
            result[name] = '***'
            continue
        try:
            result[name] = _serialize_value(getattr(instance, field.attname))
        except Exception:
            pass
    return result


def _write_log(acao, instance, changes=None, event_json=None):
    """Grava um AuditLog. Importação lazy para evitar import circular."""
    from auditoria.middleware import (
        get_current_plataforma,
        get_current_user,
        get_usuario_nome_override,
    )
    from auditoria.models import AuditLog

    user = get_current_user()
    plataforma = get_current_plataforma()
    nome_override = get_usuario_nome_override()

    if nome_override:
        usuario_nome = nome_override
    elif user and getattr(user, 'is_authenticated', False):
        usuario_nome = user.get_full_name() or user.username
    elif plataforma:
        labels = {'ML': 'MercadoLivre', 'SHOPEE': 'Shopee', 'TIKTOK': 'TikTok Shop'}
        usuario_nome = labels.get(plataforma, plataforma)
    else:
        usuario_nome = 'sistema'

    db_user = user if (user and getattr(user, 'is_authenticated', False)) else None

    try:
        AuditLog.objects.create(
            acao=acao,
            modelo=_get_model_label(type(instance)),
            objeto_id=str(getattr(instance, 'pk', '') or ''),
            objeto_repr=str(instance)[:500],
            usuario_nome=usuario_nome,
            usuario=db_user,
            plataforma=plataforma,
            changes=changes or {},
            event_json=event_json,
        )
    except Exception as exc:
        logger.warning('AuditLog write failed [%s %s]: %s', acao, type(instance).__name__, exc)


# ── Handlers dos sinais ───────────────────────────────────────────────────────

def _pre_save_handler(sender, instance, **kwargs):
    """Captura snapshot dos valores antigos antes do save."""
    if instance.pk:
        try:
            old = sender.objects.get(pk=instance.pk)
            instance._audit_old_snapshot = _get_field_snapshot(old)
        except sender.DoesNotExist:
            instance._audit_old_snapshot = None
    else:
        instance._audit_old_snapshot = None


def _post_save_handler(sender, instance, created, **kwargs):
    """Registra CRIADO ou ATUALIZADO após save."""
    if created:
        _write_log(
            'CRIADO',
            instance,
            changes={'new': _get_field_snapshot(instance)},
        )
    else:
        old = getattr(instance, '_audit_old_snapshot', {}) or {}
        new = _get_field_snapshot(instance)
        diff = {
            field: {'old': old.get(field), 'new': new[field]}
            for field in new
            if new[field] != old.get(field)
        }
        if diff:
            _write_log('ATUALIZADO', instance, changes=diff)


def _post_delete_handler(sender, instance, **kwargs):
    """Registra EXCLUIDO após delete."""
    _write_log(
        'EXCLUIDO',
        instance,
        changes={'snapshot': _get_field_snapshot(instance)},
    )


# ── Registro ──────────────────────────────────────────────────────────────────

def connect_audit_signals():
    """Conecta os sinais de auditoria. Chamado em AuditoriaConfig.ready()."""
    for model_path in AUDITED_MODELS:
        try:
            app_label, model_name = model_path.split('.')
            model = apps.get_model(app_label, model_name)
            pre_save.connect(_pre_save_handler, sender=model, weak=False,
                             dispatch_uid=f'audit_pre_save_{model_path}')
            post_save.connect(_post_save_handler, sender=model, weak=False,
                              dispatch_uid=f'audit_post_save_{model_path}')
            post_delete.connect(_post_delete_handler, sender=model, weak=False,
                                dispatch_uid=f'audit_post_delete_{model_path}')
            logger.debug('Audit signals connected for %s', model_path)
        except Exception as exc:
            logger.warning('Failed to connect audit signals for %s: %s', model_path, exc)
