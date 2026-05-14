from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from decimal import Decimal
from .models import MovimentacaoCaixa
from .forms import MovimentacaoCaixaForm


@login_required
def caixa_list(request):
    movimentacoes = MovimentacaoCaixa.objects.all()

    # Filtro por mês
    mes_str = request.GET.get('mes', '')
    if mes_str:
        try:
            ano, mes = mes_str.split('-')
            movimentacoes = movimentacoes.filter(data__year=int(ano), data__month=int(mes))
        except (ValueError, AttributeError):
            mes_str = ''

    # Filtro por tipo
    tipo_filtro = request.GET.get('tipo', '')
    if tipo_filtro in ('ENTRADA', 'SAIDA'):
        movimentacoes = movimentacoes.filter(tipo=tipo_filtro)

    total_entradas = movimentacoes.filter(tipo='ENTRADA').aggregate(t=Sum('valor'))['t'] or Decimal('0')
    total_saidas = movimentacoes.filter(tipo='SAIDA').aggregate(t=Sum('valor'))['t'] or Decimal('0')
    saldo = total_entradas - total_saidas

    # Saldo geral (all-time)
    total_entradas_geral = MovimentacaoCaixa.objects.filter(tipo='ENTRADA').aggregate(t=Sum('valor'))['t'] or Decimal('0')
    total_saidas_geral = MovimentacaoCaixa.objects.filter(tipo='SAIDA').aggregate(t=Sum('valor'))['t'] or Decimal('0')
    saldo_geral = total_entradas_geral - total_saidas_geral

    return render(request, 'caixa/caixa_list.html', {
        'movimentacoes': movimentacoes,
        'total_entradas': total_entradas,
        'total_saidas': total_saidas,
        'saldo': saldo,
        'saldo_geral': saldo_geral,
        'mes_filtro': mes_str,
        'tipo_filtro': tipo_filtro,
    })


@login_required
def movimentacao_create(request):
    form = MovimentacaoCaixaForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, 'Movimentação registrada com sucesso!')
        return redirect('caixa:caixa_list')
    return render(request, 'caixa/movimentacao_form.html', {'form': form})


@login_required
def movimentacao_delete(request, pk):
    mov = get_object_or_404(MovimentacaoCaixa, pk=pk, venda__isnull=True)
    if request.method == 'POST':
        mov.delete()
        messages.success(request, 'Movimentação excluída com sucesso!')
        return redirect('caixa:caixa_list')
    return render(request, 'caixa/movimentacao_confirm_delete.html', {'objeto': mov})
