import json

from django.core.paginator import Paginator
from django.shortcuts import render

from .decorators import admin_group_required
from .models import AuditLog

PAGE_SIZES = [10, 20, 50, 100, 500, 1000]
DEFAULT_PAGE_SIZE = 50


def _page_size(request):
    try:
        s = int(request.GET.get('per_page', DEFAULT_PAGE_SIZE))
        return s if s in PAGE_SIZES else DEFAULT_PAGE_SIZE
    except (ValueError, TypeError):
        return DEFAULT_PAGE_SIZE


def _qp(request, *drop):
    p = request.GET.copy()
    p.pop('page', None)
    for k in drop:
        p.pop(k, None)
    return p.urlencode()


@admin_group_required
def log_list(request):
    qs = AuditLog.objects.select_related('usuario').order_by('-timestamp')

    modelo_filter = request.GET.get('modelo', '').strip()
    acao_filter = request.GET.get('acao', '').strip()
    usuario_filter = request.GET.get('usuario', '').strip()
    plataforma_filter = request.GET.get('plataforma', '').strip()

    if modelo_filter:
        qs = qs.filter(modelo=modelo_filter)
    if acao_filter:
        qs = qs.filter(acao=acao_filter)
    if usuario_filter:
        qs = qs.filter(usuario_nome__icontains=usuario_filter)
    if plataforma_filter:
        qs = qs.filter(plataforma=plataforma_filter)

    per_page = _page_size(request)
    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    modelos = (
        AuditLog.objects.values_list('modelo', flat=True)
        .distinct()
        .order_by('modelo')
    )

    return render(request, 'auditoria/log_list.html', {
        'logs': page_obj,
        'page_obj': page_obj,
        'modelos': modelos,
        'acoes': AuditLog.ACAO_CHOICES,
        'plataformas': AuditLog.PLATAFORMA_CHOICES,
        'modelo_filter': modelo_filter,
        'acao_filter': acao_filter,
        'usuario_filter': usuario_filter,
        'plataforma_filter': plataforma_filter,
        'per_page': per_page,
        'page_sizes': PAGE_SIZES,
        'query_params': _qp(request),
        'query_params_base': _qp(request, 'per_page'),
    })


@admin_group_required
def log_detail(request, pk):
    """Retorna o JSON completo de um log para exibição em modal."""
    from django.http import JsonResponse
    log = AuditLog.objects.get(pk=pk)
    return JsonResponse({
        'id': log.pk,
        'timestamp': log.timestamp.strftime('%d/%m/%Y %H:%M:%S'),
        'acao': log.get_acao_display(),
        'modelo': log.modelo,
        'objeto_id': log.objeto_id,
        'objeto_repr': log.objeto_repr,
        'usuario_nome': log.usuario_nome,
        'plataforma': log.plataforma_label,
        'changes': log.changes,
        'event_json': log.event_json,
    })
