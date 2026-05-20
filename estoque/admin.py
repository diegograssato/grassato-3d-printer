from django.contrib import admin
from .models import Filamento, Produto, ProdutoFilamento


@admin.register(Filamento)
class FilamentoAdmin(admin.ModelAdmin):
    list_display = ['nome', 'material', 'cor', 'peso_total_g', 'peso_disponivel_g', 'percentual_disponivel', 'preco_por_kg']
    list_filter = ['material']
    search_fields = ['nome', 'cor', 'fornecedor']
    readonly_fields = ['criado_em', 'atualizado_em']


class ProdutoFilamentoInline(admin.TabularInline):
    model = ProdutoFilamento
    extra = 0
    min_num = 1
    max_num = 4
    fields = ['filamento', 'peso_filamento_g', 'comprimento_filamento_m']


@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ['nome', 'preco_venda', 'preco_custo', 'estoque_quantidade', 'ativo']
    list_filter = ['ativo']
    search_fields = ['nome', 'descricao']
    readonly_fields = ['criado_em', 'atualizado_em']
    inlines = [ProdutoFilamentoInline]
