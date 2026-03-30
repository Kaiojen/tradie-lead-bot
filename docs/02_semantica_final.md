# SEMÂNTICA FINAL — Tradie Lead Bot (AU)
**Versão:** 1.0 | **Status:** Aprovada

---

## 1. ESSÊNCIA DO PRODUTO

**Definição:** Um assistente silencioso de caixa de entrada que garante que nenhuma oportunidade de orçamento seja perdida enquanto o profissional está trabalhando.

**Problema em uma frase:** "Estou com a mão na massa e perco clientes porque não posso atender ou responder na hora."

**Como o produto deve parecer:** Um cockpit silencioso. Uma ferramenta operacional confiável — não um personagem, não um robô conversacional, não um assistente com personalidade.

**Tom:** Direto, calmo, utilitário, com o casual australiano (*matey, but strictly business*). Sem jargão de marketing ou tecnologia.

---

## 2. VOCABULÁRIO DO SISTEMA

Tradies não gerenciam "leads" nem fecham "deals". Eles recebem **enquiries** e fazem **jobs** e **quotes**.

| Termo técnico | Termo no produto |
|---|---|
| Lead | **Enquiry** (plural: Enquiries) |
| Dashboard | **Inbox** |
| Templates | **Auto-Replies** |
| Onboarding | **Setup** |
| Alert para o tradie | **New Job Alert** |
| Resposta automática | **Auto-Reply** |
| Pedido de orçamento | **Quote Request** |
| Serviço urgente | **Urgent Job** / **Emergency Job** |
| Bot / IA | ❌ Nunca usar para o cliente final do tradie |
| "Our AI" | → "Our system" |
| "AI parsed" | → "We extracted the details" |

**Regra de ouro:** Use **Enquiry** do início ao fim. Se chamou de Enquiry no Inbox, não chame de Lead nas configurações nem de Request no billing.

---

## 3. NAVEGAÇÃO (SIDEBAR)

```
Inbox (com filtros internos: New / Follow Up / Done)
Auto-Replies
Settings
Subscription
Support
```

Os filtros New / Follow Up / Done ficam dentro do Inbox como tabs ou dropdown. Done não é página separada.

---

## 4. STATUS DO SISTEMA

### Status de Enquiry (visível para o usuário)
| Estado interno | Status no produto |
|---|---|
| Novo, não lido | **New** (dot azul) |
| Processado, aguarda ação | **Follow Up** |
| Finalizado | **Done** |

### Status de SMS (visível para o usuário)
| Estado interno | Status no produto |
|---|---|
| Enviado com sucesso | Checkmark simples + "Sent" (sem destaque) |
| Falha de entrega | **Failed to send** (vermelho + botão Retry) |

### Status de Conta / Billing
| Estado interno | Status no produto |
|---|---|
| Assinatura ativa | **Active** |
| Trial | **Trial (X days left)** |
| Inadimplente | **Payment Issue** |

---

## 5. VERBOS DE AÇÃO

| Ação | Texto no produto |
|---|---|
| Salvar | **Save** |
| Responder manualmente | **Reply** |
| Reenviar / Tentar novamente | **Retry** |
| Marcar como resolvido | **Mark as Done** |
| Ativar automação | **Turn On** |
| Desativar automação | **Turn Off** |
| Configurar | **Edit** |
| Reprocessar | **Reprocess** |

---

## 6. COPYWRITING — LANDING PAGE

**Headline principal:**
> *Never miss a job while you're on the tools.*

**Subheadline:**
> *Instantly reply to new enquiries and get SMS alerts for urgent jobs, automatically.*

**Pitch de 1 linha:**
> *The automated inbox that replies to customers while you're busy, so you win the quote before your competitors even call back.*

**Frase de ROI:**
> *Pay for a whole year by saving just one missed job.*

**Zero state (painel vazio):**
> *You're all caught up. New enquiries will appear here.*

---

## 7. SETUP (ONBOARDING) — 5 PASSOS

