from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Sum
from decimal import Decimal
from .models import Venda
from .forms import VendaForm


def venda_list(request):
    vendas = Venda.objects.select_related('produto').all()

    # Filtro por mês
    mes_str = request.GET.get('mes', '')
    if mes_str:
        try:
            ano, mes = mes_str.split('-')
            vendas = vendas.filter(data__year=int(ano), data__month=int(mes))
        except (ValueError, AttributeError):
            mes_str = ''

    agg = vendas.aggregate(
        total_valor=Sum('total'),
        total_qtd=Sum('quantidade'),
    )
    total_valor = agg['total_valor'] or Decimal('0')
    total_qtd = agg['total_qtd'] or 0

    return render(request, 'vendas/venda_list.html', {
        'vendas': vendas,
        'total_valor': total_valor,
        'total_qtd': total_qtd,
        'mes_filtro': mes_str,
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
