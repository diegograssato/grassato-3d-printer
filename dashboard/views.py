from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from decimal import Decimal
from datetime import date
import json


def _meses_anteriores(n=6):
    """Retorna lista com o primeiro dia dos últimos n meses."""
    hoje = date.today()
    result = []
    year, month = hoje.year, hoje.month
    for _ in range(n):
        result.insert(0, date(year, month, 1))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return result


def _proximo_mes(d):
    if d.month == 12:
        return d.replace(year=d.year + 1, month=1)
    return d.replace(month=d.month + 1)


def dashboard(request):
    from caixa.models import MovimentacaoCaixa
    from vendas.models import Venda
    from estoque.models import Produto, Filamento

    hoje = date.today()
    primeiro_dia_mes = hoje.replace(day=1)

    # Financeiro do mês
    receita_mes = MovimentacaoCaixa.objects.filter(
        tipo='ENTRADA', data__gte=primeiro_dia_mes
    ).aggregate(t=Sum('valor'))['t'] or Decimal('0')

    despesas_mes = MovimentacaoCaixa.objects.filter(
        tipo='SAIDA', data__gte=primeiro_dia_mes
    ).aggregate(t=Sum('valor'))['t'] or Decimal('0')

    lucro_mes = receita_mes - despesas_mes

    # Saldo total acumulado
    total_entradas = MovimentacaoCaixa.objects.filter(tipo='ENTRADA').aggregate(t=Sum('valor'))['t'] or Decimal('0')
    total_saidas = MovimentacaoCaixa.objects.filter(tipo='SAIDA').aggregate(t=Sum('valor'))['t'] or Decimal('0')
    saldo_caixa = total_entradas - total_saidas

    # Alertas de estoque baixo
    produtos_criticos = Produto.objects.filter(estoque_quantidade__lte=2, ativo=True).select_related('filamento')
    filamentos_criticos = [f for f in Filamento.objects.all() if float(f.percentual_disponivel) <= 30]

    # Vendas recentes
    vendas_recentes = Venda.objects.select_related('produto').order_by('-data', '-criado_em')[:8]

    # Dados para gráfico: últimos 6 meses
    meses = _meses_anteriores(6)
    labels = []
    receitas_chart = []
    despesas_chart = []

    MESES_PT = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
    for m in meses:
        prox = _proximo_mes(m)
        labels.append(f'{MESES_PT[m.month - 1]}/{str(m.year)[2:]}')
        r = MovimentacaoCaixa.objects.filter(
            tipo='ENTRADA', data__gte=m, data__lt=prox
        ).aggregate(t=Sum('valor'))['t'] or Decimal('0')
        d = MovimentacaoCaixa.objects.filter(
            tipo='SAIDA', data__gte=m, data__lt=prox
        ).aggregate(t=Sum('valor'))['t'] or Decimal('0')
        receitas_chart.append(float(r))
        despesas_chart.append(float(d))

    context = {
        'receita_mes': receita_mes,
        'despesas_mes': despesas_mes,
        'lucro_mes': lucro_mes,
        'saldo_caixa': saldo_caixa,
        'produtos_criticos': produtos_criticos,
        'filamentos_criticos': filamentos_criticos,
        'vendas_recentes': vendas_recentes,
        'chart_labels': json.dumps(labels),
        'chart_receitas': json.dumps(receitas_chart),
        'chart_despesas': json.dumps(despesas_chart),
    }
    return render(request, 'dashboard/dashboard.html', context)


@login_required
def balancete(request):
    from caixa.models import MovimentacaoCaixa
    from vendas.models import Venda

    meses = _meses_anteriores(12)
    MESES_PT = [
        'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
        'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
    ]

    resumo = []
    saldo_acumulado = Decimal('0')

    for m in meses:
        prox = _proximo_mes(m)

        entradas = MovimentacaoCaixa.objects.filter(
            tipo='ENTRADA', data__gte=m, data__lt=prox
        ).aggregate(t=Sum('valor'))['t'] or Decimal('0')

        saidas = MovimentacaoCaixa.objects.filter(
            tipo='SAIDA', data__gte=m, data__lt=prox
        ).aggregate(t=Sum('valor'))['t'] or Decimal('0')

        lucro = entradas - saidas
        saldo_acumulado += lucro

        qtd_vendas = Venda.objects.filter(data__gte=m, data__lt=prox).count()
        total_vendas = Venda.objects.filter(
            data__gte=m, data__lt=prox
        ).aggregate(t=Sum('total'))['t'] or Decimal('0')

        resumo.append({
            'mes': m,
            'mes_label': f'{MESES_PT[m.month - 1]}/{m.year}',
            'entradas': entradas,
            'saidas': saidas,
            'lucro': lucro,
            'saldo_acumulado': saldo_acumulado,
            'qtd_vendas': qtd_vendas,
            'total_vendas': total_vendas,
        })

    context = {'resumo': resumo}
    return render(request, 'dashboard/balancete.html', context)
