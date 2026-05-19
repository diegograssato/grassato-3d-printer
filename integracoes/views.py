import json
import logging
import sys
from io import BytesIO

from decouple import config as env_config
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .forms import IntegracaoForm, ProdutoIntegracaoForm
from .models import Integracao, ProdutoIntegracao
from .services.mercadolivre import MercadoLivreService

logger = logging.getLogger(__name__)


def _processar_imagem_ml(arquivo):
    """
    Processa a imagem para garantir compatibilidade com os requisitos do ML:
    - Converte para modo RGB (remove canal alfa de PNG/WEBP)
    - Redimensiona para no máximo 1200×1200px preservando proporção
    - Converte para JPEG com qualidade 85 e metadados EXIF removidos
    Retorna um InMemoryUploadedFile pronto para salvar no model.
    Lança ValueError se a imagem não puder ser processada.
    """
    from PIL import Image, UnidentifiedImageError
    from django.core.files.uploadedfile import InMemoryUploadedFile

    MAX_DIM = 1200

    try:
        arquivo.seek(0)
        img = Image.open(arquivo)
        img.load()
    except (UnidentifiedImageError, Exception) as exc:
        raise ValueError(f'Não foi possível processar "{arquivo.name}": {exc}')

    # Remove EXIF/metadados abrindo sem eles
    data = list(img.getdata())
    clean = Image.new(img.mode, img.size)
    clean.putdata(data)
    img = clean

    # Garante modo RGB (fundo branco para transparências)
    if img.mode in ('RGBA', 'LA', 'P'):
        if img.mode == 'P':
            img = img.convert('RGBA')
        bg = Image.new('RGB', img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1])
        img = bg
    elif img.mode != 'RGB':
        img = img.convert('RGB')

    # Redimensiona se maior que 1200×1200 (mantém proporção)
    w, h = img.size
    if w > MAX_DIM or h > MAX_DIM:
        img.thumbnail((MAX_DIM, MAX_DIM), Image.LANCZOS)

    # Salva como JPEG
    output = BytesIO()
    img.save(output, format='JPEG', quality=85, optimize=True)
    size = output.tell()
    output.seek(0)

    nome_base = arquivo.name.rsplit('.', 1)[0]
    return InMemoryUploadedFile(
        output, 'ImageField', f'{nome_base}.jpg', 'image/jpeg', size, None
    )


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
    """Callback OAuth: enfileira a troca do code pelo access_token via Celery.
    Sem @login_required pois o ML redireciona sem manter a sessão Django.
    A segurança é garantida pelo parâmetro `state` (pk da integração).
    """
    from .tasks import processar_oauth_ml

    code = request.GET.get('code', '').strip()
    pk = request.GET.get('state', '').strip()

    if not code or not pk:
        messages.error(request, 'Parâmetros inválidos no callback do MercadoLivre.')
        return redirect('integracoes:integracao_list')

    integracao = get_object_or_404(Integracao, pk=pk, plataforma='ML')

    # O redirect_uri deve ser IDÊNTICO ao cadastrado no painel de desenvolvedores ML
    redirect_uri = _ml_redirect_uri(request)

    # Enfileira a troca do código na fila ml_oauth — resposta imediata ao usuário
    # Em dev (DEBUG=True / CELERY_TASK_ALWAYS_EAGER=True) executa inline com feedback imediato
    result = processar_oauth_ml.apply_async(
        args=[integracao.pk, code, redirect_uri],
        queue='ml_oauth',
    )
    logger.info(
        'ml_callback: task processar_oauth_ml enfileirada para integracao_pk=%s',
        integracao.pk,
    )

    from django.conf import settings as dj_settings
    if getattr(dj_settings, 'CELERY_TASK_ALWAYS_EAGER', False):
        # Resultado disponível inline em dev — mostra feedback real ao usuário
        outcome = result.get()
        if outcome.get('ok'):
            integracao.refresh_from_db()
            messages.success(
                request,
                f'MercadoLivre autorizado com sucesso! Seller ID: {integracao.ml_user_id}'
            )
        else:
            messages.error(
                request,
                f'Falha ao autorizar com o MercadoLivre: {outcome.get("error")} '
                f'— verifique se o Redirect URI cadastrado no ML é exatamente: {redirect_uri}'
            )
    else:
        messages.info(
            request,
            'Autorização com o MercadoLivre em processamento. '
            'Aguarde alguns segundos e atualize a página para confirmar.'
        )
    return redirect('integracoes:integracao_list')


# ── Produto ↔ Integração ──────────────────────────────────────────────────────

