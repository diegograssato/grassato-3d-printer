from django.urls import path
from . import views

app_name = 'estoque'

urlpatterns = [
    # Filamentos
    path('filamentos/', views.filamento_list, name='filamento_list'),
    path('filamentos/novo/', views.filamento_create, name='filamento_create'),
    path('filamentos/<int:pk>/editar/', views.filamento_update, name='filamento_update'),
    path('filamentos/<int:pk>/excluir/', views.filamento_delete, name='filamento_delete'),
    # Produtos
    path('produtos/', views.produto_list, name='produto_list'),
    path('produtos/novo/', views.produto_create, name='produto_create'),
    path('produtos/<int:pk>/editar/', views.produto_update, name='produto_update'),
    path('produtos/<int:pk>/excluir/', views.produto_delete, name='produto_delete'),
    # Fornecedores
    path('fornecedores/', views.fornecedor_list, name='fornecedor_list'),
    path('fornecedores/novo/', views.fornecedor_create, name='fornecedor_create'),
    path('fornecedores/<int:pk>/editar/', views.fornecedor_update, name='fornecedor_update'),
    path('fornecedores/<int:pk>/excluir/', views.fornecedor_delete, name='fornecedor_delete'),
    path('fornecedores/<int:pk>/uso/', views.fornecedor_uso, name='fornecedor_uso'),
    # Filamentos (uso)
    path('filamentos/<int:pk>/uso/', views.filamento_uso, name='filamento_uso'),
    # API
    path('api/produto/<int:pk>/preco/', views.produto_preco_api, name='produto_preco_api'),
]
