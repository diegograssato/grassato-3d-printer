"""
Tasks Celery para processamento assíncrono das integrações com MercadoLivre.

Filas utilizadas:
  - ml_oauth   : troca do authorization code pelo access_token
  - ml_orders  : processamento de pedidos recebidos via IPN/webhook
  - ml_status  : atualizações de status de anúncios
  - ml_sync    : sincronização de produto (preço, estoque, ativo) → ML
"""
import logging
from decimal import Decimal

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


# ── Fila: ml_oauth ────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    queue='ml_oauth',
    name='integracoes.tasks.processar_oauth_ml',
    max_retries=3,
    default_retry_delay=10,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def processar_oauth_ml(self, integracao_pk: int, code: str, redirect_uri: str) -> dict:
    """
    Troca o authorization code do ML pelo access_token/refresh_token.
    Executado de forma assíncrona para não bloquear a resposta ao usuário.
    """
    from .models import Integracao
    from .services.mercadolivre import MercadoLivreService

    logger.info(
        'processar_oauth_ml: iniciando troca de código para integracao_pk=%s',
        integracao_pk,
    )

    try:
        integracao = Integracao.objects.get(pk=integracao_pk, plataforma='ML')
    except Integracao.DoesNotExist:
        logger.error('processar_oauth_ml: integração %s não encontrada', integracao_pk)
        return {'ok': False, 'error': 'Integração não encontrada'}

    ml_service = MercadoLivreService()
    ok, error_msg = ml_service.exchange_code(integracao, code, redirect_uri)

    if ok:
        logger.info(
            'processar_oauth_ml: autorizado com sucesso — seller_id=%s integracao=%s',
            integracao.ml_user_id,
            integracao_pk,
        )
        return {'ok': True, 'seller_id': integracao.ml_user_id}

    logger.error(
        'processar_oauth_ml: falha na troca de código para integracao=%s — %s',
        integracao_pk,
        error_msg,
    )
    return {'ok': False, 'error': error_msg}


# ── Fila: ml_orders ───────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    queue='ml_orders',
    name='integracoes.tasks.processar_pedido_ml',
    max_retries=5,
    default_retry_delay=30,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def processar_pedido_ml(self, integracao_pk: int, order_id: str) -> dict:
    """
    Processa um pedido recebido via IPN do MercadoLivre:
    - Cria Venda no sistema
    - Decrementa estoque via signal
    - Lança no caixa via signal
    - Registra evento de auditoria com JSON bruto do pedido
    """
    from .models import Integracao, ProdutoIntegracao
    from .services.mercadolivre import MercadoLivreService
    from vendas.models import Venda
    from auditoria.middleware import set_integration_context, clear_integration_context

    logger.info(
        'processar_pedido_ml: iniciando order_id=%s integracao_pk=%s',
        order_id,
        integracao_pk,
    )

    try:
        integracao = Integracao.objects.get(pk=integracao_pk, plataforma='ML', ativa=True)
    except Integracao.DoesNotExist:
        logger.error(
            'processar_pedido_ml: integração %s não encontrada ou inativa', integracao_pk
        )
        return {'ok': False, 'error': 'Integração não encontrada'}

    # Configura contexto de auditoria para identificar a origem como integração ML
    set_integration_context('ML', f'MercadoLivre — {integracao.nome}')

    try:
        ml_service = MercadoLivreService()
        order = ml_service.get_order(integracao, order_id)

        if not order:
            logger.warning('processar_pedido_ml: order %s não encontrado no ML', order_id)
            return {'ok': False, 'error': 'Pedido não encontrado na API do ML'}

        status = order.get('status', '')
        if status not in ('paid', 'payment_required'):
            logger.info(
                'processar_pedido_ml: order %s status=%s — ignorado', order_id, status
            )
            return {'ok': True, 'skipped': True, 'status': status}

        vendas_criadas = []
        for order_item in order.get('order_items', []):
            item_id = order_item.get('item', {}).get('id', '')
            quantity = int(order_item.get('quantity', 1))
            unit_price = Decimal(str(order_item.get('unit_price', 0)))

            try:
                pi = ProdutoIntegracao.objects.select_related('produto').get(
                    sku_externo=item_id, integracao=integracao
                )
            except ProdutoIntegracao.DoesNotExist:
                logger.warning(
                    'processar_pedido_ml: item %s do order %s não mapeado no sistema',
                    item_id,
                    order_id,
                )
                continue

            # O signal vendas.signals.venda_post_save cuida do caixa e do estoque.
            # O AuditLog será gravado pelo signal post_save de Venda com event_json do pedido.
            from auditoria.signals import _write_log as _audit_write
            venda = Venda.objects.create(
                produto=pi.produto,
                quantidade=quantity,
                preco_unitario=unit_price,
                data=timezone.now().date(),
                forma_pagamento='CARTAO_CREDITO',
                observacoes=f'Venda via MercadoLivre — pedido #{order_id}',
            )
            # Grava log extra com JSON bruto do pedido ML
            try:
                _audit_write('CRIADO', venda, event_json=order)
            except Exception:
                pass

            vendas_criadas.append(venda.pk)
            logger.info(
                'processar_pedido_ml: venda=%s criada — produto=%s qtd=%d order=%s',
                venda.pk,
                pi.produto,
                quantity,
                order_id,
            )

        return {'ok': True, 'order_id': order_id, 'vendas': vendas_criadas}

    finally:
        clear_integration_context()


