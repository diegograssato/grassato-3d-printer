from django.contrib import admin
from .models import MovimentacaoCaixa


@admin.register(MovimentacaoCaixa)
class MovimentacaoCaixaAdmin(admin.ModelAdmin):
    list_display = ['data', 'tipo', 'categoria', 'descricao', 'valor', 'venda']
    list_filter = ['tipo', 'categoria', 'data']
    search_fields = ['descricao']
    readonly_fields = ['venda', 'criado_em']
    date_hierarchy = 'data'
