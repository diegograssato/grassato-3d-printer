import json
import logging

from decouple import config as env_config
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .forms import IntegracaoForm, ProdutoIntegracaoForm
from .models import Integracao, ProdutoIntegracao
from .services.mercadolivre import MercadoLivreService

logger = logging.getLogger(__name__)
ml_service = MercadoLivreService()


# ── Integrações CRUD ──────────────────────────────────────────────────────────

@login_required
def integracao_list(request):
    integracoes = Integracao.objects.prefetch_related('produto_integracoes__produto').all()
    return render(request, 'integracoes/integracao_list.html', {'integracoes': integracoes})


@login_required
def integracao_create(request):
    form = IntegracaoForm(request.POST or None)
    if form.is_valid():
        integracao = form.save()
        messages.success(
            request,
            f'Integração "{integracao}" criada! Agora clique em "Autorizar" para conectar sua conta.'
        )
        return redirect('integracoes:integracao_list')
    return render(request, 'integracoes/integracao_form.html', {
        'form': form, 'titulo': 'Nova Integração'
    })


@login_required
def integracao_update(request, pk):
    integracao = get_object_or_404(Integracao, pk=pk)
    form = IntegracaoForm(request.POST or None, instance=integracao)
    if form.is_valid():
        form.save()
        messages.success(request, 'Integração atualizada com sucesso.')
        return redirect('integracoes:integracao_list')
    return render(request, 'integracoes/integracao_form.html', {
        'form': form, 'titulo': 'Editar Integração', 'objeto': integracao
    })


@login_required
def integracao_delete(request, pk):
    integracao = get_object_or_404(Integracao, pk=pk)
    if request.method == 'POST':
        integracao.delete()
        messages.success(request, 'Integração removida.')
        return redirect('integracoes:integracao_list')
    return render(request, 'integracoes/integracao_confirm_delete.html', {'objeto': integracao})


# ── OAuth MercadoLivre ────────────────────────────────────────────────────────

def _ml_redirect_uri(request) -> str:
    """
    Retorna a Redirect URI para o OAuth do ML.
    Prioridade: variável de ambiente ML_CALLBACK_URI (ngrok / domínio real)
    Fallback: URI construída a partir do request atual (funciona em produção).
    """
    override = env_config('ML_CALLBACK_URI', default='')
    if override:
        return override.rstrip('/') + '/'
    return request.build_absolute_uri('/integracoes/ml/callback/')


@login_required
def ml_authorize(request, pk):
    """Redireciona para a página de autorização do MercadoLivre."""
    integracao = get_object_or_404(Integracao, pk=pk, plataforma='ML')
    redirect_uri = _ml_redirect_uri(request)
    auth_url = ml_service.get_authorization_url(
        integracao.client_id, redirect_uri, state=str(pk)
    )
    return redirect(auth_url)


def ml_callback(request):
    """Callback OAuth: troca o code pelo access_token.
    Sem @login_required pois o ML redireciona sem manter a sessão Django.
    A segurança é garantida pelo parâmetro `state` (pk da integração).
    """
    code = request.GET.get('code', '').strip()
    pk = request.GET.get('state', '').strip()

    if not code or not pk:
        messages.error(request, 'Parâmetros inválidos no callback do MercadoLivre.')
        return redirect('integracoes:integracao_list')

    integracao = get_object_or_404(Integracao, pk=pk, plataforma='ML')

    # O redirect_uri deve ser IDÊNTICO ao cadastrado no painel de desenvolvedores ML
    redirect_uri = _ml_redirect_uri(request)

    ok, error_msg = ml_service.exchange_code(integracao, code, redirect_uri)

    if ok:
        messages.success(
            request,
            f'MercadoLivre autorizado com sucesso! Seller ID: {integracao.ml_user_id}'
        )
    else:
        messages.error(
            request,
            f'Falha ao autorizar com o MercadoLivre: {error_msg} '
            f'— verifique se o Redirect URI cadastrado no ML é exatamente: {redirect_uri}'
        )
    return redirect('integracoes:integracao_list')


# ── Produto ↔ Integração ──────────────────────────────────────────────────────

