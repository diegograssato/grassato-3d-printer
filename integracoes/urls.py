from django.urls import path
from . import views

app_name = 'integracoes'

urlpatterns = [
    # ── Integrações CRUD ──────────────────────────────────────────────────────
    path('', views.integracao_list, name='integracao_list'),
    path('nova/', views.integracao_create, name='integracao_create'),
    path('<int:pk>/editar/', views.integracao_update, name='integracao_update'),
    path('<int:pk>/excluir/', views.integracao_delete, name='integracao_delete'),

    # ── OAuth MercadoLivre ────────────────────────────────────────────────────
    path('<int:pk>/ml/autorizar/', views.ml_authorize, name='ml_authorize'),
    path('ml/callback/', views.ml_callback, name='ml_callback'),

    # ── Produto ↔ Integração ──────────────────────────────────────────────────
    path('produto/<int:produto_pk>/vincular/', views.produto_integracao_create, name='produto_integracao_create'),
    path('produto-integracao/<int:pk>/sync/', views.produto_integracao_sync, name='produto_integracao_sync'),
    path('produto-integracao/<int:pk>/remover/', views.produto_integracao_delete, name='produto_integracao_delete'),

    # ── Categorias ML ─────────────────────────────────────────────────────────
    path('ml/categorias/', views.ml_categorias, name='ml_categorias'),
    path('ml/categorias/busca/', views.ml_categorias_busca_json, name='ml_categorias_busca'),
    path('ml/category-attributes/', views.ml_category_attributes, name='ml_category_attributes'),

    # ── Webhook público (sem login) ───────────────────────────────────────────
    path('ml/notificacao/', views.ml_notificacao, name='ml_notificacao'),
]
