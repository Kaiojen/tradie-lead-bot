# BRIEF TÉCNICO FINAL — Tradie Lead Bot (AU)
**Para:** o1 (executor técnico)
**De:** Planejamento do projeto
**Versão:** 1.0 | **Status:** Pronto para build

---

## CONTEXTO DO PRODUTO

Micro-SaaS B2B para o mercado australiano. O produto é um assistente automatizado de captura e qualificação de leads (chamados de "enquiries" no produto) para pequenas empresas de serviços — tradies (encanadores, eletricistas, etc.).

**Problema:** O tradie está em obra, não consegue atender o telefone ou responder mensagens, e perde jobs para concorrentes que respondem mais rápido.

**Solução:** Formulário no site do tradie captura o lead → sistema qualifica automaticamente com IA → envia auto-reply por SMS ao cliente → envia alerta SMS ao tradie com resumo do lead.

**Meta de negócio:** 25 clientes pagantes a AUD 149/mês.

---

## STACK DEFINIDO (NÃO NEGOCIÁVEL)

| Camada | Tecnologia |
|---|---|
| Frontend | Next.js (web responsivo — sem app nativo) |
| Backend API | FastAPI (Python) |
| Worker | Python — processo separado do servidor web |
| Banco | Supabase (Postgres) |
| Auth | Supabase Auth |
| Fila | Postgres jobs (tabela `processing_jobs`) |
| IA | OpenAI GPT-4o mini |
| SMS | Twilio |
| Pagamento | Paddle |
| Deploy | Render ou Railway (3 serviços: web/api/worker) |
| Observabilidade | Logs estruturados + Sentry |

---

## ARQUITETURA

### Fluxo principal
```
[Formulário web do tradie]
        ↓ POST
[FastAPI — /api/leads/ingest]
        ↓ 1. valida
        ↓ 2. persiste lead (leads table)
        ↓ 3. persiste job (processing_jobs table)
        ↓ 4. responde 200
[Worker Python — polling processing_jobs]
        ↓ 1. obtém lock
        ↓ 2. normaliza dados
        ↓ 3. dedupe básico
        ↓ 4. chama OpenAI GPT-4o mini
        ↓ 5. persiste qualificação
        ↓ 6. cria messages (cliente + tradie)
        ↓ 7. despacha jobs de envio SMS
[Worker SMS]
        ↓ Twilio API
        ↓ registra message_attempt
[Twilio callback → FastAPI /webhooks/twilio]
        ↓ valida assinatura HMAC
        ↓ atualiza delivery_status_events
        ↓ atualiza message status
[Painel Next.js]
        → tradie vê lead com timeline e status SMS
```

### Arquitetura de deploy
```
Render/Railway:
├── Service 1: Next.js (frontend + SSR)
├── Service 2: FastAPI (API)
└── Service 3: Python Worker (único processo — consome job_type: process_lead e job_type: send_sms)

Externos:
├── Supabase (Postgres + Auth)
├── Twilio (SMS)
├── OpenAI (IA)
└── Paddle (billing)
```

**REGRA ABSOLUTA:** Lead salvo no banco antes de qualquer chamada a Twilio ou OpenAI. Criação de lead + criação de job em transação atômica.

---

## MODELAGEM DE DADOS COMPLETA

### users
```sql
id UUID PRIMARY KEY
email TEXT UNIQUE NOT NULL
full_name TEXT
auth_provider TEXT
phone TEXT
is_active BOOLEAN DEFAULT true
created_at TIMESTAMPTZ DEFAULT now()
```

### accounts
```sql
id UUID PRIMARY KEY
business_name TEXT NOT NULL
slug TEXT UNIQUE
country TEXT DEFAULT 'AU'
timezone TEXT DEFAULT 'Australia/Brisbane'
business_type TEXT  -- plumber, electrician, cleaner, other
plan_code TEXT
status TEXT  -- active, trial, suspended, cancelled
primary_phone TEXT
onboarding_step INT DEFAULT 1
onboarding_completed_at TIMESTAMPTZ
created_at TIMESTAMPTZ DEFAULT now()
```

### account_memberships
```sql
id UUID PRIMARY KEY
account_id UUID REFERENCES accounts(id)
user_id UUID REFERENCES users(id)
role TEXT  -- owner, staff
invited_at TIMESTAMPTZ
accepted_at TIMESTAMPTZ
```

