from django.contrib import admin
from .models import Venda


@admin.register(Venda)
class VendaAdmin(admin.ModelAdmin):
    list_display = ['pk', 'data', 'produto', 'quantidade', 'preco_unitario', 'total', 'forma_pagamento']
    list_filter = ['forma_pagamento', 'data']
    search_fields = ['produto__nome', 'observacoes']
    readonly_fields = ['total', 'criado_em']
    date_hierarchy = 'data'
