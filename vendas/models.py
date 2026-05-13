from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
from django.utils import timezone


class Venda(models.Model):
    FORMA_PAGAMENTO = [
        ('DINHEIRO', 'Dinheiro'),
        ('PIX', 'PIX'),
        ('CARTAO_CREDITO', 'Cartão de Crédito'),
        ('CARTAO_DEBITO', 'Cartão de Débito'),
        ('TRANSFERENCIA', 'Transferência'),
    ]

    data = models.DateField('Data', default=timezone.now)
    produto = models.ForeignKey(
        'estoque.Produto', on_delete=models.PROTECT,
        related_name='vendas', verbose_name='Produto'
    )
    quantidade = models.IntegerField(
        'Quantidade', validators=[MinValueValidator(1)], default=1
    )
    preco_unitario = models.DecimalField(
        'Preço unitário (R$)', max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    total = models.DecimalField(
        'Total (R$)', max_digits=10, decimal_places=2,
        editable=False, default=Decimal('0')
    )
    forma_pagamento = models.CharField(
        'Forma de pagamento', max_length=20,
        choices=FORMA_PAGAMENTO, default='PIX'
    )
    observacoes = models.TextField('Observações', blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Venda'
        verbose_name_plural = 'Vendas'
        ordering = ['-data', '-criado_em']

    def __str__(self):
        return f'Venda #{self.pk} — {self.produto.nome} x{self.quantidade}'

    def save(self, *args, **kwargs):
        self.total = self.preco_unitario * Decimal(str(self.quantidade))
        super().save(*args, **kwargs)
