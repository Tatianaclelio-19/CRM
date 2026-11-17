from django import forms
from .models import Cliente, Interacao, Negocio

QUALIFICACAO_CHOICES = [
    ('', 'Selecione a qualificação...'),
    ('Comprador', 'Comprador'),
    ('Vendedor', 'Vendedor'),
    ('Proprietário / Senhorio', 'Proprietário / Senhorio'),
    ('Arrendatário', 'Arrendatário'),
    ('Investidor', 'Investidor'),
    ('Lead / Potencial Cliente', 'Lead / Potencial Cliente'),
]

class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = [
            # Etapa 1: Dados Pessoais e de Interesse
            'nome_completo', 'morada', 'codigo_postal',
            'telefone_principal', 'telefone_secundario',
            'email_principal', 'email_secundario',
            'data_nascimento', 'area_interesse', 'tipo_imovel',
            'qualificacao', 'origem_contacto',
            
            # Etapa 2: Identificação para Fins Legais (sem os campos estáticos de negócios)
            'tipo_documento', 'data_validade_documento', 'naturalidade',
            'profissao', 'nif', 'estado_civil', 'filhos',
            'observacoes', 'consentimento_marketing'
        ]
        widgets = {
            'nome_completo': forms.TextInput(attrs={'class': 'form-control'}),
            'morada': forms.TextInput(attrs={'class': 'form-control'}),
            'codigo_postal': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex.: 1000-001'}),
            'telefone_principal': forms.TextInput(attrs={'class': 'form-control'}),
            'telefone_secundario': forms.TextInput(attrs={'class': 'form-control'}),
            'email_principal': forms.EmailInput(attrs={'class': 'form-control'}),
            'email_secundario': forms.EmailInput(attrs={'class': 'form-control'}),
            'data_nascimento': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'area_interesse': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex.: Freguesia, Concelho, Distrito'}),
            'tipo_imovel': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex.: T2, Moradia'}),
            'qualificacao': forms.Select(choices=QUALIFICACAO_CHOICES, attrs={'class': 'form-select'}),
            'origem_contacto': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo_documento': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex.: CC 12345678'}),
            'data_validade_documento': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'naturalidade': forms.TextInput(attrs={'class': 'form-control'}),
            'profissao': forms.TextInput(attrs={'class': 'form-control'}),
            'nif': forms.TextInput(attrs={'class': 'form-control'}),
            'estado_civil': forms.TextInput(attrs={'class': 'form-control'}),
            'filhos': forms.TextInput(attrs={'class': 'form-control'}),
            
            'observacoes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'consentimento_marketing': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class InteracaoForm(forms.ModelForm):
    class Meta:
        model = Interacao
        fields = ['tipo', 'resumo', 'detalhes', 'data_proximo_contacto']
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'resumo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex.: Apresentação de imóveis T2'}),
            'detalhes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Notas pormenorizadas da conversa...'}),
            'data_proximo_contacto': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }


class NegocioForm(forms.ModelForm):
    class Meta:
        model = Negocio
        fields = ['tipo_negocio', 'referencia_imovel', 'morada_imovel', 'valor', 'estado']
        widgets = {
            'tipo_negocio': forms.Select(attrs={'class': 'form-select'}),
            'referencia_imovel': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex.: REF-1023'}),
            'morada_imovel': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex.: Rua das Flores, nº 10'}),
            'valor': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ex.: 250000'}),
            'estado': forms.Select(attrs={'class': 'form-select'}),
        }