@login_required
def produto_integracao_create(request, produto_pk):
    """Vincula um produto a uma integração, salva imagens e publica o anúncio."""
    from estoque.models import Produto
    produto = get_object_or_404(Produto, pk=produto_pk)
    existentes = ProdutoIntegracao.objects.filter(produto=produto).select_related('integracao')

    form = ProdutoIntegracaoForm(
        request.POST or None,
        request.FILES or None,
        produto=produto,
    )
    if form.is_valid():
        pi = form.save(commit=False)
        pi.produto = produto

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

            # Salva pi primeiro para ter PK e poder vincular as imagens
            pi.save()

            # Processa e persiste imagens, constrói picture_urls com URLs públicas
            from .models import ImagemProdutoIntegracao
            from django.conf import settings as dj_settings
            arquivos = form.cleaned_data.get('imagens') or []
            picture_urls_list = []
            erros_imagem = []

            for idx, arquivo in enumerate(arquivos):
                try:
                    arquivo_processado = _processar_imagem_ml(arquivo)
                except ValueError as exc:
                    erros_imagem.append(str(exc))
                    continue

                img_obj = ImagemProdutoIntegracao.objects.create(
                    produto_integracao=pi,
                    imagem=arquivo_processado,
                    is_capa=(idx == 0),
                    ordem=idx,
                )
                site_url = getattr(dj_settings, 'SITE_URL', '').rstrip('/')
                picture_urls_list.append(f'{site_url}{img_obj.imagem.url}')
                logger.info(
                    'Imagem ML salva: %s (capa=%s) → %s',
                    img_obj.imagem.name, idx == 0, img_obj.imagem.url,
                )

            if erros_imagem:
                pi.delete()
                for erro in erros_imagem:
                    messages.error(request, erro)
                return render(request, 'integracoes/produto_integracao_form.html', {
                    'form': form, 'produto': produto, 'existentes': existentes
                })

            if len(picture_urls_list) < 2:
                pi.delete()
                messages.error(
                    request,
                    'Não foi possível processar as imagens. Verifique os arquivos e tente novamente.'
                )
                return render(request, 'integracoes/produto_integracao_form.html', {
                    'form': form, 'produto': produto, 'existentes': existentes
                })

            pi.picture_urls = '\n'.join(picture_urls_list)
            pi.save(update_fields=['picture_urls'])

            resultado, error_msg = ml_service.create_listing(integracao, pi)
            if resultado:
                pi.sku_externo = resultado['id']
                pi.status_externo = resultado.get('status', 'active')
                pi.sincronizado_em = timezone.now()
                pi.save(update_fields=['sku_externo', 'status_externo', 'sincronizado_em'])
                messages.success(
                    request,
                    f'Produto publicado no MercadoLivre! ID do anúncio: {pi.sku_externo}'
                )
            else:
                messages.error(request, f'Erro ao publicar no MercadoLivre: {error_msg}')
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
    """Remove o vínculo e pausa o anúncio no MercadoLivre (via signal pre_delete)."""
    pi = get_object_or_404(ProdutoIntegracao, pk=pk)
    if request.method == 'POST':
        sku = pi.sku_externo or ''
        pi.delete()
        if sku:
            messages.success(
                request,
                f'Vínculo removido e anúncio {sku} pausado no MercadoLivre.'
            )
        else:
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
def ml_categorias_busca_json(request):
    """
    AJAX: busca categorias ML por termo e retorna JSON para o modal de seleção.
    GET ?q=impressora+3d
    """
    term = request.GET.get('q', '').strip()
    if not term or len(term) < 2:
        return JsonResponse({'results': [], 'error': 'Digite ao menos 2 caracteres.'})

    resultados = ml_service.search_categories(term)
    return JsonResponse({'results': [
        {
            'id': r.get('category_id', ''),
            'name': r.get('category_name', ''),
            'domain': r.get('domain_name', ''),
        }
        for r in resultados
    ]})


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
def ml_notificacao(request):
    """
    Endpoint público para receber notificações do MercadoLivre (IPN/Webhook).
    URL deve ser registrada no painel de developers do ML.

    GET  → retorna 200 para validação da URL pelo painel de developers do ML.
    POST → enfileira o processamento via Celery (resposta em < 500ms).
    """
    # ML envia GET ao salvar a URL no painel — basta confirmar que o endpoint existe
    if request.method == 'GET':
        return HttpResponse(status=200)

    if request.method != 'POST':
        return HttpResponse(status=405)

    from .tasks import processar_pedido_ml, processar_status_ml

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        # Alguns clientes do ML enviam form-encoded — tenta fallback
        data = request.POST.dict()

    if not data:
        return HttpResponse(status=200)

    topic = data.get('topic', '')
    resource = data.get('resource', '')
    user_id = str(data.get('user_id', ''))

    logger.info('ML notification: topic=%s resource=%s user_id=%s', topic, resource, user_id)

    try:
        integracao = Integracao.objects.get(ml_user_id=user_id, plataforma='ML', ativa=True)
    except Integracao.DoesNotExist:
        logger.warning('ML notification: nenhuma integração para user_id=%s', user_id)
        return HttpResponse(status=200)

    if topic in ('orders_v2', 'orders'):
        try:
            order_id = resource.strip('/').split('/')[-1]
        except (AttributeError, IndexError):
            return HttpResponse(status=200)

        processar_pedido_ml.apply_async(
            args=[integracao.pk, order_id],
            queue='ml_orders',
        )
        logger.info(
            'ml_notificacao: task processar_pedido_ml enfileirada — order_id=%s integracao=%s',
            order_id,
            integracao.pk,
        )

    elif topic in ('items', 'item_status', 'item_price'):
        processar_status_ml.apply_async(
            args=[integracao.pk, topic, resource],
            queue='ml_status',
        )
        logger.info(
            'ml_notificacao: task processar_status_ml enfileirada — resource=%s integracao=%s',
            resource,
            integracao.pk,
        )

    else:
        logger.info('ml_notificacao: topic=%s ignorado', topic)

    return HttpResponse(status=200)
