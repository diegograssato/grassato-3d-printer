from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from decimal import Decimal
from .models import Produto, Filamento


@receiver(pre_save, sender=Produto)
def produto_pre_save(sender, instance, **kwargs):
    """Armazena estado anterior do produto para ajuste do filamento."""
    if instance.pk:
        try:
            old = Produto.objects.get(pk=instance.pk)
            instance._old_filamento_id = old.filamento_id
            instance._old_peso_filamento_g = old.peso_filamento_g
            instance._old_estoque_quantidade = old.estoque_quantidade
            instance._old_ativo = old.ativo
        except Produto.DoesNotExist:
            instance._old_filamento_id = None
            instance._old_peso_filamento_g = Decimal('0')
            instance._old_estoque_quantidade = 0
            instance._old_ativo = True
    else:
        instance._old_filamento_id = None
        instance._old_peso_filamento_g = Decimal('0')
        instance._old_estoque_quantidade = 0
        instance._old_ativo = True


@receiver(post_save, sender=Produto)
def produto_post_save(sender, instance, created, **kwargs):
    """Ao criar/alterar produto, ajusta peso_disponivel_g do(s) filamento(s)."""
    if created:
        # Produto novo: decrementa filamento pelo estoque inicial impresso
        if instance.estoque_quantidade > 0:
            filamento = instance.filamento
            peso_consumido = instance.peso_filamento_g * Decimal(str(instance.estoque_quantidade))
            filamento.peso_disponivel_g = max(
                Decimal('0'),
                filamento.peso_disponivel_g - peso_consumido,
            )
            filamento.save(update_fields=['peso_disponivel_g'])
        return

    old_fil_id = getattr(instance, '_old_filamento_id', None)
    old_peso = getattr(instance, '_old_peso_filamento_g', Decimal('0'))
    old_estoque = getattr(instance, '_old_estoque_quantidade', 0)
    old_ativo = getattr(instance, '_old_ativo', True)

    if old_fil_id is None:
        return

    # Produto desativado: devolve ao filamento o material em estoque
    if old_ativo and not instance.ativo:
        try:
            filamento = Filamento.objects.get(pk=old_fil_id)
            peso_devolvido = old_peso * Decimal(str(old_estoque))
            filamento.peso_disponivel_g = min(
                filamento.peso_total_g,
                filamento.peso_disponivel_g + peso_devolvido,
            )
            filamento.save(update_fields=['peso_disponivel_g'])
        except Filamento.DoesNotExist:
            pass
        return

    # Produto reativado: decrementa o filamento novamente
    if not old_ativo and instance.ativo:
        filamento = instance.filamento
        peso_consumido = instance.peso_filamento_g * Decimal(str(instance.estoque_quantidade))
        filamento.peso_disponivel_g = max(
            Decimal('0'),
            filamento.peso_disponivel_g - peso_consumido,
        )
        filamento.save(update_fields=['peso_disponivel_g'])
        return

    # Produto ativo atualizado
    if old_fil_id != instance.filamento_id:
        # Filamento trocado: restaura o antigo, decrementa o novo
        try:
            old_filamento = Filamento.objects.get(pk=old_fil_id)
            peso_devolvido = old_peso * Decimal(str(old_estoque))
            old_filamento.peso_disponivel_g = min(
                old_filamento.peso_total_g,
                old_filamento.peso_disponivel_g + peso_devolvido,
            )
            old_filamento.save(update_fields=['peso_disponivel_g'])
        except Filamento.DoesNotExist:
            pass

        new_filamento = instance.filamento
        peso_consumido = instance.peso_filamento_g * Decimal(str(instance.estoque_quantidade))
        new_filamento.peso_disponivel_g = max(
            Decimal('0'),
            new_filamento.peso_disponivel_g - peso_consumido,
        )
        new_filamento.save(update_fields=['peso_disponivel_g'])
    else:
        # Mesmo filamento: ajusta o delta (diferença de consumo)
        peso_anterior = old_peso * Decimal(str(old_estoque))
        peso_atual = instance.peso_filamento_g * Decimal(str(instance.estoque_quantidade))
        delta = peso_atual - peso_anterior
        if delta != Decimal('0'):
            filamento = instance.filamento
            filamento.peso_disponivel_g = max(
                Decimal('0'),
                min(filamento.peso_total_g, filamento.peso_disponivel_g - delta),
            )
            filamento.save(update_fields=['peso_disponivel_g'])
