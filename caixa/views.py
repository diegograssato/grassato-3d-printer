from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Sum
from decimal import Decimal
from .models import MovimentacaoCaixa
from .forms import MovimentacaoCaixaForm

PAGE_SIZES = [10, 20, 50, 100, 500, 1000]
DEFAULT_PAGE_SIZE = 20


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


@login_required
def caixa_list(request):
    from estoque.models import Fornecedor

    qs = MovimentacaoCaixa.objects.select_related('fornecedor').order_by('-data', '-criado_em')

    mes_str = request.GET.get('mes', '').strip()
    tipo_filtro = request.GET.get('tipo', '').strip()
    categoria_f = request.GET.get('categoria', '').strip()
    fornecedor_f = request.GET.get('fornecedor', '').strip()

    if mes_str:
        try:
            ano, mes = mes_str.split('-')
            qs = qs.filter(data__year=int(ano), data__month=int(mes))
        except (ValueError, AttributeError):
            mes_str = ''
    if tipo_filtro in ('ENTRADA', 'SAIDA'):
        qs = qs.filter(tipo=tipo_filtro)
    if categoria_f:
        qs = qs.filter(categoria=categoria_f)
    if fornecedor_f:
        qs = qs.filter(fornecedor_id=fornecedor_f)

    total_entradas = qs.filter(tipo='ENTRADA').aggregate(t=Sum('valor'))['t'] or Decimal('0')
    total_saidas = qs.filter(tipo='SAIDA').aggregate(t=Sum('valor'))['t'] or Decimal('0')
    saldo = total_entradas - total_saidas

    total_entradas_geral = MovimentacaoCaixa.objects.filter(tipo='ENTRADA').aggregate(t=Sum('valor'))['t'] or Decimal('0')
    total_saidas_geral = MovimentacaoCaixa.objects.filter(tipo='SAIDA').aggregate(t=Sum('valor'))['t'] or Decimal('0')
    saldo_geral = total_entradas_geral - total_saidas_geral

    per_page = _page_size(request)
    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'caixa/caixa_list.html', {
        'page_obj': page_obj,
        'movimentacoes': page_obj,
        'total_entradas': total_entradas,
        'total_saidas': total_saidas,
        'saldo': saldo,
        'saldo_geral': saldo_geral,
        'mes_filtro': mes_str,
        'tipo_filtro': tipo_filtro,
        'categoria_f': categoria_f,
        'fornecedor_f': fornecedor_f,
        'categorias_opts': MovimentacaoCaixa.CATEGORIA,
        'fornecedores_opts': Fornecedor.objects.order_by('nome'),
        'per_page': per_page,
        'page_sizes': PAGE_SIZES,
        'query_params': _qp(request),
        'query_params_base': _qp(request, 'per_page'),
    })


@login_required
def movimentacao_create(request):
    form = MovimentacaoCaixaForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, 'Movimentação registrada com sucesso!')
        return redirect('caixa:caixa_list')
    return render(request, 'caixa/movimentacao_form.html', {'form': form})


def _is_admin(request):
    return (
        request.user.is_superuser
        or request.user.groups.filter(name='Administradores').exists()
    )


@login_required
def movimentacao_delete(request, pk):
    is_admin = _is_admin(request)
    # Administradores podem excluir qualquer movimentação, inclusive as geradas por vendas
    if is_admin:
        mov = get_object_or_404(MovimentacaoCaixa, pk=pk)
    else:
        mov = get_object_or_404(MovimentacaoCaixa, pk=pk, venda__isnull=True)
    if request.method == 'POST':
        if mov.venda:
            # Exclui a venda; CASCADE remove esta movimentação automaticamente
            mov.venda.delete()
            messages.success(request, 'Venda e movimentação de caixa excluídas com sucesso.')
        else:
            mov.delete()
            messages.success(request, 'Movimentação excluída com sucesso!')
        return redirect('caixa:caixa_list')
    return render(request, 'caixa/movimentacao_confirm_delete.html', {
        'objeto': mov,
        'venda_vinculada': mov.venda,
    })