Objetivo: tradie ou office manager vê o sistema enviando um SMS para o próprio celular em menos de 3 minutos.

| Passo | Título | Objetivo |
|---|---|---|
| 1 | **Business Basics** | "What's your business name and trade?" |
| 2 | **Your Number** | "Where should we send your urgent job alerts?" |
| 3 | **Your Auto-Reply** | "How do you want to sound?" (3 templates prontos por nicho) |
| 4 | **Test Drive** ⭐ | "Let's test it. We just sent an SMS to your phone." |
| 5 | **Connect** | "You're all set. Link this to your website." |

**Test Drive é o momento de confiança.** O sistema dispara um SMS de teste real durante o setup. Isso converte mais do que qualquer copy.

**Regras do Setup:**
- Sem cartão de crédito no passo 1
- Sem perguntas sobre tamanho da empresa
- Sem wizard gigante
- Passos curtos, uma decisão por vez

---

## 8. ESTRUTURA DAS TELAS DO MVP

### Tela 1 — Inbox
- Lista de enquiries ordenada por recência
- Tag visual de urgência (Urgent / Emergency) para classificações altas da IA
- Clique na linha abre os detalhes
- ❌ Sem gráficos, estatísticas ou charts na v1

### Tela 2 — Enquiry Details (modal ou slide-over)
- Nome, telefone, serviço solicitado, suburb
- Resumo de urgência (gerado pelo sistema, não pela "IA")
- Timeline limpa: "Received 10:00am → Auto-reply sent 10:01am → Job alert sent to you 10:01am"
- Botão principal: **Mark as Done**
- Botão de copiar telefone
- Botão Retry se SMS falhou

### Tela 3 — Auto-Replies
- Caixa de texto do SMS de resposta
- Variáveis permitidas: apenas `[Customer Name]` e `[Business Name]`
- Botões: **Save** e **Send Test SMS**
- ❌ Sem variáveis complexas tipo `{{lead.custom_field_9}}`

### Tela 4 — Settings
- Dados da empresa
- Telefone de alerta
- Horário de atendimento
- Tipo de serviço

### Tela 5 — Subscription
- Plano atual, próximo vencimento
- Botão de upgrade/cancelamento

---

## 9. ESTRUTURA DOS AUTO-REPLIES (FRAMEWORK)

Os templates seguem 3 camadas configuráveis:

**Camada 1 — Intenção**
- Acknowledge (confirmação simples)
- Qualify (coletar informações)
- Urgent triage (emergência)
- After-hours reply (fora do horário)

**Camada 2 — Tom**
- Professional
- Friendly
- Direct

**Camada 3 — Nicho**
- Plumber / Electrician / Cleaner / General trades

**Estrutura interna de cada auto-reply:**
1. Confirmação
2. Contexto (estamos em serviço agora)
3. Próxima ação (retornaremos em breve)
4. Pergunta curta (suburb + tipo de serviço)

**O que evitar nos textos:**
- Emojis
- Exclamações excessivas
- Frases longas
- Múltiplas perguntas em bloco
- Promessas de tempo exatas
- Tom de call center / suporte corporativo
- Qualquer coisa que pareça chatbot genérico

> **Nota:** A criação dos templates de texto prontos (Auto-Replies em inglês australiano) será feita com o Gemini.

---

## 10. REGRAS DE CONSISTÊNCIA

1. **Nunca usar "AI" para o cliente final do tradie.** Use "our system" ou "we".
2. **Enquiry em todo lugar.** Não misturar com Lead, Request ou Contact.
3. **Foco em resolução.** O fluxo guia para "Done". O sistema existe para esvaziar a tela.
4. **Esconder complexidade técnica.** Guias de integração usam logos de plataformas (WordPress, Gmail) com passos de copiar e colar — sem expor API ou webhooks para o usuário.
5. **Confiança via transparência operacional.** A Timeline mostra exatamente o que aconteceu e quando. Se algo falhou, aparece com botão de Retry imediato.
