from django.contrib import admin
from .models import Integracao, ProdutoIntegracao


@admin.register(Integracao)
class IntegracaoAdmin(admin.ModelAdmin):
    list_display = ['nome', 'plataforma', 'ativa', 'autorizada', 'ml_user_id', 'criado_em']
    list_filter = ['plataforma', 'ativa']
    readonly_fields = ['access_token', 'refresh_token', 'token_expires_at', 'ml_user_id', 'criado_em', 'atualizado_em']

    def autorizada(self, obj):
        return obj.autorizada
    autorizada.boolean = True


@admin.register(ProdutoIntegracao)
class ProdutoIntegracaoAdmin(admin.ModelAdmin):
    list_display = ['produto', 'integracao', 'sku_externo', 'status_externo', 'sincronizado_em']
    list_filter = ['integracao__plataforma', 'status_externo']
    readonly_fields = ['sincronizado_em']
