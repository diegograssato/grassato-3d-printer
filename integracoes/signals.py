"""
Signals do app integracoes:
- pre_save em Produto  → detecta mudanças de nome/preço/ativo para rastrear no ML
- post_save em Produto → enfileira task Celery (ml_sync) para sincronizar com ML
- pre_delete em Produto → pausa anúncio ML SÍNCRONO antes de excluir
"""
import logging

from django.db.models.signals import post_save, pre_delete, pre_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(pre_save, sender='estoque.Produto')
def produto_pre_save_track_ml(sender, instance, **kwargs):
    """
    Rastreia mudanças de nome, preço, ativo e estoque antes do save.
    O resultado é armazenado em instance._ml_changed_fields para uso no post_save.
    """
    if getattr(instance, '_skip_integracoes_signal', False):
        instance._ml_changed_fields = {}
        return

    instance._ml_changed_fields = {}
    if not instance.pk:
        return  # novo produto, sem anúncio ainda

    try:
        old = sender.objects.get(pk=instance.pk)
        if old.nome != instance.nome:
            instance._ml_changed_fields['title'] = True
        if old.preco_venda != instance.preco_venda:
            instance._ml_changed_fields['price'] = True
        if old.ativo != instance.ativo:
            instance._ml_changed_fields['ativo'] = True
        if old.estoque_quantidade != instance.estoque_quantidade:
            instance._ml_changed_fields['estoque'] = True
    except sender.DoesNotExist:
        pass


@receiver(post_save, sender='estoque.Produto')
def produto_post_save_ml(sender, instance, **kwargs):
    """
    Enfileira uma task Celery (fila ml_sync) para cada ProdutoIntegracao ML ativa
    quando nome, preço, estoque ou campo 'ativo' são alterados.

    A sincronização em si é feita de forma assíncrona pela task
    `integracoes.tasks.sincronizar_produto_ml`, que lê o estado mais recente
    do banco — garantindo idempotência.

    Signals de pre_delete permanecem síncronos pois precisam pausar o anúncio
    antes que o objeto seja removido do banco.
    """
    if getattr(instance, '_skip_integracoes_signal', False):
        return

    changed = getattr(instance, '_ml_changed_fields', {})

    # Só enfileira se algum campo ML-relevante foi alterado ou é criação
    if not kwargs.get('created') and not changed:
        return

    try:
        from integracoes.models import ProdutoIntegracao
        from integracoes.tasks import sincronizar_produto_ml
    except Exception:
        return

    pis = ProdutoIntegracao.objects.filter(
        produto=instance,
        integracao__plataforma='ML',
        integracao__ativa=True,
    ).values_list('pk', flat=True)

    for pi_pk in pis:
        try:
            sincronizar_produto_ml.apply_async(
                args=[instance.pk, pi_pk],
                queue='ml_sync',
            )
            logger.info(
                'ML sync enfileirado: produto=%s pi=%s campos=%s',
                instance.pk, pi_pk, list(changed.keys()),
            )
        except Exception as exc:
            logger.error(
                'Falha ao enfileirar ML sync produto=%s pi=%s: %s',
                instance.pk, pi_pk, exc,
            )


@receiver(pre_delete, sender='estoque.Produto')
def produto_pre_delete_ml(sender, instance, **kwargs):
    """
    Antes de excluir o produto: pausa o anúncio ML para manter histórico de vendas.
    """
    try:
        from integracoes.models import ProdutoIntegracao
        from integracoes.services.mercadolivre import MercadoLivreService
    except Exception:
        return

    pis = ProdutoIntegracao.objects.filter(
        produto=instance,
        integracao__plataforma='ML',
        integracao__ativa=True,
    ).select_related('integracao')

    if not pis.exists():
        return

    ml = MercadoLivreService()
    for pi in pis:
        if not pi.sku_externo:
            continue
        try:
            ml.pause_listing(pi.integracao, pi.sku_externo)
            logger.info('ML listing paused on product delete: %s', pi.sku_externo)
        except Exception as exc:
            logger.error('ML pause on delete error for %s: %s', pi.sku_externo, exc)


@receiver(pre_delete, sender='integracoes.ProdutoIntegracao')
def produto_integracao_pre_delete_ml(sender, instance, **kwargs):
    """
    Antes de remover o vínculo produto↔integração: pausa o anúncio no ML.
    Garante que o item não fique ativo sem um dono no sistema.
    """
    if instance.integracao.plataforma != 'ML':
        return
    if not instance.sku_externo:
        return
    if not instance.integracao.ativa:
        return

    try:
        from integracoes.services.mercadolivre import MercadoLivreService
        ml = MercadoLivreService()
        ok = ml.pause_listing(instance.integracao, instance.sku_externo)
        if ok:
            logger.info(
                'ML listing paused on integracao delete: sku=%s produto=%s',
                instance.sku_externo,
                instance.produto_id,
            )
        else:
            logger.warning(
                'ML listing pause falhou ao remover vínculo: sku=%s',
                instance.sku_externo,
            )
    except Exception as exc:
        logger.error(
            'ML pause on ProdutoIntegracao delete error: sku=%s exc=%s',
            instance.sku_externo,
            exc,
        )
