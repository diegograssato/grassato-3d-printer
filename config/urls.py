from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', include('dashboard.urls')),
    path('estoque/', include('estoque.urls')),
    path('vendas/', include('vendas.urls')),
    path('caixa/', include('caixa.urls')),
    path('integracoes/', include('integracoes.urls')),
    path('importexport/', include('importexport.urls')),
    path('auditoria/', include('auditoria.urls')),
]

# Serve arquivos de mídia localmente em qualquer ambiente
# (em produção o nginx serve /media/ diretamente)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
