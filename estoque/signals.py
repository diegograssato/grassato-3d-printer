from django.db.models.signals import pre_save, post_save, pre_delete
from django.dispatch import receiver
from decimal import Decimal
from .models import Produto, Filamento, ProdutoFilamento


# ──────────────────────────────────────────────────────────────
# Produto — rastreamento de estado anterior
# ──────────────────────────────────────────────────────────────

@receiver(pre_save, sender=Produto)
def produto_pre_save(sender, instance, **kwargs):
    """Armazena estado anterior do produto para ajustes de estoque."""
    if instance.pk:
        try:
            old = Produto.objects.get(pk=instance.pk)
            instance._old_estoque_quantidade = old.estoque_quantidade
            instance._old_ativo = old.ativo
        except Produto.DoesNotExist:
            instance._old_estoque_quantidade = 0
            instance._old_ativo = True
    else:
        instance._old_estoque_quantidade = 0
        instance._old_ativo = True


@receiver(post_save, sender=Produto)
def produto_post_save(sender, instance, created, **kwargs):
    """
    Trata mudanças de ativo e estoque_quantidade no Produto.
    A criação/remoção de filamentos é tratada pelos signals de ProdutoFilamento.
    """
    if created:
        # Novo produto: os filamentos ainda não existem (formset salvo depois).
        # O decremento será feito em produto_filamento_post_save.
        return

    old_ativo = getattr(instance, '_old_ativo', True)
    old_estoque = getattr(instance, '_old_estoque_quantidade', 0)

    ativo_mudou = old_ativo != instance.ativo
    estoque_mudou = old_estoque != instance.estoque_quantidade

    if ativo_mudou:
        if old_ativo and not instance.ativo:
            # Produto desativado → restaura filamentos com base no estoque antigo
            _ajustar_todos_filamentos(instance, sinal=+1, estoque_qty=old_estoque)
        elif not old_ativo and instance.ativo:
            # Produto reativado → consome filamentos com o estoque atual
            _ajustar_todos_filamentos(instance, sinal=-1, estoque_qty=instance.estoque_quantidade)
        # Quando ativo muda, não processa mais o delta de estoque
        return

    # Produto permanece ativo com quantidade alterada → ajusta delta
    if instance.ativo and estoque_mudou:
        delta = Decimal(str(instance.estoque_quantidade - old_estoque))
        if delta:
            _ajustar_todos_filamentos(instance, sinal=-1, estoque_qty=delta)


def _ajustar_todos_filamentos(produto, sinal: int, estoque_qty):
    """
    Itera sobre todos os ProdutoFilamento e aplica o ajuste de sinal
    (sinal=-1 decrementa, sinal=+1 restaura) multiplicado por estoque_qty.
    """
    qty = Decimal(str(estoque_qty))
    for pf in produto.filamentos_produto.select_related('filamento').all():
        f = pf.filamento
        ajuste = pf.peso_filamento_g * qty * sinal
        if sinal < 0:
            f.peso_disponivel_g = max(Decimal('0'), f.peso_disponivel_g + ajuste)
        else:
            f.peso_disponivel_g = min(f.peso_total_g, f.peso_disponivel_g + ajuste)
        f.save(update_fields=['peso_disponivel_g'])


# ──────────────────────────────────────────────────────────────
# ProdutoFilamento — adição, alteração e remoção de filamentos
# ──────────────────────────────────────────────────────────────

@receiver(pre_save, sender=ProdutoFilamento)
def produto_filamento_pre_save(sender, instance, **kwargs):
    """Armazena estado anterior do ProdutoFilamento para ajustes."""
    if instance.pk:
        try:
            old = ProdutoFilamento.objects.get(pk=instance.pk)
            instance._old_filamento_id = old.filamento_id
            instance._old_peso_filamento_g = old.peso_filamento_g
        except ProdutoFilamento.DoesNotExist:
            instance._old_filamento_id = None
            instance._old_peso_filamento_g = Decimal('0')
    else:
        instance._old_filamento_id = None
        instance._old_peso_filamento_g = Decimal('0')


@receiver(post_save, sender=ProdutoFilamento)
def produto_filamento_post_save(sender, instance, created, **kwargs):
    """
    Ao criar/alterar um ProdutoFilamento, ajusta o peso_disponivel_g do(s) filamento(s).
    Só opera se o produto estiver ativo e com estoque > 0.
    """
    produto = instance.produto
    if not produto.ativo or produto.estoque_quantidade == 0:
        return

    estoque = Decimal(str(produto.estoque_quantidade))

    if created:
        # Novo filamento adicionado ao produto: decrementa
        f = instance.filamento
        f.peso_disponivel_g = max(
            Decimal('0'),
            f.peso_disponivel_g - instance.peso_filamento_g * estoque,
        )
        f.save(update_fields=['peso_disponivel_g'])
        return

    old_fil_id = getattr(instance, '_old_filamento_id', None)
    old_peso = getattr(instance, '_old_peso_filamento_g', Decimal('0'))

    if old_fil_id is None:
        return

    if old_fil_id != instance.filamento_id:
        # Filamento trocado: restaura o antigo, decrementa o novo
        try:
            old_f = Filamento.objects.get(pk=old_fil_id)
            old_f.peso_disponivel_g = min(
                old_f.peso_total_g,
                old_f.peso_disponivel_g + old_peso * estoque,
            )
            old_f.save(update_fields=['peso_disponivel_g'])
        except Filamento.DoesNotExist:
            pass

        new_f = instance.filamento
        new_f.peso_disponivel_g = max(
            Decimal('0'),
            new_f.peso_disponivel_g - instance.peso_filamento_g * estoque,
        )
        new_f.save(update_fields=['peso_disponivel_g'])
    else:
        # Mesmo filamento: ajusta delta de peso
        delta = (instance.peso_filamento_g - old_peso) * estoque
        if delta:
            f = instance.filamento
            f.peso_disponivel_g = max(
                Decimal('0'),
                min(f.peso_total_g, f.peso_disponivel_g - delta),
            )
            f.save(update_fields=['peso_disponivel_g'])


@receiver(pre_delete, sender=ProdutoFilamento)
def produto_filamento_pre_delete(sender, instance, **kwargs):
    """
    Ao remover um filamento do produto, restaura o estoque do filamento
    correspondente (apenas se o produto estiver ativo e com estoque > 0).
    """
    produto = instance.produto
    if not produto.ativo or produto.estoque_quantidade == 0:
        return

    estoque = Decimal(str(produto.estoque_quantidade))
    f = instance.filamento
    f.peso_disponivel_g = min(
        f.peso_total_g,
        f.peso_disponivel_g + instance.peso_filamento_g * estoque,
    )
    f.save(update_fields=['peso_disponivel_g'])
