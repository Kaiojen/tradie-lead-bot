# ARQUITETURA FINAL — Tradie Lead Bot (AU)
**Versão:** 1.0 | **Status:** Aprovada para build

---

## 1. DECISÃO ESTRUTURAL

| Item | Decisão |
|---|---|
| Formato | SaaS 100% web responsivo |
| App nativo iOS/Android | ❌ Não na v1 |
| PWA | ❌ Não na v1 (base preparada para v1.1) |
| Arquitetura | Monólito modular + worker separado |
| Microserviços | ❌ Não |

---

## 2. STACK TECNOLÓGICO

| Camada | Tecnologia |
|---|---|
| Frontend | Next.js (web responsivo) |
| Backend API | FastAPI (Python) |
| Worker | FastAPI/Python — processo separado |
| Banco | Supabase (Postgres) |
| Auth | Supabase Auth |
| Fila | Postgres jobs (tabela processing_jobs) |
| IA | OpenAI GPT-4o mini |
| SMS | Twilio |
| Pagamento | Paddle |
| Deploy | Render ou Railway (web + api + worker separados) |
| Observabilidade | Logs estruturados + Sentry |

---

## 3. COMPONENTES DO SISTEMA

```
[Lead entra]
     ↓
[API — FastAPI]
     ↓ valida + persiste
[Supabase Postgres]
     ↓ cria job
[processing_jobs]
     ↓
[Worker — Python]
     ├── OpenAI GPT-4o mini (qualifica)
     └── Twilio (envia SMS)
          ↓
     [Callback Twilio → API → atualiza status]
          ↓
     [Painel Next.js — tradie vê o lead]
```

---

## 4. MÓDULOS DA V1

### Módulo 1 — Auth & Access
- Login por e-mail + magic link ou senha
- Roles: `owner` e `staff` apenas
- Isolamento por `account_id`

### Módulo 2 — Account & Tenancy
- Multi-tenant: shared DB + shared schema + `account_id`
- Dados: nome da empresa, timezone, telefone principal, tipo de serviço, regras de SMS
- Todo registro carrega `account_id` — sem exceção

### Módulo 3 — Onboarding (Setup)
- 5 passos guiados (ver documento de semântica)
- Sem wizard gigante
- Primeiro SMS de teste disparado durante o setup
- Campos: nome da empresa, tipo de serviço, telefone do tradie, horário de atendimento, auto-reply padrão

### Módulo 4 — Lead Ingestion
- Entrada v1: **formulário web apenas** (e-mail parsing → v1.1)
- Fluxo obrigatório: validar → persistir → criar job → responder 200
- **Nunca chamar IA ou Twilio antes de persistir o lead**
- Deduplicação básica por fingerprint (account_id + phone + janela de tempo)

### Módulo 5 — Processing Queue
- Fila persistida em tabela `processing_jobs`
- Worker polling com lock
- Retries com backoff exponencial
- Dead-letter lógico (status `failed`)
- Reprocessamento manual disponível no painel
- Idempotência por `idempotency_key`

### Módulo 6 — AI Qualification Engine
A IA na v1 faz apenas 3 coisas:
1. Resumir o lead
2. Classificar urgência (`low` / `medium` / `high` / `emergency`)
3. Extrair campos essenciais (nome, serviço, suburb, disponibilidade)

❌ Lead score sofisticado → v1.1  
❌ Decisões irreversíveis baseadas em IA → nunca

### Módulo 7 — Messaging / SMS Orchestrator
- SMS para cliente final (auto-reply)
- SMS alerta para o tradie (resumo do lead)
- Registrar 3 estados separados: intenção de envio / tentativa / status final
- Reconciliar callbacks do Twilio
- Validar assinatura de todos os webhooks Twilio

### Módulo 8 — Web Dashboard (Inbox)
- Lista de enquiries com status visual
- Timeline do lead (recebido → qualificado → SMS enviado)
- Botão "Mark as Done"
- Botão "Retry" quando SMS falha
- Botão "Reprocess" para reprocessamento manual
- Painel de onboarding
- Status da assinatura

### Módulo 9 — Billing
- Trial de 14 dias
- 2 planos: Early Adopter (AUD 99) e Padrão (AUD 149)
- Bloqueio suave por inadimplência
- Webhook de subscription update do Paddle

