# CRITÉRIOS DE SEGURANÇA — Tradie Lead Bot (AU)
**Versão:** 1.0 | **Status:** Obrigatório desde o dia 1

---

## 1. AUTENTICAÇÃO

| Item | Requisito |
|---|---|
| Método | E-mail + magic link ou senha forte |
| MFA | Opcional para roles owner/admin |
| Sessões | Curtas com refresh tokens controlados |
| Reset de acesso | Fluxo seguro via e-mail verificado |
| Senhas | Nunca armazenar em texto plano — hash bcrypt ou Argon2 |

---

## 2. AUTORIZAÇÃO (RBAC)

**Roles da v1:**
- `owner` — acesso total, billing, team management
- `staff` — acesso operacional (Inbox, Auto-Replies, Settings básicas)

**Regras:**
- Toda query filtrada obrigatoriamente por `account_id`
- Nenhuma rota pode confiar só no frontend para autorização
- Middleware de auth + account scoping em todas as rotas do backend
- Validação de membership antes de qualquer operação
- Bloqueio de rotas por role no backend — nunca só no frontend

---

## 3. MULTI-TENANCY — ISOLAMENTO DE DADOS

| Item | Requisito |
|---|---|
| Modelo | Shared DB + shared schema + `account_id` em todas as tabelas |
| Índices | Compostos por `account_id` em todas as tabelas principais |
| RLS | Habilitar Row Level Security no Supabase para tabelas expostas ao frontend |
| Testes | Testes automatizados garantindo que conta A nunca acessa dados da conta B |
| Queries | Nenhuma query sem filtro de `account_id` em produção |

**Teste obrigatório antes do deploy:**
> Simular dois tenants e confirmar que nenhum endpoint retorna dados cruzados.

---

## 4. PROTEÇÃO DE WEBHOOKS

### Twilio
- Validar assinatura HMAC em toda requisição recebida
- Rejeitar requests fora de janela temporal (tolerância: 5 minutos)
- Endpoint dedicado e mínimo — não misturar com rotas da aplicação
- Nunca processar payload não autenticado

### Paddle
- Validar assinatura do webhook antes de processar qualquer evento de billing
- Idempotência: verificar se o evento já foi processado antes de executar
- Logar todos os eventos recebidos na tabela `billing_events`

---

## 5. CRIPTOGRAFIA E DADOS SENSÍVEIS

| Item | Requisito |
|---|---|
| Transporte | TLS obrigatório em todas as rotas |
| Segredos | Armazenar em variáveis de ambiente / secret manager — nunca no código |
| Campos sensíveis | Criptografar em repouso via camada da aplicação (biblioteca `cryptography` Python — Fernet/AES-256, chave em variável de ambiente): `customer_phone` e `customer_email` |
| Logs | Masking de dados sensíveis (telefone, e-mail) em todos os logs |
| API keys | Nunca logar API keys da Twilio, OpenAI ou Paddle |

---

## 6. VALIDAÇÃO DE INPUT

| Item | Requisito |
|---|---|
| Schema | Validação estrita em todas as entradas (Pydantic no FastAPI) |
| Sanitização | Sanitizar texto livre antes de armazenar e antes de enviar para OpenAI |
| Limites | Tamanho máximo de payload definido por endpoint |
| Injeção | Proteção contra HTML/script injection em campos de texto |
| Normalização | Phone e e-mail normalizados antes de persistir |
| SQL Injection | Usar ORM com queries parametrizadas — nunca interpolação de string |

---

## 7. RATE LIMITING

| Endpoint | Limite recomendado |
|---|---|
| Lead capture (formulário público) | 10 req/min por IP |
| Auth (login / magic link) | 5 req/min por IP |
| Webhooks (Twilio / Paddle) | 100 req/min |
| Ações manuais críticas (reprocess) | 10 req/min por usuário |
| API geral autenticada | 60 req/min por usuário |

---

## 8. PROTEÇÃO CONTRA PERDA DE LEAD

| Requisito | Detalhe |
|---|---|
| Persistência síncrona | Lead salvo no banco antes de qualquer chamada externa |
| Transação | Criação de lead + criação de job em uma única transação atômica |
| Zero in-memory | Nunca processar lead apenas em memória |
| Fallback | Se IA falha, lead existe; alerta bruto enviado ao tradie |
| Fallback 2 | Se SMS falha, lead existe no painel com flag visível |

---

## 9. LOGS E AUDITORIA

| Item | Requisito |
|---|---|
| Formato | Logs estruturados (JSON) |
| Correlation ID | Por request / job / lead — rastreabilidade de ponta a ponta |
| Masking | Dados sensíveis mascarados automaticamente nos logs |
| Audit log | Tabela `audit_logs` obrigatória desde o dia 1 |
| Retenção | Definir política de retenção de logs (mínimo 90 dias) |
| Alertas | Notificação interna para erros críticos (falha de SMS em massa, webhook falhando) |

---

## 10. BACKUPS

| Item | Requisito |
|---|---|
| Postgres | Backup automático via Supabase (diário no mínimo) |
| Restore | Testar restore ao menos uma vez antes do lançamento |
| Export mínimo | Exportação de leads e messages disponível para operações de emergência |

---

## 11. PRIVACIDADE E COMPLIANCE (Austrália)

O produto opera com dados de consumidores australianos — Australian Privacy Act 1988 se aplica para empresas com faturamento acima de AUD 3M, mas boas práticas se aplicam desde o início.

| Item | Requisito |
|---|---|
| Data minimization | Coletar apenas o necessário (nome, telefone, suburb, serviço) |
| Privacy notice | Exibida no formulário de captura de lead |
| Consentimento | Checkbox de consentimento no formulário (opt-in para receber SMS) |
| Retenção | Política de retenção de dados definida e comunicada |
| Acesso restrito | Dados de um tenant inacessíveis para outro |
| Exclusão | Mecanismo para apagar dados de uma conta (ao cancelar assinatura) |
| Export | Mecanismo para exportar dados de uma conta |
| Audit trail | Todas as ações sobre dados sensíveis registradas |

---

## 12. CHECKLIST DE SEGURANÇA PRÉ-LAUNCH

- [ ] TLS ativo em todos os ambientes
- [ ] Validação de assinatura Twilio implementada e testada
- [ ] Validação de assinatura Paddle implementada e testada
- [ ] RLS habilitado no Supabase
- [ ] Teste de isolamento multi-tenant executado
- [ ] Rate limiting ativo nos endpoints públicos
- [ ] Masking de dados sensíveis nos logs confirmado
- [ ] Backup automático configurado e restore testado
- [ ] Privacy notice no formulário de captura
- [ ] API keys e segredos fora do código (environment variables)
- [ ] Nenhuma rota retorna dados sem filtro de `account_id`
- [ ] Testes de autorização (staff não acessa rotas de owner)
