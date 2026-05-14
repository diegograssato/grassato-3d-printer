from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import Filamento, Produto
from .forms import FilamentoForm, ProdutoForm


# ==================== Filamentos ====================

@login_required
def filamento_list(request):
    filamentos = Filamento.objects.all()
    return render(request, 'estoque/filamento_list.html', {'filamentos': filamentos})


def filamento_create(request):
    form = FilamentoForm(request.POST or None)
    if form.is_valid():
        filamento = form.save()
        # Lança automaticamente a compra no caixa
        from caixa.models import MovimentacaoCaixa
        from decimal import Decimal
        custo_total = filamento.preco_por_kg * (filamento.peso_total_g / Decimal('1000'))
        MovimentacaoCaixa.objects.create(
            data=filamento.criado_em.date(),
            tipo='SAIDA',
            categoria='FILAMENTO',
            descricao=f'Compra de Filamento: {filamento} ({filamento.peso_total_g}g)',
            valor=custo_total,
        )
        messages.success(request, 'Filamento cadastrado! Lançamento de compra registrado no caixa.')
        return redirect('estoque:filamento_list')
    return render(request, 'estoque/filamento_form.html', {
        'form': form,
        'titulo': 'Novo Filamento',
    })


@login_required
def filamento_update(request, pk):
    filamento = get_object_or_404(Filamento, pk=pk)
    form = FilamentoForm(request.POST or None, instance=filamento)
    if form.is_valid():
        form.save()
        messages.success(request, 'Filamento atualizado com sucesso!')
        return redirect('estoque:filamento_list')
    return render(request, 'estoque/filamento_form.html', {
        'form': form,
        'titulo': 'Editar Filamento',
        'objeto': filamento,
    })


@login_required
def filamento_delete(request, pk):
    filamento = get_object_or_404(Filamento, pk=pk)
    if request.method == 'POST':
        try:
            filamento.delete()
            messages.success(request, 'Filamento excluído com sucesso!')
        except Exception:
            messages.error(request, 'Não é possível excluir: filamento vinculado a produtos.')
        return redirect('estoque:filamento_list')
    return render(request, 'estoque/filamento_confirm_delete.html', {'objeto': filamento})


# ==================== Produtos ====================

@login_required
def produto_list(request):
    produtos = Produto.objects.select_related('filamento').filter(ativo=True)
    inativos = Produto.objects.filter(ativo=False).count()
    return render(request, 'estoque/produto_list.html', {
        'produtos': produtos,
        'inativos': inativos,
    })


@login_required
def produto_create(request):
    form = ProdutoForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, 'Produto cadastrado com sucesso!')
        return redirect('estoque:produto_list')
    return render(request, 'estoque/produto_form.html', {
        'form': form,
        'titulo': 'Novo Produto',
    })


@login_required
def produto_update(request, pk):
    produto = get_object_or_404(Produto, pk=pk)
    form = ProdutoForm(request.POST or None, instance=produto)
    if form.is_valid():
        form.save()
        messages.success(request, 'Produto atualizado com sucesso!')
        return redirect('estoque:produto_list')
    return render(request, 'estoque/produto_form.html', {
        'form': form,
        'titulo': 'Editar Produto',
        'objeto': produto,
    })


@login_required
def produto_delete(request, pk):
    produto = get_object_or_404(Produto, pk=pk)
    if request.method == 'POST':
        produto.ativo = False
        produto.save()
        messages.success(request, 'Produto desativado com sucesso!')
        return redirect('estoque:produto_list')
    return render(request, 'estoque/produto_confirm_delete.html', {'objeto': produto})


@login_required
def produto_preco_api(request, pk):
    """API interna: retorna preço de venda e estoque do produto (usado pelo form de venda)."""
    produto = get_object_or_404(Produto, pk=pk, ativo=True)
    return JsonResponse({
        'preco_venda': str(produto.preco_venda),
        'estoque': produto.estoque_quantidade,
        'filamento_disponivel_g': str(produto.filamento.peso_disponivel_g),
        'peso_filamento_g': str(produto.peso_filamento_g),
    })