### Módulo 10 — Audit Log
Registrar obrigatoriamente desde o dia 1:
- Lead recebido
- Job criado
- IA executada
- SMS tentado / enviado / falhou
- Usuário alterou auto-reply
- Reprocessamento manual
- Billing webhooks

### Módulo 11 — Monitoring & Alerting
- Erros por módulo
- Job stuck
- Webhook falhando
- Taxa de leads não processados
- Notificações internas de falha

---

## 5. FLUXO PRINCIPAL COMPLETO

### A. Entrada
1. Lead entra via formulário web
2. API valida payload
3. API resolve `account_id` pelo form token
4. API cria registro `lead` com status `received`
5. API grava `audit_log`
6. API cria job `process_lead`
7. API responde 200 imediatamente

### B. Processamento (Worker)
8. Worker consome job
9. Worker obtém lock / idempotency key
10. Worker normaliza dados
11. Worker roda dedupe básico
12. Worker chama OpenAI: resume + classifica urgência + extrai campos
13. Worker persiste resultado
14. Worker monta templates de SMS
15. Worker despacha jobs de envio

### C. Envio
16. Worker envia SMS via Twilio
17. Cada tentativa gera `message_attempt`
18. Status inicial: `queued` / `sent_to_provider`
19. Callback Twilio atualiza: `delivered` / `failed` / `undelivered`
20. Dashboard reflete estado atualizado

### D. Painel
21. Tradie/office manager abre o Inbox
22. Vê enquiry com: origem, resumo, urgência, timeline, status SMS
23. Pode: Mark as Done / Add Note / Retry / Reprocess

---

## 6. FLUXOS DE EXCEÇÃO

| Exceção | Comportamento |
|---|---|
| OpenAI falha | Lead salvo; envia alerta SMS bruto ao tradie com dados crus; job entra em retry |
| Twilio falha | Lead processado; `message` fica `provider_failed`; retry com backoff; alerta interno após N falhas |
| Lead duplicado | Marca `possible_duplicate`; não apaga; associa ao lead anterior; evita duplo envio |
| Webhook inválido | Rejeita 401/403; loga tentativa; nunca processa payload não autenticado |
| Banco indisponível | Request falha explicitamente; não tenta processar sem salvar |
| Worker travado | Watchdog detecta; requeue controlado; lock com TTL |

**Princípio absoluto: o failsafe não é "nunca falhar". É "nunca perder o lead".**

---

## 7. MODELAGEM DE DADOS

### Tabelas principais

| Tabela | Finalidade |
|---|---|
| `users` | Identidade do usuário |
| `accounts` | Tenant / empresa cliente |
| `account_memberships` | Relação user-account com role |
| `lead_sources` | Origem de captura (form token) |
| `leads` | Entidade principal de negócio |
| `lead_events` | Timeline operacional do lead |
| `processing_jobs` | Fila persistida |
| `messages` | Intenção de comunicação |
| `message_attempts` | Histórico técnico de envio |
| `delivery_status_events` | Callbacks do provedor |
| `templates` | Auto-replies configuráveis |
| `subscriptions` | Assinatura e trial |
| `billing_events` | Trilha de webhooks financeiros |
| `audit_logs` | Auditoria geral |

### Campos-chave de leads
```
id, account_id, lead_source_id,
customer_name, customer_phone, customer_email,
suburb, service_requested,
raw_text, normalized_text,
urgency_level, qualification_summary,
status, ai_status, duplicate_of_lead_id,
received_at, created_at, updated_at
```

> Nota: `trade_type` NÃO vai no lead. Vai em `accounts.business_type`. Se a conta é de um encanador, todo lead é contextualmente de encanamento. O lead carrega `service_requested` (o que o cliente pediu especificamente).

### Templates — campos adicionais necessários
```
locale, active_version, fallback_template_id, variables_schema
```

---

## 8. ROADMAP DE FASES

### V1 (construir agora)
Auth · Account/tenant · Onboarding básico · Formulário · Lead ingestion · Processing jobs · IA básica (3 funções) · SMS outbound · Painel Inbox · Trial + billing · Audit log · Monitoramento mínimo · Reprocessamento manual · Webhooks validados

### V1.1
E-mail parsing · Dedupe melhorado · Analytics por conta · Templates avançados · Regras sem IA · Fallback e-mail · Retries mais sofisticados · PWA leve

### V2
Integrações (ServiceM8 / Tradify / Xero) · Calendar sync · WhatsApp Business API · Voice/telephony · CRM lite · App mobile (se houver prova de necessidade)
