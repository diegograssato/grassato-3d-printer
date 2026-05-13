from django.urls import path
from . import views

app_name = 'vendas'

urlpatterns = [
    path('', views.venda_list, name='venda_list'),
    path('nova/', views.venda_create, name='venda_create'),
    path('<int:pk>/excluir/', views.venda_delete, name='venda_delete'),
]
