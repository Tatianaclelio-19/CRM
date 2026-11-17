from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q
from .models import Cliente, Interacao, Negocio
from django.utils import timezone
from .forms import ClienteForm, InteracaoForm, NegocioForm
from django.views.decorators.debug import sensitive_post_parameters
from django.contrib.auth.decorators import login_required
import openpyxl
from datetime import datetime, date
from django.db.models.functions import Lower
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from django.core.mail import EmailMultiAlternatives
from django.urls import reverse
from urllib.parse import quote
import time
from django.core.mail import EmailMultiAlternatives, get_connection
from django.http import JsonResponse

@login_required
@sensitive_post_parameters('nif', 'tipo_documento', 'telefone_principal', 'email_principal', 'morada')
def criar_cliente(request):
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            cliente = form.save()
            messages.success(request, f"Cliente {cliente.nome_completo} registado com sucesso!")
            return redirect('listar_clientes')
    else:
        form = ClienteForm()
        
    return render(request, 'crm_core/cliente_form.html', {'form': form})

@login_required
def listar_clientes(request):
    clientes = Cliente.objects.filter(is_ativo=True)
    hoje = timezone.now().date()
    
    q = request.GET.get('q', '').strip()
    qualificacao = request.GET.get('qualificacao', '').strip()
    interesse = request.GET.get('interesse', '').strip()
    mes_aniversario = request.GET.get('mes_aniversario', '').strip()
    mes_validade = request.GET.get('mes_validade', '').strip()
    ano_validade = request.GET.get('ano_validade', '').strip()
    ordem = request.GET.get('ordem', 'nome_asc').strip()

    if q:
        clientes = clientes.filter(nome_completo__icontains=q)
    if qualificacao:
        clientes = clientes.filter(qualificacao__icontains=qualificacao)
    if interesse:
        clientes = clientes.filter(area_interesse__icontains=interesse)
        
    # 1. Filtro de Aniversariantes do Mês
    if mes_aniversario and mes_aniversario.isdigit():
        clientes = clientes.filter(data_nascimento__month=int(mes_aniversario))

    # 2. Filtro de Validade do Documento (Mês + Ano/Estado + Com Negócio)
    if mes_validade or ano_validade:
        clientes = clientes.filter(
            negocios__isnull=False
        ).exclude(
            Q(tipo_documento__isnull=True) | Q(tipo_documento='')
        )
        
        if mes_validade and mes_validade.isdigit():
            clientes = clientes.filter(data_validade_documento__month=int(mes_validade))
            
        if ano_validade == 'expirados':
            clientes = clientes.filter(data_validade_documento__lt=hoje)
        elif ano_validade and ano_validade.isdigit():
            clientes = clientes.filter(data_validade_documento__year=int(ano_validade))
        elif mes_validade and not ano_validade:
            # Se escolheu apenas o Mês, filtra automaticamente pelo Ano Atual (ex: 2026)
            clientes = clientes.filter(data_validade_documento__year=hoje.year)
            
        clientes = clientes.distinct()

    # Lógica de ordenação estilo Excel (Padrão: Nome de A a Z)
    mapa_ordenacao = {
        'nome_asc': Lower('nome_completo').asc(),
        'nome_desc': Lower('nome_completo').desc(),
        'interesse_asc': Lower('area_interesse').asc(),
        'interesse_desc': Lower('area_interesse').desc(),
        'validade_asc': 'data_validade_documento',
        'validade_desc': '-data_validade_documento',
    }
    
    if (mes_validade or ano_validade) and 'ordem' not in request.GET:
        clientes = clientes.order_by('data_validade_documento', Lower('nome_completo'))
    elif mes_aniversario and 'ordem' not in request.GET:
        clientes = clientes.order_by('data_nascimento__day', Lower('nome_completo'))
    else:
        criterio = mapa_ordenacao.get(ordem, Lower('nome_completo').asc())
        clientes = clientes.order_by(criterio)

    # Procura os últimos 5 cancelamentos de consentimento (Opt-out) registados no Histórico
    ultimos_optouts = Interacao.objects.filter(
        cliente__consentimento_marketing=False,
        resumo__contains='Opt-out'
    ).select_related('cliente').order_by('-data_interacao')[:5]

    # Conta quantos clientes da pesquisa atual têm Opt-in RGPD e E-mail preenchido
    total_elegiveis_lote = clientes.filter(
        consentimento_marketing=True
    ).exclude(
        Q(email_principal__isnull=True) | Q(email_principal='')
    ).count()

    context = {
        'clientes': clientes,
        'hoje': hoje,
        'ano_atual': hoje.year,
        'proximo_ano': hoje.year + 1,
        'ordem_atual': ordem,
        'ultimos_optouts': ultimos_optouts,
        'total_elegiveis_lote': total_elegiveis_lote,
    }
    return render(request, 'crm_core/cliente_lista.html', context)

