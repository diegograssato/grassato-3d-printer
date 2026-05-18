from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from .models import Venda


@receiver(post_save, sender=Venda)
def venda_post_save(sender, instance, created, **kwargs):
    """Ao registrar uma venda: decrementa estoque do produto e cria lançamento no caixa.
    O filamento já foi consumido no momento da fabricação (via estoque.signals)."""
    if not created:
        return

    # Decrementa estoque do produto
    produto = instance.produto
    produto.estoque_quantidade -= instance.quantidade
    produto.save(update_fields=['estoque_quantidade'])

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
    """Ao excluir uma venda: reverte estoque do produto."""
    produto = instance.produto
    produto.estoque_quantidade += instance.quantidade
    produto.save(update_fields=['estoque_quantidade'])
