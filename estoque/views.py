from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, ExpressionWrapper, F, FloatField, Q
from django.http import JsonResponse
from .models import Filamento, Produto, Fornecedor
from .forms import FilamentoForm, ProdutoForm, FornecedorForm

PAGE_SIZES = [10, 20, 50, 100, 500, 1000]
DEFAULT_PAGE_SIZE = 20


def _page_size(request):
    try:
        s = int(request.GET.get('per_page', DEFAULT_PAGE_SIZE))
        return s if s in PAGE_SIZES else DEFAULT_PAGE_SIZE
    except (ValueError, TypeError):
        return DEFAULT_PAGE_SIZE


def _qp(request, *drop):
    """Query-params sem 'page' e sem as chaves em *drop."""
    p = request.GET.copy()
    p.pop('page', None)
    for k in drop:
        p.pop(k, None)
    return p.urlencode()


def _is_admin(request):
    return (
        request.user.is_superuser
        or request.user.groups.filter(name='Administradores').exists()
    )


# ==================== Filamentos ====================

@login_required
def filamento_list(request):
    qs = Filamento.objects.select_related('fornecedor').annotate(
        num_produtos=Count('produtos', filter=Q(produtos__ativo=True)),
        pct=ExpressionWrapper(
            100.0 * F('peso_disponivel_g') / F('peso_total_g'),
            output_field=FloatField(),
        ),
    ).order_by('nome')

    busca = request.GET.get('busca', '').strip()
    material_f = request.GET.get('material', '').strip()
    fornecedor_f = request.GET.get('fornecedor', '').strip()
    status_f = request.GET.get('status', '').strip()

    if busca:
        qs = qs.filter(Q(nome__icontains=busca) | Q(cor__icontains=busca))
    if material_f:
        qs = qs.filter(material=material_f)
    if fornecedor_f:
        qs = qs.filter(fornecedor_id=fornecedor_f)
    if status_f == 'Crítico':
        qs = qs.filter(pct__lte=10)
    elif status_f == 'Baixo':
        qs = qs.filter(pct__gt=10, pct__lte=30)
    elif status_f == 'OK':
        qs = qs.filter(pct__gt=30)

    per_page = _page_size(request)
    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    from .models import MATERIAL_CHOICES
    return render(request, 'estoque/filamento_list.html', {
        'page_obj': page_obj,
        'filamentos': page_obj,
        'fornecedores_opts': Fornecedor.objects.order_by('nome'),
        'materiais_opts': MATERIAL_CHOICES,
        'busca': busca,
        'material_f': material_f,
        'fornecedor_f': fornecedor_f,
        'status_f': status_f,
        'per_page': per_page,
        'page_sizes': PAGE_SIZES,
        'query_params': _qp(request),
        'query_params_base': _qp(request, 'per_page'),
    })


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
    is_admin = _is_admin(request)
    if request.method == 'POST':
        acao = request.POST.get('acao', 'excluir')
        if acao == 'force' and is_admin:
            nome = str(filamento)
            # Cascata manual: remove vendas → produtos → filamento
            for produto in filamento.produtos.all():
                produto.vendas.all().delete()
                produto.delete()
            filamento.delete()
            messages.success(request, f'Filamento "{nome}" e todos os itens vinculados excluídos permanentemente.')
        else:
            try:
                filamento.delete()
                messages.success(request, 'Filamento excluído com sucesso!')
            except Exception:
                messages.error(request, 'Não é possível excluir: filamento vinculado a produtos. Use a opção de exclusão forçada.')
        return redirect('estoque:filamento_list')
    num_produtos = filamento.produtos.count()
    return render(request, 'estoque/filamento_confirm_delete.html', {
        'objeto': filamento,
        'is_admin': is_admin,
        'num_produtos': num_produtos,
    })


# ==================== Produtos ====================