@login_required
@sensitive_post_parameters('nif', 'tipo_documento', 'telefone_principal', 'email_principal', 'morada')
def editar_cliente(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    
    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            messages.success(request, f"Contacto de {cliente.nome_completo} atualizado com sucesso!")
            return redirect('listar_clientes')
    else:
        form = ClienteForm(instance=cliente)
        
    return render(request, 'crm_core/cliente_form.html', {
        'form': form,
        'cliente': cliente,
        'edicao': True
    })

@login_required
def detalhe_cliente(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    interacoes = cliente.interacoes.all()
    negocios = cliente.negocios.all() # Todos os negócios associados
    
    if request.method == 'POST':
        # Verificamos qual formulário foi submetido (Interação ou Negócio)
        if 'form_tipo' in request.POST and request.POST['form_tipo'] == 'negocio':
            negocio_form = NegocioForm(request.POST)
            if negocio_form.is_valid():
                novo_negocio = negocio_form.save(commit=False)
                novo_negocio.cliente = cliente
                novo_negocio.save()
                return redirect('detalhe_cliente', pk=cliente.pk)
        else:
            # Caso contrário, assume-se que é o formulário de Interação/Follow-up
            interacao_form = InteracaoForm(request.POST)
            if interacao_form.is_valid():
                nova_interacao = interacao_form.save(commit=False)
                nova_interacao.cliente = cliente
                nova_interacao.save()
                return redirect('detalhe_cliente', pk=cliente.pk)
    else:
        interacao_form = InteracaoForm()
        negocio_form = NegocioForm()
        
    context = {
        'cliente': cliente,
        'interacoes': interacoes,
        'negocios': negocios,
        'interacao_form': interacao_form,
        'negocio_form': negocio_form,
    }
    return render(request, 'crm_core/cliente_detalhe.html', context)
def concluir_interacao(request, pk):
    interacao = get_object_or_404(Interacao, pk=pk)
    interacao.concluido = True
    interacao.save()
    messages.success(request, f"Follow-up com {interacao.cliente.nome_completo} marcado como concluído!")
    return redirect('listar_clientes')

def converter_data_excel(valor):
    if not valor:
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    valor_str = str(valor).strip()
    for formato in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y'):
        try:
            return datetime.strptime(valor_str, formato).date()
        except ValueError:
            continue
    return None

@login_required
def importar_clientes_excel(request):
    if request.method == 'POST' and request.FILES.get('ficheiro_excel'):
        ficheiro = request.FILES['ficheiro_excel']
        
        if not ficheiro.name.endswith('.xlsx'):
            messages.error(request, 'Por favor, carregue um ficheiro Excel válido (.xlsx).')
            return redirect('listar_clientes')
            
        try:
            wb = openpyxl.load_workbook(ficheiro, data_only=True)
            folha = wb.active
            
            importados = 0
            ignorados = 0
            
            for linha in folha.iter_rows(min_row=2, values_only=True):
                if not any(linha):
                    continue
                    
                # Extração das 12 Colunas (A até L)
                nome = " ".join(str(linha[0]).splitlines()).strip() if len(linha) > 0 and linha[0] else None
                data_nasc = converter_data_excel(linha[1]) if len(linha) > 1 else None
                telemovel = str(linha[2]).strip() if len(linha) > 2 and linha[2] else None
                email = "".join(str(linha[3]).splitlines()).strip() if len(linha) > 3 and linha[3] else ""
                naturalidade = str(linha[4]).strip() if len(linha) > 4 and linha[4] else ""
                validade_doc = converter_data_excel(linha[5]) if len(linha) > 5 else None
                morada_cli = str(linha[6]).strip() if len(linha) > 6 and linha[6] else ""
                cp_cli = str(linha[7]).strip() if len(linha) > 7 and linha[7] else ""
                
                ref_imovel = str(linha[8]).strip() if len(linha) > 8 and linha[8] else ""
                morada_imovel = str(linha[9]).strip() if len(linha) > 9 and linha[9] else ""
                cp_imovel = str(linha[10]).strip() if len(linha) > 10 and linha[10] else ""
                rgpd_val = str(linha[11]).strip().lower() if len(linha) > 11 and linha[11] else ""
                
                consentimento = rgpd_val in ['sim', 's', 'yes', 'true', '1', 'ativo', 'opt-in']
                
                if nome and telemovel:
                    if not Cliente.objects.filter(telefone_principal=telemovel).exists():
                        novo_cliente = Cliente.objects.create(
                            nome_completo=nome,
                            data_nascimento=data_nasc,
                            telefone_principal=telemovel,
                            email_principal=email,
                            naturalidade=naturalidade,
                            data_validade_documento=validade_doc,
                            morada=morada_cli,
                            codigo_postal=cp_cli,
                            # Se trouxe validade do documento, preenchemos indicação para ativar o filtro de validade
                            tipo_documento="Doc. Registado (Excel)" if validade_doc else None,
                            consentimento_marketing=consentimento
                        )
                        
                        # Se tiver Referência ou Morada do Imóvel (Colunas I, J, K), cria automaticamente a Transação!
                        if ref_imovel or morada_imovel:
                            morada_completa_imovel = f"{morada_imovel} ({cp_imovel})".strip() if cp_imovel else morada_imovel
                            Negocio.objects.create(
                                cliente=novo_cliente,
                                tipo_negocio='compra',
                                referencia_imovel=ref_imovel if ref_imovel else "S/ Ref",
                                morada_imovel=morada_completa_imovel,
                                estado='concluido'
                            )
                            
                        importados += 1
                    else:
                        ignorados += 1
                        
            messages.success(request, f'Importação concluída: {importados} novos clientes adicionados ({ignorados} já existiam).')
        except Exception as e:
            messages.error(request, f'Erro ao ler a planilha: verifique o formato do ficheiro.')
            
    return redirect('listar_clientes')
# --- COMUNICAÇÃO (E-MAIL HTML / WHATSAPP) E OPT-OUT RGPD ---

@login_required
def enviar_comunicacao_cliente(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk, is_ativo=True)

    # Travão de Segurança RGPD: Bloqueia marketing se não tiver Opt-in Ativo
    if not cliente.consentimento_marketing:
        messages.error(request, f"⛔ Envio bloqueado: {cliente.nome_completo} não possui consentimento RGPD ativo para comunicações.")
        return redirect('detalhe_cliente', pk=cliente.pk)

    # Gerar link único e assinado criptograficamente para Cancelar Consentimento (Opt-out)
    signer = TimestampSigner()
    token = signer.sign(str(cliente.pk))
    link_optout = request.build_absolute_uri(reverse('cancelar_consentimento_rgpd', args=[token]))

    if request.method == 'POST':
        canal = request.POST.get('canal')  # 'email' ou 'whatsapp'
        
        # 1. Limpar quebras de linha (\n ou \r) do nome, do e-mail do cliente e do assunto
        nome_limpo = " ".join(str(cliente.nome_completo).splitlines()).strip()
        email_limpo = "".join(str(cliente.email_principal or '').splitlines()).strip()
        assunto_bruto = request.POST.get('assunto', 'Novidades Imobiliárias').replace('{{ nome }}', nome_limpo)
        assunto = " ".join(assunto_bruto.splitlines()).strip()

        conteudo = request.POST.get('conteudo', '').strip()
        ficheiro_html = request.FILES.get('ficheiro_html')

        # Se a consultora anexou um ficheiro .html do Marketing, lemos o conteúdo dele
        if ficheiro_html:
            if not ficheiro_html.name.lower().endswith(('.html', '.htm')):
                messages.error(request, "Por favor, selecione um ficheiro HTML válido (.html).")
                return redirect('detalhe_cliente', pk=cliente.pk)
            try:
                conteudo = ficheiro_html.read().decode('utf-8')
            except UnicodeDecodeError:
                ficheiro_html.seek(0)
                conteudo = ficheiro_html.read().decode('latin-1')

        if not conteudo:
            messages.error(request, "Por favor, escreva uma mensagem ou anexe um template HTML do Marketing.")
            return redirect('detalhe_cliente', pk=cliente.pk)

        # Substituir variável {{ nome }} caso o template do marketing a utilize
        conteudo_personalizado = conteudo.replace('{{ nome }}', nome_limpo)

        if canal == 'email':
            if not email_limpo or '@' not in email_limpo:
                messages.error(request, "Este cliente não tem um endereço de e-mail válido registado.")
                return redirect('detalhe_cliente', pk=cliente.pk)

            # Rodapé obrigatório RGPD injetado automaticamente no final do HTML
            rodape_rgpd_html = f"""
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin-top: 30px; margin-bottom: 15px;">
            <div style="font-family: Arial, sans-serif; font-size: 12px; color: #64748b; text-align: center;">
                <p>Recebeu esta comunicação porque autorizou o envio de informações comerciais (RGPD).</p>
                <p>Se desejar deixar de receber as nossas comunicações, 
                   <a href="{link_optout}" style="color: #be123c; font-weight: bold;">clique aqui para cancelar o seu consentimento</a>.
                </p>
            </div>
            """
            corpo_html_final = f"<div>{conteudo_personalizado}</div>{rodape_rgpd_html}"
            corpo_texto_simples = f"{conteudo_personalizado}\n\n---\nPara cancelar o seu consentimento RGPD, aceda a: {link_optout}"

            # Limpar também o e-mail de resposta (Reply-To)
            email_user = "".join(str(request.user.email or '').splitlines()).strip()
            email_resposta = email_user if email_user else 'consultora@crmimobiliario.pt'

            email = EmailMultiAlternatives(
                subject=assunto,
                body=corpo_texto_simples,
                to=[email_limpo],
                reply_to=[email_resposta]
            )
            email.attach_alternative(corpo_html_final, "text/html")
            email.send()

            # Imprime o link direto e limpo no terminal para testar com 1 clique:
            print("\n" + "="*70)
            print(f"🔗 LINK DE TESTE OPT-OUT RGPD (Ctrl + Clique aqui): {link_optout}")
            print("="*70 + "\n")

            # Registar automaticamente no Histórico de Interações
            origem_msg = f" (via ficheiro {ficheiro_html.name})" if ficheiro_html else ""
            Interacao.objects.create(
                cliente=cliente,
                tipo='email',
                resumo=f"E-mail enviado: {assunto}{origem_msg}",
                detalhes="Comunicação enviada pelo CRM com suporte a resposta (Reply-To) e rodapé de opt-out RGPD incluído."
            )
            messages.success(request, f"✉️ E-mail enviado com sucesso para {nome_limpo}!")
            return redirect('detalhe_cliente', pk=cliente.pk)

        elif canal == 'whatsapp':
            if not cliente.telefone_principal:
                messages.error(request, "Este cliente não tem telefone registado.")
                return redirect('detalhe_cliente', pk=cliente.pk)

            # Limpar espaços e caracteres do número de telefone
            numero_limpo = ''.join(filter(str.isdigit, str(cliente.telefone_principal)))
            if len(numero_limpo) == 9:  # Se tiver 9 dígitos (Portugal), adiciona 351
                numero_limpo = f"351{numero_limpo}"

            texto_whatsapp = (
                f"{conteudo_personalizado}\n\n"
                f"---\n"
                f"_Caso deseje cancelar o consentimento para futuras mensagens, clique aqui:_ {link_optout}"
            )

            # Registar no Histórico que a mensagem foi gerada
            Interacao.objects.create(
                cliente=cliente,
                tipo='mensagem',
                resumo=f"WhatsApp enviado: {assunto}",
                detalhes=conteudo_personalizado
            )

            url_whatsapp = f"https://wa.me/{numero_limpo}?text={quote(texto_whatsapp)}"
            return redirect(url_whatsapp)

    return redirect('detalhe_cliente', pk=cliente.pk)

def cancelar_consentimento_rgpd(request, token):
    """Página pública (sem login) onde o cliente confirma o cancelamento do consentimento."""
    signer = TimestampSigner()
    try:
        # Token válido por 180 dias (15552000 segundos)
        cliente_id = signer.unsign(token, max_age=15552000)
        cliente = get_object_or_404(Cliente, pk=cliente_id)
    except (BadSignature, SignatureExpired):
        return render(request, 'crm_core/optout_confirmacao.html', {'erro_token': True})

    if request.method == 'POST':
        cliente.consentimento_marketing = False
        cliente.save()

        # Cria a notificação/registo automático no Histórico do Cliente!
        Interacao.objects.create(
            cliente=cliente,
            tipo='outro',
            resumo='🛑 [ALERTA RGPD] Cliente cancelou o consentimento (Opt-out)',
            detalhes='O cliente clicou no link de cancelamento de consentimento enviado numa comunicação e deixou de autorizar envios de marketing.'
        )
        return render(request, 'crm_core/optout_confirmacao.html', {'cliente': cliente, 'cancelado': True})

    return render(request, 'crm_core/optout_confirmacao.html', {'cliente': cliente, 'cancelado': False})
@login_required
def enviar_campanha_lote(request):
    """Envia e-mails personalizados em pequenos grupos (lotes) apenas para clientes com Opt-in RGPD."""
    if request.method == 'POST':
        assunto_base = request.POST.get('assunto', 'Boas Festas!').strip()
        conteudo = request.POST.get('conteudo', '').strip()
        ficheiro_html = request.FILES.get('ficheiro_html')
        tamanho_lote = int(request.POST.get('tamanho_lote', 15))

        # 1. Se anexou ficheiro .html do Marketing, lê o conteúdo dele
        if ficheiro_html:
            if not ficheiro_html.name.lower().endswith(('.html', '.htm')):
                messages.error(request, "Por favor, selecione um ficheiro HTML válido (.html).")
                return redirect('listar_clientes')
            try:
                conteudo = ficheiro_html.read().decode('utf-8')
            except UnicodeDecodeError:
                ficheiro_html.seek(0)
                conteudo = ficheiro_html.read().decode('latin-1')

        if not conteudo:
            messages.error(request, "Por favor, escreva uma mensagem ou anexe um template HTML.")
            return redirect('listar_clientes')

        # 2. Filtrar destinatários (Apenas Ativos + Com Opt-in RGPD + Com E-mail)
        clientes = Cliente.objects.filter(
            is_ativo=True,
            consentimento_marketing=True
        ).exclude(
            Q(email_principal__isnull=True) | Q(email_principal='')
        )

        # Se a consultora escolheu enviar apenas para o filtro atual do painel:
        escopo = request.POST.get('escopo', 'todos')
        if escopo == 'filtrados':
            hoje = timezone.now().date()
            q = request.POST.get('filtro_q', '').strip()
            qualificacao = request.POST.get('filtro_qualificacao', '').strip()
            interesse = request.POST.get('filtro_interesse', '').strip()
            mes_aniversario = request.POST.get('filtro_mes_aniversario', '').strip()
            mes_validade = request.POST.get('filtro_mes_validade', '').strip()
            ano_validade = request.POST.get('filtro_ano_validade', '').strip()

            if q:
                clientes = clientes.filter(nome_completo__icontains=q)
            if qualificacao:
                clientes = clientes.filter(qualificacao__icontains=qualificacao)
            if interesse:
                clientes = clientes.filter(area_interesse__icontains=interesse)
            if mes_aniversario and mes_aniversario.isdigit():
                clientes = clientes.filter(data_nascimento__month=int(mes_aniversario))
            if mes_validade or ano_validade:
                clientes = clientes.filter(negocios__isnull=False).exclude(
                    Q(tipo_documento__isnull=True) | Q(tipo_documento='')
                )
                if mes_validade and mes_validade.isdigit():
                    clientes = clientes.filter(data_validade_documento__month=int(mes_validade))
                if ano_validade == 'expirados':
                    clientes = clientes.filter(data_validade_documento__lt=hoje)
                elif ano_validade and ano_validade.isdigit():
                    clientes = clientes.filter(data_validade_documento__year=int(ano_validade))
                elif mes_validade and not ano_validade:
                    clientes = clientes.filter(data_validade_documento__year=hoje.year)
                clientes = clientes.distinct()

        lista_destinatarios = list(clientes)
        total = len(lista_destinatarios)

        if total == 0:
            messages.warning(request, "⚠️ Nenhum cliente elegível (com Opt-in RGPD ativo e e-mail) para este envio.")
            return redirect('listar_clientes')

        # 3. Disparo fracionado em pequenos grupos (Lotes) com link de Opt-out único por cliente
        signer = TimestampSigner()
        email_resposta = request.user.email if request.user.email else 'consultora@crmimobiliario.pt'
        enviados = 0
        total_grupos = (total + tamanho_lote - 1) // tamanho_lote

        connection = get_connection()
        connection.open()

        try:
            for i in range(0, total, tamanho_lote):
                lote_atual = lista_destinatarios[i:i + tamanho_lote]
                numero_grupo = (i // tamanho_lote) + 1
                print(f"\n📦 [CAMPANHA EM LOTE] A processar Grupo {numero_grupo} de {total_grupos} ({len(lote_atual)} destinatários)...")

                for cliente in lote_atual:
                    # Limpar possíveis quebras de linha (\n ou \r) vindas do Excel no nome e no e-mail
                    nome_limpo = " ".join(str(cliente.nome_completo).splitlines()).strip()
                    email_limpo = "".join(str(cliente.email_principal).splitlines()).strip()

                    if not email_limpo or '@' not in email_limpo:
                        continue

                    # Gerar token de cancelamento (Opt-out) exclusivo para este cliente
                    token = signer.sign(str(cliente.pk))
                    link_optout = request.build_absolute_uri(reverse('cancelar_consentimento_rgpd', args=[token]))

                    # Personalizar {{ nome }} no assunto e no corpo (garantindo assunto numa única linha)
                    assunto_final = " ".join(assunto_base.replace('{{ nome }}', nome_limpo).splitlines()).strip()
                    conteudo_personalizado = conteudo.replace('{{ nome }}', nome_limpo)

                    rodape_rgpd_html = f"""
                    <hr style="border: none; border-top: 1px solid #e2e8f0; margin-top: 30px; margin-bottom: 15px;">
                    <div style="font-family: Arial, sans-serif; font-size: 12px; color: #64748b; text-align: center;">
                        <p>Recebeu esta comunicação porque autorizou o envio de informações comerciais (RGPD).</p>
                        <p>Se desejar deixar de receber as nossas comunicações, 
                           <a href="{link_optout}" style="color: #be123c; font-weight: bold;">clique aqui para cancelar o seu consentimento</a>.
                        </p>
                    </div>
                    """
                    corpo_html_final = f"<div>{conteudo_personalizado}</div>{rodape_rgpd_html}"
                    corpo_texto_simples = f"{conteudo_personalizado}\n\n---\nPara cancelar o seu consentimento RGPD, aceda a: {link_optout}"

                    email = EmailMultiAlternatives(
                        subject=assunto_final,
                        body=corpo_texto_simples,
                        to=[email_limpo],
                        reply_to=[email_resposta],
                        connection=connection
                    )
                    email.attach_alternative(corpo_html_final, "text/html")
                    email.send()

                    # Registar automaticamente no Histórico individual de cada cliente
                    Interacao.objects.create(
                        cliente=cliente,
                        tipo='email',
                        resumo=f"📣 Campanha em Lote: {assunto_final}",
                        detalhes=f"Enviado no Grupo {numero_grupo}/{total_grupos} com proteção RGPD (Opt-out individual)."
                    )
                    enviados += 1

                # Se ainda houver mais grupos a seguir, faz uma pausa de 2 segundos (anti-spam)
                if i + tamanho_lote < total:
                    time.sleep(2)
        finally:
            connection.close()

        messages.success(
            request,
            f"🚀 Campanha concluída com sucesso! {enviados} e-mails personalizados enviados em {total_grupos} grupo(s) (apenas clientes com Opt-in RGPD)."
        )
        return redirect('listar_clientes')

    return redirect('listar_clientes')
@login_required
def atalho_whatsapp_rapido(request, pk):
    """Abre o WhatsApp diretamente da tabela principal com mensagem adaptada ao filtro ativo e link Opt-out RGPD."""
    cliente = get_object_or_404(Cliente, pk=pk, is_ativo=True)

    # 1. Travão de Segurança RGPD
    if not cliente.consentimento_marketing:
        messages.error(request, f"⛔ Envio bloqueado: {cliente.nome_completo} não possui consentimento RGPD ativo.")
        return redirect('listar_clientes')

    if not cliente.telefone_principal:
        messages.error(request, f"⚠️ O cliente {cliente.nome_completo} não tem telefone registado.")
        return redirect('listar_clientes')

    # 2. Higienizar nome e número de telefone
    nome_limpo = " ".join(str(cliente.nome_completo).splitlines()).strip()
    numero_limpo = ''.join(filter(str.isdigit, str(cliente.telefone_principal)))
    if len(numero_limpo) == 9:
        numero_limpo = f"351{numero_limpo}"

    # 3. Escolher a mensagem automaticamente consoante o filtro usado na tabela
    contexto_msg = request.GET.get('tipo', 'geral')
    if contexto_msg == 'aniversario':
        assunto = "Felicitações de Aniversário (Atalho Rápido)"
        corpo = (
            f"Olá {nome_limpo}! 🎂\n\n"
            f"Passo por aqui para lhe desejar um excelente dia de aniversário, "
            f"repleto de saúde, alegria e grandes conquistas!\n\n"
            f"Um grande abraço,\nA sua Consultora Imobiliária"
        )
    elif contexto_msg == 'validade':
        data_str = cliente.data_validade_documento.strftime('%d/%m/%Y') if cliente.data_validade_documento else 'brevemente'
        assunto = "Lembrete de Validade de Documento (Atalho Rápido)"
        corpo = (
            f"Olá {nome_limpo},\n\n"
            f"Espero que esteja tudo bem consigo! Ao revermos a sua ficha, notámos que a validade "
            f"do seu documento de identificação registado é {data_str}. 🪪\n\n"
            f"Caso já o tenha renovado e queira atualizar os dados connosco, estou ao inteiro dispor!\n\n"
            f"Com os melhores cumprimentos,\nA sua Consultora Imobiliária"
        )
    else:
        assunto = "Contacto Rápido WhatsApp"
        corpo = (
            f"Olá {nome_limpo},\n\n"
            f"Espero que esteja tudo bem consigo! Entro em contacto para saber se precisa de algum "
            f"apoio com os seus projetos imobiliários.\n\n"
            f"Com os melhores cumprimentos,\nA sua Consultora Imobiliária"
        )

    # 4. Gerar link único de Opt-out RGPD
    signer = TimestampSigner()
    token = signer.sign(str(cliente.pk))
    link_optout = request.build_absolute_uri(reverse('cancelar_consentimento_rgpd', args=[token]))

    texto_final = (
        f"{corpo}\n\n"
        f"---\n"
        f"_Para cancelar o consentimento de futuras mensagens, aceda a:_ {link_optout}"
    )

    # 5. Registar automaticamente no Histórico de Interações
    Interacao.objects.create(
        cliente=cliente,
        tipo='mensagem',
        resumo=f"💬 WhatsApp Rápido: {assunto}",
        detalhes=corpo
    )

    url_whatsapp = f"https://wa.me/{numero_limpo}?text={quote(texto_final)}"
    return redirect(url_whatsapp)

@login_required
def preparar_campanha_whatsapp(request):
    """Prepara uma fila de disparo rápido de WhatsApp personalizado apenas para clientes com Opt-in RGPD."""
    if request.method == 'POST':
        assunto = request.POST.get('assunto', 'Campanha WhatsApp').strip()
        mensagem_base = request.POST.get('conteudo', '').strip()

        if not mensagem_base:
            messages.error(request, "Por favor, escreva o texto da mensagem para a campanha de WhatsApp.")
            return redirect('listar_clientes')

        clientes = Cliente.objects.filter(
            is_ativo=True,
            consentimento_marketing=True
        ).exclude(
            Q(telefone_principal__isnull=True) | Q(telefone_principal='')
        )

        escopo = request.POST.get('escopo', 'todos')
        if escopo == 'filtrados':
            hoje = timezone.now().date()
            q = request.POST.get('filtro_q', '').strip()
            qualificacao = request.POST.get('filtro_qualificacao', '').strip()
            interesse = request.POST.get('filtro_interesse', '').strip()
            mes_aniversario = request.POST.get('filtro_mes_aniversario', '').strip()
            mes_validade = request.POST.get('filtro_mes_validade', '').strip()
            ano_validade = request.POST.get('filtro_ano_validade', '').strip()

            if q:
                clientes = clientes.filter(nome_completo__icontains=q)
            if qualificacao:
                clientes = clientes.filter(qualificacao__icontains=qualificacao)
            if interesse:
                clientes = clientes.filter(area_interesse__icontains=interesse)
            if mes_aniversario and mes_aniversario.isdigit():
                clientes = clientes.filter(data_nascimento__month=int(mes_aniversario))
            if mes_validade or ano_validade:
                clientes = clientes.filter(negocios__isnull=False).exclude(
                    Q(tipo_documento__isnull=True) | Q(tipo_documento='')
                )
                if mes_validade and mes_validade.isdigit():
                    clientes = clientes.filter(data_validade_documento__month=int(mes_validade))
                if ano_validade == 'expirados':
                    clientes = clientes.filter(data_validade_documento__lt=hoje)
                elif ano_validade and ano_validade.isdigit():
                    clientes = clientes.filter(data_validade_documento__year=int(ano_validade))
                elif mes_validade and not ano_validade:
                    clientes = clientes.filter(data_validade_documento__year=hoje.year)
                clientes = clientes.distinct()

        fila_envio = []
        for cliente in clientes:
            nome_limpo = " ".join(str(cliente.nome_completo).splitlines()).strip()
            numero_limpo = ''.join(filter(str.isdigit, str(cliente.telefone_principal)))
            if len(numero_limpo) == 9:
                numero_limpo = f"351{numero_limpo}"

            if not numero_limpo:
                continue

            texto_personalizado = mensagem_base.replace('{{ nome }}', nome_limpo)
            texto_com_rodape = (
                f"{texto_personalizado}\n\n"
                f"_(Para não receber estes lembretes, basta responder \"Cancelar\")_"
            )

            fila_envio.append({
                'cliente': cliente,
                'nome': nome_limpo,
                'telefone': cliente.telefone_principal,
                'url_whatsapp': f"https://wa.me/{numero_limpo}?text={quote(texto_com_rodape)}",
                'preview': texto_personalizado,
            })

        if not fila_envio:
            messages.warning(request, "⚠️ Nenhum cliente elegível (com Opt-in RGPD ativo e telefone) para esta campanha.")
            return redirect('listar_clientes')

        return render(request, 'crm_core/campanha_whatsapp_fila.html', {
            'fila_envio': fila_envio,
            'assunto': assunto,
            'total': len(fila_envio),
        })

    return redirect('listar_clientes')
@login_required
def registar_envio_whatsapp_lote(request, pk):
    """Grava no Histórico de Interações apenas quando a consultora clica efetivamente em Enviar."""
    if request.method == 'POST':
        cliente = get_object_or_404(Cliente, pk=pk, is_ativo=True, consentimento_marketing=True)
        assunto = request.POST.get('assunto', 'Campanha WhatsApp').strip()
        detalhes = request.POST.get('detalhes', '').strip()

        Interacao.objects.create(
            cliente=cliente,
            tipo='mensagem',
            resumo=f"📣 Campanha WhatsApp: {assunto}",
            detalhes=detalhes
        )
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'erro'}, status=400)
