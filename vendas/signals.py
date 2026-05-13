from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from decimal import Decimal
from .models import Venda


@receiver(post_save, sender=Venda)
def venda_post_save(sender, instance, created, **kwargs):
    """Ao registrar uma venda: decrementa estoque do produto e do filamento,
    e cria lançamento automático no caixa."""
    if not created:
        return

    # Decrementa estoque do produto
    produto = instance.produto
    produto.estoque_quantidade -= instance.quantidade
    produto.save(update_fields=['estoque_quantidade'])

    # Decrementa peso disponível do filamento
    filamento = produto.filamento
    peso_consumido = produto.peso_filamento_g * Decimal(str(instance.quantidade))
    filamento.peso_disponivel_g = max(
        Decimal('0'),
        filamento.peso_disponivel_g - peso_consumido
    )
    filamento.save(update_fields=['peso_disponivel_g'])

    # Cria entrada automática no caixa
    from caixa.models import MovimentacaoCaixa
    MovimentacaoCaixa.objects.create(
        data=instance.data,
        tipo='ENTRADA',
        categoria='VENDA',
        descricao=f'Venda: {instance.produto.nome} x{instance.quantidade}',
        valor=instance.total,
        venda=instance,
    )


@receiver(pre_delete, sender=Venda)
def venda_pre_delete(sender, instance, **kwargs):
    """Ao excluir uma venda: reverte estoque do produto e do filamento."""
    produto = instance.produto
    produto.estoque_quantidade += instance.quantidade
    produto.save(update_fields=['estoque_quantidade'])

    filamento = produto.filamento
    peso_devolvido = produto.peso_filamento_g * Decimal(str(instance.quantidade))
    filamento.peso_disponivel_g = min(
        filamento.peso_total_g,
        filamento.peso_disponivel_g + peso_devolvido
    )
    filamento.save(update_fields=['peso_disponivel_g'])