# ── Fila: ml_status ───────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    queue='ml_status',
    name='integracoes.tasks.processar_status_ml',
    max_retries=3,
    default_retry_delay=20,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def processar_status_ml(self, integracao_pk: int, topic: str, resource: str) -> dict:
    """
    Processa notificações de mudança de status de anúncios recebidas via IPN.
    Atualiza o status_externo do ProdutoIntegracao correspondente.
    """
    from .models import Integracao, ProdutoIntegracao
    from .services.mercadolivre import MercadoLivreService

    logger.info(
        'processar_status_ml: topic=%s resource=%s integracao_pk=%s',
        topic,
        resource,
        integracao_pk,
    )

    try:
        integracao = Integracao.objects.get(pk=integracao_pk, plataforma='ML', ativa=True)
    except Integracao.DoesNotExist:
        logger.error('processar_status_ml: integração %s não encontrada', integracao_pk)
        return {'ok': False, 'error': 'Integração não encontrada'}

    ml_service = MercadoLivreService()

    # Extrai item_id do resource (/items/MLB123456)
    try:
        item_id = resource.strip('/').split('/')[-1]
    except (AttributeError, IndexError):
        logger.warning('processar_status_ml: resource inválido — %s', resource)
        return {'ok': False, 'error': 'Resource inválido'}

    item = ml_service.get_item(integracao, item_id)
    if not item:
        logger.warning('processar_status_ml: item %s não encontrado no ML', item_id)
        return {'ok': False, 'error': 'Item não encontrado no ML'}

    novo_status = item.get('status', '')
    updated = ProdutoIntegracao.objects.filter(
        sku_externo=item_id, integracao=integracao
    ).update(status_externo=novo_status, sincronizado_em=timezone.now())

    logger.info(
        'processar_status_ml: item=%s novo_status=%s registros_atualizados=%d',
        item_id,
        novo_status,
        updated,
    )
    return {'ok': True, 'item_id': item_id, 'status': novo_status, 'updated': updated}


