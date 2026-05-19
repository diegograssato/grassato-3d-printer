from django.urls import path
from . import views

app_name = 'importexport'

urlpatterns = [
    path('', views.index, name='index'),
    path('exportar/', views.exportar, name='exportar'),
    path('importar/', views.importar, name='importar'),
]