### lead_sources
```sql
id UUID PRIMARY KEY
account_id UUID REFERENCES accounts(id)
type TEXT  -- web_form (v1 only)
external_key TEXT UNIQUE  -- form token público
config_json JSONB
is_active BOOLEAN DEFAULT true
```

### leads
```sql
id UUID PRIMARY KEY
account_id UUID REFERENCES accounts(id)
lead_source_id UUID REFERENCES lead_sources(id)
external_reference TEXT
customer_name TEXT
customer_phone TEXT  -- criptografado em repouso (Fernet/AES-256 na camada da aplicação)
customer_email TEXT  -- criptografado em repouso (Fernet/AES-256 na camada da aplicação)
suburb TEXT
service_requested TEXT
raw_text TEXT
normalized_text TEXT
urgency_level TEXT  -- low, medium, high, emergency
qualification_summary TEXT
-- DOIS CAMPOS DE STATUS COM RESPONSABILIDADES DISTINTAS:
status TEXT  -- new, follow_up, done (controlado pelo usuário no painel)
ai_status TEXT  -- pending, completed, failed (controlado pelo sistema/worker)
-- Pipeline interno registrado em lead_events, não aqui
is_possible_duplicate BOOLEAN DEFAULT false
duplicate_of_lead_id UUID REFERENCES leads(id)
received_at TIMESTAMPTZ DEFAULT now()
created_at TIMESTAMPTZ DEFAULT now()
updated_at TIMESTAMPTZ DEFAULT now()
```

### lead_events
```sql
id UUID PRIMARY KEY
account_id UUID REFERENCES accounts(id)
lead_id UUID REFERENCES leads(id)
event_type TEXT  -- received, qualified, sms_sent, sms_failed, manually_reviewed, marked_done
payload_json JSONB
created_at TIMESTAMPTZ DEFAULT now()
```

### processing_jobs
```sql
id UUID PRIMARY KEY
account_id UUID REFERENCES accounts(id)
lead_id UUID REFERENCES leads(id)
job_type TEXT  -- process_lead, send_sms
status TEXT  -- pending, processing, completed, failed
attempts INT DEFAULT 0
max_attempts INT DEFAULT 3
idempotency_key TEXT UNIQUE
locked_until TIMESTAMPTZ
scheduled_at TIMESTAMPTZ DEFAULT now()
processed_at TIMESTAMPTZ
error_code TEXT
error_message TEXT
```

### messages
```sql
id UUID PRIMARY KEY
account_id UUID REFERENCES accounts(id)
lead_id UUID REFERENCES leads(id)
channel TEXT  -- sms
recipient_type TEXT  -- lead, tradie
recipient_value TEXT  -- telefone
template_id UUID REFERENCES templates(id)
body TEXT
status TEXT  -- queued, sent_to_provider, delivered, failed, undelivered
provider TEXT  -- twilio
provider_message_id TEXT
created_at TIMESTAMPTZ DEFAULT now()
```

### message_attempts
```sql
id UUID PRIMARY KEY
message_id UUID REFERENCES messages(id)
attempt_number INT
request_payload_json JSONB
provider_response_json JSONB
provider_status TEXT
error_message TEXT
attempted_at TIMESTAMPTZ DEFAULT now()
```

### delivery_status_events
```sql
id UUID PRIMARY KEY
account_id UUID REFERENCES accounts(id)
message_id UUID REFERENCES messages(id)
provider TEXT
provider_message_id TEXT
status TEXT
raw_payload_json JSONB
received_at TIMESTAMPTZ DEFAULT now()
```

### templates
```sql
id UUID PRIMARY KEY
account_id UUID REFERENCES accounts(id)
template_type TEXT  -- acknowledge, qualify, urgent, after_hours
channel TEXT  -- sms
content TEXT
locale TEXT DEFAULT 'en-AU'
is_default BOOLEAN DEFAULT false
active_version INT DEFAULT 1
fallback_template_id UUID REFERENCES templates(id)
variables_schema JSONB  -- ["customer_name", "business_name"]
is_active BOOLEAN DEFAULT true
version INT DEFAULT 1
```

### subscriptions
```sql
id UUID PRIMARY KEY
account_id UUID REFERENCES accounts(id)
provider TEXT  -- paddle
provider_customer_id TEXT
provider_subscription_id TEXT
status TEXT  -- trialing, active, past_due, cancelled
plan_code TEXT  -- early_adopter, standard
trial_ends_at TIMESTAMPTZ
current_period_end TIMESTAMPTZ
cancel_at_period_end BOOLEAN DEFAULT false
```

