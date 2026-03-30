# FLUXO DE PÁGINAS — Tradie Lead Bot (AU)
**Versão:** 1.0 | **Status:** Aprovado para design/build

---

## 1. MAPA GERAL DE PÁGINAS

```
[Público]
├── Landing Page
├── Pricing
└── Login / Sign Up

[Setup (pós-cadastro, pré-ativação)]
├── Passo 1 — Business Basics
├── Passo 2 — Your Number
├── Passo 3 — Your Auto-Reply
├── Passo 4 — Test Drive ⭐
└── Passo 5 — Connect

[App autenticado]
├── Inbox (tela principal — com filtros: New / Follow Up / Done)
│   └── Enquiry Details (modal)
├── Auto-Replies
├── Settings
├── Subscription
└── Support
```

---

## 2. PÁGINAS PÚBLICAS

### 2.1 Landing Page

**Objetivo:** Converter visitante em trial

**Seções:**
1. Hero — Headline + Subheadline + CTA ("Start free trial")
2. Problema — "Every missed call is a missed job" (visual de lead perdido)
3. Como funciona — 3 passos simples (lead chega → sistema responde → você recebe alerta)
4. Prova — Depoimento ou número (ex: "Tradies save X hours/week")
5. Pricing — 2 planos simples
6. FAQ — 5-6 perguntas
7. CTA final — "Start your 14-day free trial"

**CTA principal:** Start free trial (sem cartão de crédito)

---

### 2.2 Pricing

**Objetivo:** Remover objeção de preço antes do cadastro

**Conteúdo:**
- Early Adopter: AUD 99/mês (primeiros 10 clientes)
- Padrão: AUD 149/mês
- Trial: 14 dias grátis, sem cartão
- ROI frame: "One saved job pays for a full year"

---

### 2.3 Login / Sign Up

**Fluxo Sign Up:**
1. E-mail
2. Senha (ou magic link)
3. → Redireciona para Setup (passo 1)

**Fluxo Login:**
1. E-mail + senha
2. → Redireciona para Inbox

---

## 3. SETUP (5 PASSOS)

Barra de progresso visível durante todo o setup.

---

### Setup 1 — Business Basics

**Título:** "Tell us about your business"

**Campos:**
- Business name (obrigatório)
- Trade type — dropdown:
  - Plumber
  - Electrician
  - Cleaner
  - Locksmith
  - Other

**CTA:** Next →

---

### Setup 2 — Your Number

**Título:** "Where should we send your job alerts?"

**Campos:**
- Mobile number (Australian format: 04XX XXX XXX)
- Business hours (horário de atendimento — opcional no setup, ajustável depois)

**Copy de apoio:** "We'll send you an SMS whenever a new enquiry comes in."

**CTA:** Next →

---

### Setup 3 — Your Auto-Reply

**Título:** "How do you want to sound?"

**Apresenta 3 templates prontos baseados no trade escolhido no passo 1:**

Exemplo para Plumber:
- **Professional** — "Thanks for reaching out to [Business Name]. We're on a job right now and will get back to you shortly. What suburb are you in and what do you need help with?"
- **Friendly** — "Hey, thanks for getting in touch with [Business Name]! We're flat out at the moment but will call you back soon. What's the issue and where are you located?"
- **Direct** — "[Business Name] here. We're busy right now. What suburb and what's the problem?"

**Seleção:** Radio button — escolhe um e pode editar o texto

**CTA:** Next →

---

### Setup 4 — Test Drive ⭐

**Título:** "Let's make sure it works."

**O que acontece:**
- Sistema dispara um SMS de teste para o número inserido no passo 2
- Tela exibe: "We just sent a test SMS to [número]. Check your phone."
- Loading state enquanto aguarda confirmação de entrega
- Ao confirmar entrega: feedback visual positivo + "It works. "

**Se falhar:**
- Mensagem clara: "We couldn't reach that number. Check the number and try again."
- Botão: Resend test

**CTA:** Looks good, continue →

---

### Setup 5 — Connect

**Título:** "You're all set. Now connect your enquiry source."

**Opções apresentadas com logos:**

**Opção A — Website form**
- Instrução: "Copy this code and paste it before the `</body>` tag on your site."
- Code snippet copiável
- Links para guias: WordPress · Squarespace · Wix

**Opção B — Google Business Profile**
- Instrução: "Add this link to your Google Business website button."
- Link copiável

**Opção C — I'll do this later**
- Link para pular

**CTA:** Go to my Inbox →

---

## 4. APP AUTENTICADO

### 4.1 Inbox (Tela Principal)

**Layout:**
- Sidebar esquerda: navegação (Inbox / Auto-Replies / Settings / Subscription / Support)
- Área principal: lista de enquiries

