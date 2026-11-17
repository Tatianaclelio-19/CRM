from django.db import models
from django.utils import timezone
from encrypted_model_fields.fields import EncryptedCharField

class Cliente(models.Model):
    # ==========================================
    # ETAPA 1: Dados Pessoais e de Contacto
    # ==========================================
    nome_completo = models.CharField(max_length=150, verbose_name="Nome Completo")
    morada = models.CharField(max_length=255, blank=True, null=True, verbose_name="Morada")
    codigo_postal = models.CharField(max_length=20, blank=True, null=True, verbose_name="Código Postal")
    
    telefone_principal = models.CharField(max_length=20, verbose_name="Telefone Principal")
    telefone_secundario = models.CharField(max_length=20, blank=True, null=True, verbose_name="Telefone Secundário")
    
    email_principal = models.EmailField(verbose_name="E-mail Principal")
    email_secundario = models.EmailField(blank=True, null=True, verbose_name="E-mail Secundário")
    
    data_nascimento = models.DateField(null=True, blank=True, verbose_name="Data de Nascimento")
    
    area_interesse = models.CharField(max_length=100, blank=True, null=True, verbose_name="Área de Interesse")
    tipo_imovel = models.CharField(max_length=100, blank=True, null=True, verbose_name="Tipo de Imóvel")
    qualificacao = models.CharField(max_length=50, blank=True, null=True, verbose_name="Qualificação")
    origem_contacto = models.CharField(max_length=50, default="Outro", verbose_name="Origem do Contacto")

    # ==========================================
    # ETAPA 2: Identificação para Fins Legais (Encriptados)
    # ==========================================
    tipo_documento = EncryptedCharField(max_length=100, blank=True, null=True, verbose_name="Tipo de Documento")
    nif = EncryptedCharField(max_length=20, blank=True, null=True, verbose_name="NIF")
    
    data_validade_documento = models.DateField(null=True, blank=True, verbose_name="Validade do Documento")
    naturalidade = models.CharField(max_length=100, blank=True, null=True, verbose_name="Naturalidade")
    profissao = models.CharField(max_length=100, blank=True, null=True, verbose_name="Profissão")
    estado_civil = models.CharField(max_length=50, blank=True, null=True, verbose_name="Estado Civil")
    filhos = models.CharField(max_length=100, blank=True, null=True, verbose_name="Filhos")
    
    observacoes = models.TextField(blank=True, null=True, verbose_name="Observações")
    
    consentimento_marketing = models.BooleanField(default=False, verbose_name="Consentimento (Opt-in)")
    is_ativo = models.BooleanField(default=True, verbose_name="Ativo")
    data_criacao = models.DateTimeField(default=timezone.now, verbose_name="Data de Registo")

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ['-data_criacao']

    def __str__(self):
        return f"{self.nome_completo} ({self.telefone_principal})"


class Interacao(models.Model):
    TIPO_CHOICES = [
        ('chamada', 'Chamada Telefónica'),
        ('whatsapp', 'Mensagem WhatsApp'),
        ('email', 'E-mail'),
        ('reuniao', 'Reunião Presencial'),
        ('visita', 'Visita a Imóvel'),
        ('outro', 'Outro'),
    ]

    cliente = models.ForeignKey(
        Cliente, 
        on_delete=models.CASCADE, 
        related_name='interacoes',
        verbose_name="Cliente"
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='chamada', verbose_name="Tipo de Contacto")
    data_interacao = models.DateTimeField(auto_now_add=True, verbose_name="Data/Hora do Registo")
    resumo = models.CharField(max_length=200, verbose_name="Assunto / Resumo")
    detalhes = models.TextField(verbose_name="Notas da Conversa")
    data_proximo_contacto = models.DateField(null=True, blank=True, verbose_name="Data do Próximo Contacto (Follow-up)")
    concluido = models.BooleanField(default=False, verbose_name="Concluído?")

    class Meta:
        verbose_name = "Interação"
        verbose_name_plural = "Interações"
        ordering = ['-data_interacao']

    def __str__(self):
        return f"{self.get_tipo_display()} com {self.cliente.nome_completo} em {self.data_interacao.strftime('%d/%m/%Y')}"


class Negocio(models.Model):
    TIPO_NEGOCIO_CHOICES = [
        ('venda', 'Venda'),
        ('compra', 'Compra'),
        ('arrendamento', 'Arrendamento'),
    ]
    
    ESTADO_CHOICES = [
        ('em_curso', 'Em Curso / Negociação'),
        ('concluido', 'Fechado / Concluído'),
        ('cancelado', 'Cancelado'),
    ]

    cliente = models.ForeignKey(
        Cliente, 
        on_delete=models.CASCADE, 
        related_name='negocios',
        verbose_name="Cliente"
    )
    tipo_negocio = models.CharField(max_length=20, choices=TIPO_NEGOCIO_CHOICES, default='venda', verbose_name="Tipo de Transação")
    referencia_imovel = models.CharField(max_length=50, verbose_name="Referência do Imóvel")
    morada_imovel = models.CharField(max_length=255, verbose_name="Morada do Imóvel")
    valor = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True, verbose_name="Valor (€)")
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='em_curso', verbose_name="Estado do Negócio")
    data_registo = models.DateTimeField(auto_now_add=True, verbose_name="Data do Registo")

    class Meta:
        verbose_name = "Negócio / Imóvel Negociado"
        verbose_name_plural = "Negócios / Imóveis Negociados"
        ordering = ['-data_registo']

    def __str__(self):
        return f"{self.get_tipo_negocio_display()} - Ref: {self.referencia_imovel} ({self.cliente.nome_completo})"