### billing_events
```sql
id UUID PRIMARY KEY
account_id UUID REFERENCES accounts(id)
event_type TEXT
provider_event_id TEXT UNIQUE
raw_payload_json JSONB
processed_at TIMESTAMPTZ
status TEXT  -- processed, failed
```

### audit_logs
```sql
id UUID PRIMARY KEY
account_id UUID REFERENCES accounts(id)
user_id UUID REFERENCES users(id) -- nullable para eventos de sistema
entity_type TEXT
entity_id UUID
action TEXT
metadata_json JSONB
ip_address TEXT
user_agent TEXT
created_at TIMESTAMPTZ DEFAULT now()
```

---

## MÓDULOS E PRIORIDADE

| Módulo | Prioridade | Risco técnico |
|---|---|---|
| Auth & Access | Crítica | Médio |
| Account & Tenancy | Crítica | Alto se mal modelado |
| Onboarding (Setup) | Crítica | Baixo |
| Lead Ingestion | Crítica | **Crítico** |
| Processing Queue | Crítica | **Crítico** |
| AI Qualification | Alta | Médio |
| SMS Orchestrator | Crítica | Alto |
| Web Dashboard | Crítica | Baixo |
| Billing (Paddle) | Alta | Médio |
| Audit Log | Crítica | Baixo |
| Monitoring & Alerting | Alta | Médio |

---

## CONTRATOS DE API (PRINCIPAIS ENDPOINTS)

### Lead Ingestion (público)
```
POST /api/leads/ingest
Headers: Content-Type: application/json
Body: {
  "form_token": "string",        -- identifica o account
  "customer_name": "string",
  "customer_phone": "string",    -- formato AU: 04XX XXX XXX
  "customer_email": "string?",
  "suburb": "string",
  "service_requested": "string",
  "raw_message": "string?"
}
Response 200: { "lead_id": "uuid", "status": "received" }
Response 400: { "error": "invalid_payload" }
Response 429: { "error": "rate_limited" }
```

### Webhook Twilio (recebe callbacks de entrega)
```
POST /webhooks/twilio
Headers: X-Twilio-Signature (validar HMAC)
Body: form-urlencoded (padrão Twilio)
Response 200: vazio (Twilio exige 200 rápido)
```

### Webhook Paddle (eventos de billing)
```
POST /webhooks/paddle
Headers: Paddle-Signature (validar)
Body: JSON (padrão Paddle)
Response 200: { "status": "ok" }
```

### Dashboard — listar enquiries
```
GET /api/enquiries?status=new&page=1&limit=20
Auth: Bearer token
Response: {
  "data": [...leads],
  "pagination": { "total": int, "page": int, "limit": int }
}
```

### Dashboard — atualizar status
```
PATCH /api/enquiries/{lead_id}/status
Auth: Bearer token
Body: { "status": "done" | "follow_up" | "new" }
Response 200: { "lead_id": "uuid", "status": "updated" }
```

### Dashboard — reprocessar lead
```
POST /api/enquiries/{lead_id}/reprocess
Auth: Bearer token (owner/admin only)
Response 200: { "job_id": "uuid" }
```

---

## COMPORTAMENTO DO WORKER

**Um único processo (Service 3)** consome dois tipos de job da tabela `processing_jobs`:
- `job_type: process_lead` — normaliza, dedupe, chama OpenAI, cria messages
- `job_type: send_sms` — envia via Twilio, registra tentativas

### Polling
```python
while True:
    job = fetch_next_job_with_lock()  # SELECT FOR UPDATE SKIP LOCKED
    if job:
        process(job)
    else:
        sleep(2)
```

### Estados do job
```
pending → processing → completed
                    ↓ (falha)
                  failed (após max_attempts)
```

### Lock / Idempotência
- `locked_until = now() + TTL (5 minutos)`
- `idempotency_key = f"{lead_id}:{job_type}:{version}"`
- Watchdog: jobs com `locked_until` expirado voltam para `pending`

### Comportamento da IA (GPT-4o mini)
A IA faz exatamente 3 coisas — não mais:
1. Resumir o lead em 1-2 linhas
2. Classificar urgência: `low` / `medium` / `high` / `emergency`
3. Extrair campos: nome, serviço, suburb, disponibilidade mencionada

