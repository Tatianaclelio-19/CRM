from django.urls import path
from . import views

urlpatterns = [
    path('', views.listar_clientes, name='listar_clientes'),
    path('novo/', views.criar_cliente, name='criar_cliente'),
    path('editar/<int:pk>/', views.editar_cliente, name='editar_cliente'),
    path('detalhe/<int:pk>/', views.detalhe_cliente, name='detalhe_cliente'),
    path('interacao/concluir/<int:pk>/', views.concluir_interacao, name='concluir_interacao'),
    path('importar-excel/', views.importar_clientes_excel, name='importar_clientes_excel'),
    path('<int:pk>/comunicar/', views.enviar_comunicacao_cliente, name='enviar_comunicacao_cliente'),
    path('campanha-lote/', views.enviar_campanha_lote, name='enviar_campanha_lote'),
    path('<int:pk>/whatsapp-rapido/', views.atalho_whatsapp_rapido, name='atalho_whatsapp_rapido'),
    path('optout/<str:token>/', views.cancelar_consentimento_rgpd, name='cancelar_consentimento_rgpd'),
    path('campanha-whatsapp/', views.preparar_campanha_whatsapp, name='preparar_campanha_whatsapp'),
    path('cliente/<int:pk>/apagar-rgpd/', views.apagar_dados_cliente_rgpd, name='apagar_dados_cliente_rgpd'),
]