@login_required
def produto_integracao_create(request, produto_pk):
    """Vincula um produto a uma integração e publica o anúncio."""
    from estoque.models import Produto
    produto = get_object_or_404(Produto, pk=produto_pk)
    existentes = ProdutoIntegracao.objects.filter(produto=produto).select_related('integracao')

    form = ProdutoIntegracaoForm(request.POST or None, produto=produto)
    if form.is_valid():
        pi = form.save(commit=False)
        pi.produto = produto

        # Persiste atributos enviados pelo formulário dinâmico
        attrs_raw = request.POST.get('ml_attributes_json', '').strip()
        if attrs_raw:
            pi.ml_attributes_json = attrs_raw

        integracao = pi.integracao
        if integracao.plataforma == 'ML':
            if not integracao.autorizada:
                messages.error(
                    request,
                    'Integração não autorizada. Autorize o acesso ao MercadoLivre antes.'
                )
                return render(request, 'integracoes/produto_integracao_form.html', {
                    'form': form, 'produto': produto, 'existentes': existentes
                })
            resultado, error_msg = ml_service.create_listing(integracao, pi)
            if resultado:
                pi.sku_externo = resultado['id']
                pi.status_externo = resultado.get('status', 'active')
                pi.sincronizado_em = timezone.now()
                pi.save()
                messages.success(
                    request,
                    f'Produto publicado no MercadoLivre! ID do anúncio: {pi.sku_externo}'
                )
            else:
                messages.error(
                    request,
                    f'Erro ao publicar no MercadoLivre: {error_msg}'
                )
                return render(request, 'integracoes/produto_integracao_form.html', {
                    'form': form, 'produto': produto, 'existentes': existentes
                })
        else:
            pi.save()
            messages.info(request, f'Produto vinculado à integração "{integracao}".')

        return redirect('integracoes:integracao_list')

    return render(request, 'integracoes/produto_integracao_form.html', {
        'form': form, 'produto': produto, 'existentes': existentes
    })


@login_required
def produto_integracao_sync(request, pk):
    """Sincroniza manualmente um produto com o MercadoLivre."""
    pi = get_object_or_404(
        ProdutoIntegracao.objects.select_related('produto', 'integracao'), pk=pk
    )
    if pi.integracao.plataforma != 'ML':
        messages.warning(request, 'Sincronização disponível apenas para MercadoLivre.')
        return redirect('integracoes:integracao_list')

    item = ml_service.get_item(pi.integracao, pi.sku_externo)
    if not item:
        messages.error(request, 'Não foi possível buscar os dados no MercadoLivre.')
        return redirect('integracoes:integracao_list')

    nova_qtd = item.get('available_quantity', pi.produto.estoque_quantidade)
    novo_status = item.get('status', pi.status_externo)

    # Atualiza estoque local com base no ML
    produto = pi.produto
    produto.estoque_quantidade = nova_qtd
    produto._skip_integracoes_signal = True  # evita loop de signal
    produto.save(update_fields=['estoque_quantidade', 'atualizado_em'])

    pi.status_externo = novo_status
    pi.sincronizado_em = timezone.now()
    pi.save(update_fields=['status_externo', 'sincronizado_em'])

    messages.success(
        request,
        f'Sincronizado! Estoque ML: {nova_qtd} un. | Status: {novo_status}'
    )
    return redirect('integracoes:integracao_list')


@login_required
def produto_integracao_delete(request, pk):
    """Remove o vínculo (não desativa o anúncio)."""
    pi = get_object_or_404(ProdutoIntegracao, pk=pk)
    if request.method == 'POST':
        pi.delete()
        messages.success(request, 'Vínculo com a integração removido.')
        return redirect('integracoes:integracao_list')
    return render(request, 'integracoes/produto_integracao_confirm_delete.html', {'pi': pi})


@login_required
def ml_category_attributes(request):
    """
    AJAX: retorna os atributos obrigatórios de uma categoria ML.
    GET ?cat=MLB457416
    """
    category_id = request.GET.get('cat', '').strip()
    if not category_id:
        return JsonResponse({'attributes': [], 'error': 'Informe o ID da categoria.'})

    integracao = Integracao.objects.filter(
        plataforma='ML', ativa=True
    ).exclude(access_token='').first()

    raw_attrs = ml_service.get_category_attributes(category_id, integracao)

    required = []
    for a in raw_attrs:
        tags = a.get('tags', {})
        if tags.get('required') or tags.get('required_marketplace'):
            required.append({
                'id': a['id'],
                'name': a['name'],
                'type': a.get('value_type', 'string'),
                'values': [v['name'] for v in a.get('values', [])],
            })

    return JsonResponse({'attributes': required, 'category_id': category_id})


