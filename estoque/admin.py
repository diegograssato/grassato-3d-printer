from django.contrib import admin
from .models import Filamento, Produto


@admin.register(Filamento)
class FilamentoAdmin(admin.ModelAdmin):
    list_display = ['nome', 'material', 'cor', 'peso_total_g', 'peso_disponivel_g', 'percentual_disponivel', 'preco_por_kg']
    list_filter = ['material']
    search_fields = ['nome', 'cor', 'fornecedor']
    readonly_fields = ['criado_em', 'atualizado_em']


@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ['nome', 'filamento', 'preco_venda', 'preco_custo', 'estoque_quantidade', 'ativo']
    list_filter = ['ativo', 'filamento__material']
    search_fields = ['nome', 'descricao']
    readonly_fields = ['criado_em', 'atualizado_em']