Se IA falhar:
- `ai_status = 'failed'`
- Worker envia alerta SMS bruto ao tradie com dados crus do formulário
- Job entra em retry (máx 2 tentativas adicionais)
- Lead permanece visível no painel

### Fallback SMS se Twilio falhar
- `message.status = 'failed'`
- Retry com backoff exponencial (2s, 4s, 8s)
- Após max_attempts: `status = 'failed'`, flag visual no painel
- Alerta interno gerado

---

## SEGURANÇA — REQUISITOS OBRIGATÓRIOS

1. **Toda query filtrada por `account_id`** — sem exceção
2. **RLS habilitado no Supabase** para tabelas expostas ao frontend
3. **Validação HMAC** em webhooks Twilio e Paddle
4. **Rate limiting** em endpoints públicos (lead capture: 10/min por IP)
5. **TLS obrigatório** em todos os ambientes
6. **Campos sensíveis criptografados** em repouso (phone, email)
7. **Logs com masking** de dados sensíveis
8. **Transação atômica** para criação de lead + job
9. **Nunca processar webhook sem autenticação**
10. **Testes de isolamento multi-tenant** antes do deploy

---

## O QUE NÃO ENTRA NA V1 (NÃO IMPLEMENTAR)

- ❌ E-mail parsing / inbox parsing
- ❌ Call forwarding ou qualquer voz
- ❌ WhatsApp Business API
- ❌ App nativo iOS/Android
- ❌ PWA
- ❌ Integração com ServiceM8 / Tradify / Xero
- ❌ Calendar sync
- ❌ CRM completo
- ❌ Lead score sofisticado
- ❌ Roles além de owner/staff
- ❌ Deduplicação inteligente avançada
- ❌ Analytics complexos
- ❌ Onboarding_status como tabela separada (usar campos em accounts)

---

## SPRINT 0 — SETUP E FUNDAÇÃO

- [ ] Repositório + estrutura de pastas
- [ ] Supabase: projeto, banco, auth configurados
- [ ] FastAPI: estrutura base com middlewares (auth, account scoping, rate limit)
- [ ] Next.js: estrutura base com layout autenticado
- [ ] Worker: estrutura base com polling
- [ ] Variáveis de ambiente mapeadas (Twilio, OpenAI, Paddle, Supabase)
- [ ] Deploy inicial nos 3 serviços (Render/Railway)
- [ ] Migrations das tabelas principais
- [ ] Sentry configurado

## SPRINT 1 — FLUXO CRÍTICO

- [ ] Lead ingestion endpoint + validação
- [ ] Persistência de lead + job em transação
- [ ] Worker: consumo de job com lock
- [ ] Integração OpenAI (3 funções: resumo, urgência, extração)
- [ ] Integração Twilio (SMS ao cliente + alerta ao tradie)
- [ ] Webhook Twilio (validação + atualização de status)
- [ ] Painel mínimo: lista de leads + status SMS
- [ ] Audit log nos pontos críticos
- [ ] Teste end-to-end: formulário → SMS ao cliente → SMS ao tradie → painel

## SPRINT 2 — PRODUTO COMPLETO

- [ ] Auth completo (signup, login, magic link, reset)
- [ ] Account & tenancy (criação, onboarding, roles)
- [ ] Setup (5 passos + test drive SMS)
- [ ] Enquiry Details (modal com timeline)
- [ ] Auto-Replies (editor + test SMS)
- [ ] Settings completo
- [ ] Billing (Paddle: trial, assinatura, webhook)
- [ ] Subscription page
- [ ] Support page
- [ ] Teste de isolamento multi-tenant
- [ ] Checklist de segurança completo

---

## OBSERVAÇÕES FINAIS PARA O EXECUTOR

1. **Prioridade máxima:** não perder lead. Qualquer falha de IA ou SMS é aceitável desde que o lead esteja no banco e visível no painel.

2. **Simplicidade acima de elegância.** Isso é um MVP de validação. Não super-engenheirar.

3. **Placeholders aguardando validação de mercado:**
   - Perguntas exatas de qualificação do bot (depende do nicho: electrician ou plumber)
   - Textos dos Auto-Replies prontos (sendo desenvolvidos pelo Gemini)
   - Copy da landing page (sendo desenvolvido após entrevistas de mercado)

4. **Multi-tenancy é crítico.** Testar isolamento de dados entre tenants antes de qualquer acesso a produção.

5. **Audit log é obrigatório desde o sprint 1**, não é opcional para depois.