@login_required
def produto_list(request):
    is_admin = _is_admin(request)

    # Filtro ativo: padrão "ativo"; admins podem ver inativo ou todos
    ativo_f = request.GET.get('ativo', 'ativo').strip()
    if is_admin and ativo_f == 'inativo':
        qs = Produto.objects.select_related('filamento').filter(ativo=False).order_by('nome')
    elif is_admin and ativo_f == 'todos':
        qs = Produto.objects.select_related('filamento').all().order_by('nome')
    else:
        qs = Produto.objects.select_related('filamento').filter(ativo=True).order_by('nome')
        ativo_f = 'ativo'

    busca = request.GET.get('busca', '').strip()
    material_f = request.GET.get('material', '').strip()

    if busca:
        qs = qs.filter(Q(nome__icontains=busca) | Q(sku__icontains=busca))
    if material_f:
        qs = qs.filter(filamento__material=material_f)

    total_inativos = Produto.objects.filter(ativo=False).count()

    per_page = _page_size(request)
    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    from .models import MATERIAL_CHOICES
    return render(request, 'estoque/produto_list.html', {
        'page_obj': page_obj,
        'produtos': page_obj,
        'is_admin': is_admin,
        'ativo_f': ativo_f,
        'busca': busca,
        'material_f': material_f,
        'materiais_opts': MATERIAL_CHOICES,
        'total_inativos': total_inativos,
        'per_page': per_page,
        'page_sizes': PAGE_SIZES,
        'query_params': _qp(request),
        'query_params_base': _qp(request, 'per_page'),
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
    is_admin = _is_admin(request)
    if request.method == 'POST':
        acao = request.POST.get('acao', 'desativar')
        if acao == 'excluir' and is_admin:
            nome = str(produto)
            # Remove vendas vinculadas (cascade limpa MovimentacaoCaixa via OneToOne CASCADE)
            produto.vendas.all().delete()
            produto.delete()
            messages.success(request, f'Produto "{nome}" excluído permanentemente.')
        else:
            produto.ativo = False
            produto.save()
            messages.success(request, 'Produto desativado com sucesso!')
        return redirect('estoque:produto_list')
    return render(request, 'estoque/produto_confirm_delete.html', {
        'objeto': produto,
        'is_admin': is_admin,
        'num_vendas': produto.vendas.count(),
    })


@login_required
def produto_toggle_ativo(request, pk):
    """Reativa (ou desativa) um produto. Exclusivo para Administradores."""
    if not _is_admin(request):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    produto = get_object_or_404(Produto, pk=pk)
    if request.method == 'POST':
        produto.ativo = not produto.ativo
        produto.save(update_fields=['ativo'])
        estado = 'ativado' if produto.ativo else 'desativado'
        messages.success(request, f'Produto "{produto.nome}" {estado} com sucesso!')
    return redirect(request.POST.get('next', 'estoque:produto_list'))


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


# ==================== Fornecedores ====================

@login_required
def fornecedor_list(request):
    qs = Fornecedor.objects.annotate(
        num_filamentos=Count('filamentos'),
        num_caixa=Count('movimentacoes_caixa'),
    ).order_by('nome')

    busca = request.GET.get('busca', '').strip()
    if busca:
        qs = qs.filter(Q(nome__icontains=busca) | Q(email__icontains=busca))

    per_page = _page_size(request)
    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'estoque/fornecedor_list.html', {
        'page_obj': page_obj,
        'fornecedores': page_obj,
        'busca': busca,
        'per_page': per_page,
        'page_sizes': PAGE_SIZES,
        'query_params': _qp(request),
        'query_params_base': _qp(request, 'per_page'),
    })


@login_required
def fornecedor_create(request):
    form = FornecedorForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, 'Fornecedor cadastrado com sucesso!')
        return redirect('estoque:fornecedor_list')
    return render(request, 'estoque/fornecedor_form.html', {
        'form': form,
        'titulo': 'Novo Fornecedor',
    })


@login_required
def fornecedor_update(request, pk):
    fornecedor = get_object_or_404(Fornecedor, pk=pk)
    form = FornecedorForm(request.POST or None, instance=fornecedor)
    if form.is_valid():
        form.save()
        messages.success(request, 'Fornecedor atualizado com sucesso!')
        return redirect('estoque:fornecedor_list')
    return render(request, 'estoque/fornecedor_form.html', {
        'form': form,
        'titulo': 'Editar Fornecedor',
        'objeto': fornecedor,
    })


@login_required
def fornecedor_delete(request, pk):
    fornecedor = get_object_or_404(Fornecedor, pk=pk)
    is_admin = _is_admin(request)
    if request.method == 'POST':
        if is_admin:
            # FK é SET_NULL em filamentos e caixa — deleção segura, sem cascata destrutiva
            nome = str(fornecedor)
            fornecedor.delete()
            messages.success(request, f'Fornecedor "{nome}" excluído com sucesso.')
        else:
            if fornecedor.filamentos.exists():
                messages.error(request, 'Não é possível excluir: fornecedor vinculado a filamentos.')
                return redirect('estoque:fornecedor_list')
            if fornecedor.movimentacoes_caixa.exists():
                messages.error(request, 'Não é possível excluir: fornecedor vinculado a movimentações de caixa.')
                return redirect('estoque:fornecedor_list')
            fornecedor.delete()
            messages.success(request, 'Fornecedor excluído com sucesso!')
        return redirect('estoque:fornecedor_list')
    return render(request, 'estoque/fornecedor_confirm_delete.html', {
        'objeto': fornecedor,
        'is_admin': is_admin,
        'num_filamentos': fornecedor.filamentos.count(),
        'num_caixa': fornecedor.movimentacoes_caixa.count(),
    })


@login_required
def fornecedor_uso(request, pk):
    fornecedor = get_object_or_404(Fornecedor, pk=pk)
    filamentos = fornecedor.filamentos.all()
    movimentacoes = fornecedor.movimentacoes_caixa.order_by('-data', '-criado_em')
    return render(request, 'estoque/fornecedor_uso.html', {
        'fornecedor': fornecedor,
        'filamentos': filamentos,
        'movimentacoes': movimentacoes,
    })


@login_required
def filamento_uso(request, pk):
    filamento = get_object_or_404(Filamento, pk=pk)
    produtos = filamento.produtos.filter(ativo=True).order_by('nome')
    inativos = filamento.produtos.filter(ativo=False).order_by('nome')
    return render(request, 'estoque/filamento_uso.html', {
        'filamento': filamento,
        'produtos': produtos,
        'inativos': inativos,
    })