**Lista de enquiries — colunas visíveis:**
- Status dot (azul = New / amarelo = Follow Up)
- Nome do cliente
- Serviço solicitado
- Suburb
- Tag de urgência (vermelho "Urgent" / laranja "Emergency" se IA classificou alto)
- Horário de entrada

**Ordenação:** Mais recente primeiro, com New sempre no topo

**Filtros internos:** New / Follow Up / Done (tabs ou dropdown acima da lista)

**Estado vazio:**
> *"You're all caught up. New enquiries will appear here."*

---

### 4.2 Enquiry Details (Modal / Slide-over)

**Abre ao clicar em qualquer linha da lista**

**Seções:**

**Header:**
- Nome + telefone (botão de copiar ao lado)
- Status atual + botão de mudança rápida
- Tag de urgência

**Summary (gerado pelo sistema):**
- Serviço solicitado
- Suburb
- Urgência: Low / Medium / High / Emergency
- Resumo em 1-2 linhas

**Timeline:**
```
10:00am — Enquiry received
10:01am — Auto-reply sent to customer ✓
10:01am — Job alert sent to you ✓
10:05am — [Manual action: Marked as Follow Up] by Jane
```

**Mensagens (SMS log):**
- SMS enviado ao cliente (conteúdo completo)
- Status de entrega: Sent ✓ / Failed to send ✗ + botão Retry

**Notas:**
- Campo de texto livre
- Botão Save Note

**Ações principais:**
- **Mark as Done** (CTA primário, verde)
- **Retry** (visível só se SMS falhou)
- **Reprocess** (visível para admin/owner)

---

### 4.3 Auto-Replies

**Título:** "Your Auto-Replies"

**Layout:**
- Lista de templates ativos (máximo 4 na v1: Acknowledge / Qualify / Urgent / After-hours)
- Clique abre editor

**Editor de template:**
- Campo de texto do SMS
- Variáveis disponíveis: `[Customer Name]` e `[Business Name]` (botões de inserção)
- Preview em tempo real com as variáveis substituídas
- Contador de caracteres (SMS = 160 chars por segmento)
- Botões: **Save** e **Send Test SMS**

**Estado ativo/inativo:** Toggle Turn On / Turn Off por template

---

### 4.4 Settings

**Seções:**

**Business Profile:**
- Business name
- Trade type
- Country / Timezone

**Alert Number:**
- Número de SMS do tradie
- Botão: Send test SMS

**Business Hours:**
- Horário de atendimento (usado para contexto do auto-reply after-hours)

**Team:**
- Lista de membros
- Botão: Invite team member (e-mail)
- Roles: Owner / Staff

**Integrations:**
- Form embed code (copiável)
- Google Business link (copiável)
- Webhook URL (para usuários técnicos)

---

### 4.5 Subscription

**Conteúdo:**
- Plano atual (Early Adopter AUD 99 / Padrão AUD 149)
- Status: Active / Trial (X days left) / Payment Issue
- Próxima cobrança
- Botão: Manage billing (abre portal Paddle)
- Botão: Cancel subscription

**Se Trial:**
- Banner: "X days left in your trial. Add payment to keep your Inbox running."
- CTA: Add payment method

---

### 4.6 Support

**Conteúdo:**
- Campo de mensagem (formulário simples)
- SLA visível: "We respond within 24 hours."
- Link para FAQ
- E-mail direto de suporte

---

## 5. FLUXO DE ESTADOS DO LEAD

**Dois campos separados — responsabilidades distintas:**

| Campo | Valores | Quem controla |
|---|---|---|
| `status` | `new` → `follow_up` → `done` | Usuário (painel) |
| `ai_status` | `pending` → `completed` / `failed` | Sistema (worker) |

**Pipeline interno (registrado em lead_events, não em campos de status):**
```
received
    ↓
processing (worker obtém job)
    ↓
qualified (ai_status = completed)
    ↓
sms_sent (SMS despachado ao cliente e ao tradie)
    ↓
[callback Twilio]
    ├── delivered → message.status = delivered
    └── failed   → message.status = failed (flag vermelha no painel)

Status do usuário (independente do pipeline):
new → follow_up → done
(movido manualmente — qualquer enquiry pode ser movida a qualquer momento)
```

---

## 6. ESTADOS DE FALHA VISÍVEIS

| Falha | O que o usuário vê |
|---|---|
| SMS ao cliente falhou | Tag vermelha "Failed to send" + botão Retry |
| IA não processou | Enquiry aparece sem resumo + tag "Needs review" |
| SMS ao tradie falhou | Alerta no topo do Inbox: "We couldn't send you an alert for 1 enquiry" |
| Trial expirado | Banner laranja no topo de todas as telas |
| Billing com problema | Banner vermelho + link para resolver |
