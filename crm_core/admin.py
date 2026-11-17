from django.contrib import admin
from .models import Cliente, Interacao, Negocio

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nome_completo', 'telefone_principal', 'email_principal', 'qualificacao', 'data_criacao', 'is_ativo')
    search_fields = ('nome_completo', 'telefone_principal', 'email_principal', 'nif')
    list_filter = ('qualificacao', 'is_ativo', 'consentimento_marketing', 'data_criacao')
    
    fieldsets = (
        ('Etapa 1: Dados Pessoais e de Contacto', {
            'fields': (
                'nome_completo', 'morada', 'codigo_postal',
                'telefone_principal', 'telefone_secundario',
                'email_principal', 'email_secundario',
                'data_nascimento'
            )
        }),
        ('Etapa 1: Interesse e Qualificação Comercial', {
            'fields': (
                'area_interesse', 'tipo_imovel', 'qualificacao', 'origem_contacto'
            )
        }),
        ('Etapa 2: Identificação para Fins Legais', {
            'fields': (
                'tipo_documento', 'data_validade_documento', 'naturalidade',
                'profissao', 'nif', 'estado_civil', 'filhos',
                'observacoes'
            )
        }),
        ('Conformidade RGPD e Estado', {
            'fields': ('consentimento_marketing', 'is_ativo')
        }),
    )

@admin.register(Interacao)
class InteracaoAdmin(admin.ModelAdmin):
    list_display = ('cliente', 'tipo', 'data_interacao', 'resumo', 'data_proximo_contacto', 'concluido')
    list_filter = ('tipo', 'concluido', 'data_interacao')
    search_fields = ('cliente__nome_completo', 'resumo', 'detalhes')

@admin.register(Negocio)
class NegocioAdmin(admin.ModelAdmin):
    list_display = ('cliente', 'tipo_negocio', 'referencia_imovel', 'valor', 'estado', 'data_registo')
    list_filter = ('tipo_negocio', 'estado', 'data_registo')
    search_fields = ('cliente__nome_completo', 'referencia_imovel', 'morada_imovel')