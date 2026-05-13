from django.urls import path
from . import views

app_name = 'caixa'

urlpatterns = [
    path('', views.caixa_list, name='caixa_list'),
    path('nova/', views.movimentacao_create, name='movimentacao_create'),
    path('<int:pk>/excluir/', views.movimentacao_delete, name='movimentacao_delete'),
]
