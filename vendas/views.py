from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from decimal import Decimal
from .models import Venda
from .forms import VendaForm

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


def venda_list(request):
    qs = Venda.objects.select_related('produto').order_by('-data', '-criado_em')

    mes_str = request.GET.get('mes', '').strip()
    forma_f = request.GET.get('forma_pagamento', '').strip()
    produto_f = request.GET.get('produto', '').strip()

    if mes_str:
        try:
            ano, mes = mes_str.split('-')
            qs = qs.filter(data__year=int(ano), data__month=int(mes))
        except (ValueError, AttributeError):
            mes_str = ''
    if forma_f:
        qs = qs.filter(forma_pagamento=forma_f)
    if produto_f:
        qs = qs.filter(produto__nome__icontains=produto_f)

    agg = qs.aggregate(total_valor=Sum('total'), total_qtd=Sum('quantidade'))
    total_valor = agg['total_valor'] or Decimal('0')
    total_qtd = agg['total_qtd'] or 0

    per_page = _page_size(request)
    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    from .models import Venda as VendaModel
    formas_choices = VendaModel.FORMA_PAGAMENTO

    return render(request, 'vendas/venda_list.html', {
        'page_obj': page_obj,
        'vendas': page_obj,
        'total_valor': total_valor,
        'total_qtd': total_qtd,
        'mes_filtro': mes_str,
        'forma_f': forma_f,
        'produto_f': produto_f,
        'formas_choices': formas_choices,
        'per_page': per_page,
        'page_sizes': PAGE_SIZES,
        'query_params': _qp(request),
        'query_params_base': _qp(request, 'per_page'),
    })


def venda_create(request):
    form = VendaForm(request.POST or None)
    if form.is_valid():
        produto = form.cleaned_data['produto']
        quantidade = form.cleaned_data['quantidade']
        peso_necessario = produto.peso_filamento_g * Decimal(str(quantidade))

        if produto.estoque_quantidade < quantidade:
            messages.error(
                request,
                f'Estoque insuficiente! Disponível: {produto.estoque_quantidade} un.'
            )
        elif produto.filamento.peso_disponivel_g < peso_necessario:
            messages.error(
                request,
                f'Filamento insuficiente! Disponível: {produto.filamento.peso_disponivel_g:.0f}g, '
                f'necessário: {peso_necessario:.0f}g.'
            )
        else:
            form.save()
            messages.success(request, 'Venda registrada! Estoque e caixa atualizados automaticamente.')
            return redirect('vendas:venda_list')

    return render(request, 'vendas/venda_form.html', {'form': form, 'titulo': 'Nova Venda'})


def venda_delete(request, pk):
    venda = get_object_or_404(Venda, pk=pk)
    if request.method == 'POST':
        venda.delete()
        messages.success(request, 'Venda excluída. Estoque revertido.')
        return redirect('vendas:venda_list')
    return render(request, 'vendas/venda_confirm_delete.html', {'objeto': venda})
