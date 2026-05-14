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
]