# ── Fila: ml_sync ─────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    queue='ml_sync',
    name='integracoes.tasks.sincronizar_produto_ml',
    max_retries=3,
)
def sincronizar_produto_ml(self, produto_pk: int, pi_pk: int) -> dict:
    """
    Sincroniza o estado atual de um produto com o anúncio no MercadoLivre.

    Sempre lê o estado mais recente do banco — idempotente por design.
    Disparado pelo signal post_save de Produto quando preço, estoque ou
    campo 'ativo' são alterados.

    Lógica:
      - produto.ativo=False         → pausa anúncio
      - produto.estoque_quantidade=0 → pausa anúncio
      - caso contrário              → atualiza preço, título e estoque
                                      reativa se estava pausado

    Em caso de falha definitiva (retries esgotados), grava AuditLog.
    """
    from estoque.models import Produto
    from .models import ProdutoIntegracao
    from .services.mercadolivre import MercadoLivreService

    logger.info(
        'sincronizar_produto_ml: produto_pk=%s pi_pk=%s tentativa=%d/%d',
        produto_pk, pi_pk, self.request.retries + 1, self.max_retries + 1,
    )

    try:
        produto = Produto.objects.get(pk=produto_pk)
    except Produto.DoesNotExist:
        logger.warning('sincronizar_produto_ml: produto %s não encontrado', produto_pk)
        return {'ok': False, 'error': 'Produto não encontrado'}

    try:
        pi = ProdutoIntegracao.objects.select_related('integracao').get(
            pk=pi_pk,
            integracao__plataforma='ML',
            integracao__ativa=True,
        )
    except ProdutoIntegracao.DoesNotExist:
        logger.warning('sincronizar_produto_ml: ProdutoIntegracao %s não encontrada', pi_pk)
        return {'ok': False, 'error': 'ProdutoIntegracao não encontrada'}

    if not pi.sku_externo:
        logger.info('sincronizar_produto_ml: pi=%s sem sku_externo — produto não publicado', pi_pk)
        return {'ok': False, 'error': 'sku_externo não definido — produto não publicado'}

    ml = MercadoLivreService()
    acoes = []

    try:
        # ── Produto inativo → pausa anúncio ──────────────────────────────────
        if not produto.ativo:
            ok = ml.pause_listing(pi.integracao, pi.sku_externo)
            if not ok:
                raise Exception(f'Falha ao pausar anúncio {pi.sku_externo} (produto inativo)')
            if pi.status_externo != 'paused':
                ProdutoIntegracao.objects.filter(pk=pi.pk).update(status_externo='paused')
            acoes.append('pause:inativo')
            logger.info('sincronizar_produto_ml: %s pausado — produto inativo', pi.sku_externo)
            return {'ok': True, 'pi_pk': pi_pk, 'acoes': acoes}

        # ── Estoque zerado → pausa anúncio ───────────────────────────────────
        qtd = produto.estoque_quantidade
        if qtd <= 0:
            ok = ml.pause_listing(pi.integracao, pi.sku_externo)
            if not ok:
                raise Exception(f'Falha ao pausar anúncio {pi.sku_externo} (estoque=0)')
            if pi.status_externo != 'paused':
                ProdutoIntegracao.objects.filter(pk=pi.pk).update(status_externo='paused')
            acoes.append('pause:estoque_zero')
            logger.info('sincronizar_produto_ml: %s pausado — estoque=0', pi.sku_externo)
            return {'ok': True, 'pi_pk': pi_pk, 'acoes': acoes}

        # ── Produto ativo + estoque > 0 → sincroniza ─────────────────────────
        if pi.status_externo == 'paused':
            ok = ml.activate_listing(pi.integracao, pi.sku_externo)
            if not ok:
                raise Exception(f'Falha ao reativar anúncio {pi.sku_externo}')
            ProdutoIntegracao.objects.filter(pk=pi.pk).update(status_externo='active')
            acoes.append('activate')
            logger.info('sincronizar_produto_ml: %s reativado', pi.sku_externo)

        # Envia preço, título e estoque em uma única chamada
        payload = {
            'available_quantity': qtd,
            'price': float(produto.preco_venda),
            'title': produto.nome,
        }
        ok = ml.update_listing(pi.integracao, pi.sku_externo, payload)
        if not ok:
            raise Exception(
                f'Falha ao atualizar anúncio {pi.sku_externo} campos={list(payload.keys())}'
            )
        acoes.append('update')
        logger.info(
            'sincronizar_produto_ml: %s atualizado — qtd=%d preco=%.2f',
            pi.sku_externo, qtd, produto.preco_venda,
        )
        return {'ok': True, 'pi_pk': pi_pk, 'acoes': acoes}

    except Exception as exc:
        retries_restantes = self.max_retries - self.request.retries
        if retries_restantes <= 0:
            # ── Retries esgotados → grava auditoria ──────────────────────────
            logger.error(
                'sincronizar_produto_ml: falha definitiva produto=%s pi=%s — %s',
                produto_pk, pi_pk, exc,
            )
            try:
                from auditoria.signals import _write_log as _audit_write
                _audit_write(
                    'ATUALIZADO',
                    produto,
                    changes={
                        'ml_sync_erro': str(exc),
                        'pi_pk': pi_pk,
                        'task_id': self.request.id,
                        'tentativas': self.max_retries + 1,
                    },
                )
            except Exception as audit_exc:
                logger.warning('Falha ao gravar auditoria de sync ML: %s', audit_exc)
            return {'ok': False, 'error': str(exc)}

        backoff = 30 * (2 ** self.request.retries)  # 30s → 60s → 120s
        logger.warning(
            'sincronizar_produto_ml: erro (tentativa %d/%d) — retry em %ds — %s',
            self.request.retries + 1, self.max_retries + 1, backoff, exc,
        )
        raise self.retry(exc=exc, countdown=backoff)
