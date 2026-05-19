from django.urls import path

from . import views

app_name = 'auditoria'

urlpatterns = [
    path('', views.log_list, name='log_list'),
    path('<int:pk>/json/', views.log_detail, name='log_detail'),
]