@login_required
def ml_categorias(request):
    """Pesquisa categorias do MercadoLivre pelo nome para obter o ID correto."""
    term = request.GET.get('q', '').strip()
    categoria_id = request.GET.get('cat', '').strip()

    # Usa a primeira integração ML autorizada para chamadas autenticadas
    integracao_ativa = Integracao.objects.filter(
        plataforma='ML', ativa=True
    ).exclude(access_token='').first()

    resultados = []
    children = []
    categoria_atual = None
    api_error = False

    if term:
        resultados = ml_service.search_categories(term)
        if not resultados:
            api_error = True
    elif categoria_id:
        categoria_atual = ml_service.get_category_children(categoria_id, integracao_ativa)
        children = categoria_atual.get('children_categories', []) if categoria_atual else []
    else:
        children = ml_service.get_root_categories(integracao_ativa)
        if not children:
            api_error = True

    return render(request, 'integracoes/ml_categorias.html', {
        'term': term,
        'resultados': resultados,
        'children': children,
        'categoria_atual': categoria_atual,
        'api_error': api_error,
        'tem_integracao': integracao_ativa is not None,
    })


# ── Webhook MercadoLivre ──────────────────────────────────────────────────────

@csrf_exempt
@require_POST
def ml_notificacao(request):
    """
    Endpoint público para receber notificações do MercadoLivre (IPN/Webhook).
    URL deve ser registrada no painel de developers do ML.
    Retorna 200 imediatamente (ML exige resposta em < 500ms).
    """
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return HttpResponse(status=400)

    topic = data.get('topic', '')
    resource = data.get('resource', '')
    user_id = str(data.get('user_id', ''))

    logger.info('ML notification: topic=%s resource=%s user_id=%s', topic, resource, user_id)

    # Só processa notificações de pedidos
    if topic not in ('orders_v2', 'orders'):
        return HttpResponse(status=200)

    try:
        integracao = Integracao.objects.get(ml_user_id=user_id, plataforma='ML', ativa=True)
    except Integracao.DoesNotExist:
        logger.warning('ML notification: nenhuma integração para user_id=%s', user_id)
        return HttpResponse(status=200)

    # Extrai o order_id do resource (/orders/1234567890)
    try:
        order_id = resource.strip('/').split('/')[-1]
    except (AttributeError, IndexError):
        return HttpResponse(status=200)

    _process_ml_order(integracao, order_id)
    return HttpResponse(status=200)


def _process_ml_order(integracao, order_id: str) -> None:
    """Processa um pedido do ML: cria Venda + baixa estoque + lança no caixa."""
    order = ml_service.get_order(integracao, order_id)
    if not order:
        return

    # Só processa pedidos pagos
    if order.get('status') not in ('paid', 'payment_required'):
        logger.info('ML order %s status=%s — ignorado', order_id, order.get('status'))
        return

    from decimal import Decimal
    from vendas.models import Venda

    for order_item in order.get('order_items', []):
        item_id = order_item.get('item', {}).get('id', '')
        quantity = int(order_item.get('quantity', 1))
        unit_price = Decimal(str(order_item.get('unit_price', 0)))

        try:
            pi = ProdutoIntegracao.objects.select_related('produto').get(
                sku_externo=item_id, integracao=integracao
            )
        except ProdutoIntegracao.DoesNotExist:
            logger.warning('ML order %s: item %s não encontrado no sistema', order_id, item_id)
            continue

        # Cria a Venda — o signal vendas.signals.venda_post_save cuida do
        # caixa, do estoque e da sincronização de volta ao ML
        Venda.objects.create(
            produto=pi.produto,
            quantidade=quantity,
            preco_unitario=unit_price,
            data=timezone.now().date(),
            forma_pagamento='CARTAO_CREDITO',
            observacoes=f'Venda via MercadoLivre — pedido #{order_id}',
        )
        logger.info(
            'ML venda registrada: produto=%s qtd=%d order=%s',
            pi.produto, quantity, order_id
        )
