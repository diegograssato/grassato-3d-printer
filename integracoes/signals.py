"""
Signals do app integracoes:
- pre_save em Produto  → detecta mudanças de nome/preço para sincronizar no ML
- post_save em Produto → sincroniza estoque/status/nome/preço no ML
- pre_delete em Produto → pausa anúncio no ML antes de excluir
"""
import logging

from django.db.models.signals import post_save, pre_delete, pre_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(pre_save, sender='estoque.Produto')
def produto_pre_save_track_ml(sender, instance, **kwargs):
    """
    Rastreia mudanças de nome e preço antes do save.
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
            instance._ml_changed_fields['title'] = instance.nome
        if old.preco_venda != instance.preco_venda:
            instance._ml_changed_fields['price'] = float(instance.preco_venda)
    except sender.DoesNotExist:
        pass


@receiver(post_save, sender='estoque.Produto')
def produto_post_save_ml(sender, instance, **kwargs):
    """
    Sincroniza com o ML após salvar um produto:
    - estoque = 0 → pausa o anúncio
    - estoque > 0 e estava pausado → reativa + atualiza quantidade
    - estoque > 0 e ativo → atualiza quantidade
    - nome ou preço mudou → atualiza título/preço no anúncio
    """
    if getattr(instance, '_skip_integracoes_signal', False):
        return

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
    qtd = instance.estoque_quantidade
    changed = getattr(instance, '_ml_changed_fields', {})

    for pi in pis:
        if not pi.sku_externo:
            continue
        try:
            # ── Estoque / status ─────────────────────────────────────────────
            if qtd <= 0:
                ok = ml.pause_listing(pi.integracao, pi.sku_externo)
                if ok and pi.status_externo != 'paused':
                    pi.status_externo = 'paused'
                    pi.save(update_fields=['status_externo'])
                    logger.info('ML listing paused: %s (estoque zero)', pi.sku_externo)
            elif pi.status_externo == 'paused':
                ml.activate_listing(pi.integracao, pi.sku_externo)
                ml.update_stock(pi.integracao, pi.sku_externo, qtd)
                pi.status_externo = 'active'
                pi.save(update_fields=['status_externo'])
                logger.info('ML listing reactivated: %s (estoque=%d)', pi.sku_externo, qtd)
            else:
                ml.update_stock(pi.integracao, pi.sku_externo, qtd)
                logger.debug('ML stock updated: %s → %d', pi.sku_externo, qtd)

            # ── Nome / preço ─────────────────────────────────────────────────
            if changed:
                ok = ml.update_listing(pi.integracao, pi.sku_externo, changed)
                if ok:
                    logger.info('ML listing updated %s: %s', pi.sku_externo, list(changed.keys()))
                else:
                    logger.warning('ML listing update failed %s: %s', pi.sku_externo, changed)

        except Exception as exc:
            logger.error('ML sync error for %s: %s', pi.sku_externo, exc)


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
