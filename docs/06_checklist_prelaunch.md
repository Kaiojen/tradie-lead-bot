# CHECKLIST PRÉ-LAUNCH — IMPLEMENTAÇÃO

Checklist operacional derivado de `docs/04_criterios_seguranca.md` e do escopo v1.

## Segurança

- [x] TLS-ready via deploy separado `web` / `api` / `worker`
- [x] Validação de assinatura Twilio implementada
- [x] Janela temporal Twilio de 5 minutos implementada
- [x] Validação de assinatura Paddle implementada
- [x] Rate limiting em ingestão pública, webhooks e API autenticada
- [x] Middleware de `account_id` em rotas autenticadas
- [x] RBAC backend para `owner` / `staff`
- [x] Owner-only em billing e reprocess
- [x] RLS habilitado nas tabelas expostas ao frontend
- [x] Campos sensíveis criptografados na camada da aplicação
- [x] Masking de dados sensíveis em logs
- [x] Audit log mínimo implementado
- [ ] Teste de isolamento multi-tenant executado em banco real
- [ ] Restore de backup validado

## Operação

- [x] Lead e `processing_job` nascem em transação atômica
- [x] Worker separado do servidor web
- [x] Retry e watchdog de jobs implementados
- [x] Webhook Twilio atualiza status de entrega
- [x] Webhook Paddle registra eventos processados
- [x] Eventos Paddle não resolvidos são preservados
- [x] Inbox mínima implementada
- [x] Enquiry Details mínima implementada
- [x] Notas simples em Enquiry Details implementadas
- [x] Setup em 5 passos implementado
- [x] Auto-Replies editor implementado
- [x] Settings com `business_hours` implementado
- [x] Subscription page implementada
- [x] Support page implementada

## Pendências antes de produção

- Executar teste real de isolamento multi-tenant contra Supabase
- Validar fluxo de assinatura Paddle ponta a ponta com credenciais reais
- Confirmar build de produção do frontend no ambiente de CI/deploy
- Revisar variáveis de ambiente finais em Render/Railway
