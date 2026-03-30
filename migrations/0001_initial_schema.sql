create extension if not exists pgcrypto;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create table if not exists public.users (
  id uuid primary key references auth.users(id) on delete cascade,
  email text unique not null,
  full_name text,
  auth_provider text,
  phone text,
  is_active boolean not null default true,
  created_at timestamptz not null default now()
);

create or replace function public.handle_new_auth_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.users (id, email, auth_provider)
  values (
    new.id,
    new.email,
    coalesce(new.raw_app_meta_data ->> 'provider', 'supabase')
  )
  on conflict (id) do update
  set email = excluded.email,
      auth_provider = excluded.auth_provider;

  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
after insert on auth.users
for each row execute procedure public.handle_new_auth_user();

create table if not exists public.accounts (
  id uuid primary key default gen_random_uuid(),
  business_name text not null,
  slug text unique,
  country text not null default 'AU',
  timezone text not null default 'Australia/Brisbane',
  business_type text,
  plan_code text,
  status text not null default 'trial'
    check (status in ('active', 'trial', 'suspended', 'cancelled')),
  primary_phone text,
  onboarding_step int not null default 1 check (onboarding_step between 1 and 5),
  onboarding_completed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint ck_accounts_business_type
    check (business_type is null or business_type in ('plumber', 'electrician', 'cleaner', 'locksmith', 'other'))
);

create trigger trg_accounts_updated_at
before update on public.accounts
for each row execute procedure public.set_updated_at();

create table if not exists public.account_memberships (
  id uuid primary key default gen_random_uuid(),
  account_id uuid not null references public.accounts(id) on delete cascade,
  user_id uuid not null references public.users(id) on delete cascade,
  role text not null check (role in ('owner', 'staff')),
  invited_at timestamptz,
  accepted_at timestamptz,
  unique (account_id, user_id)
);

create index if not exists ix_account_memberships_account_role
  on public.account_memberships (account_id, role);

create table if not exists public.lead_sources (
  id uuid primary key default gen_random_uuid(),
  account_id uuid not null references public.accounts(id) on delete cascade,
  type text not null check (type = 'web_form'),
  external_key text not null unique,
  config_json jsonb,
  is_active boolean not null default true
);

create index if not exists ix_lead_sources_account_active
  on public.lead_sources (account_id, is_active);

create table if not exists public.leads (
  id uuid primary key default gen_random_uuid(),
  account_id uuid not null references public.accounts(id) on delete cascade,
  lead_source_id uuid not null references public.lead_sources(id) on delete restrict,
  external_reference text,
  customer_name text not null,
  customer_phone text not null,
  customer_email text,
  customer_phone_hash text,
  customer_email_hash text,
  suburb text not null,
  service_requested text not null,
  raw_text text,
  normalized_text text,
  urgency_level text check (urgency_level is null or urgency_level in ('low', 'medium', 'high', 'emergency')),
  qualification_summary text,
  status text not null default 'new' check (status in ('new', 'follow_up', 'done')),
  ai_status text not null default 'pending' check (ai_status in ('pending', 'completed', 'failed')),
  is_possible_duplicate boolean not null default false,
  duplicate_of_lead_id uuid references public.leads(id),
  consent_to_sms boolean not null default true,
  consent_captured_at timestamptz,
  received_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create trigger trg_leads_updated_at
before update on public.leads
for each row execute procedure public.set_updated_at();

create index if not exists ix_leads_account_status_received
  on public.leads (account_id, status, received_at desc);

create index if not exists ix_leads_account_phone_hash_received
  on public.leads (account_id, customer_phone_hash, received_at desc);

create index if not exists ix_leads_account_ai_status
  on public.leads (account_id, ai_status);

create table if not exists public.lead_events (
  id uuid primary key default gen_random_uuid(),
  account_id uuid not null references public.accounts(id) on delete cascade,
  lead_id uuid not null references public.leads(id) on delete cascade,
  event_type text not null,
  payload_json jsonb,
  created_at timestamptz not null default now()
);

create index if not exists ix_lead_events_account_lead_created
  on public.lead_events (account_id, lead_id, created_at desc);

create table if not exists public.processing_jobs (
  id uuid primary key default gen_random_uuid(),
  account_id uuid not null references public.accounts(id) on delete cascade,
  lead_id uuid not null references public.leads(id) on delete cascade,
  job_type text not null check (job_type in ('process_lead', 'send_sms')),
  status text not null default 'pending' check (status in ('pending', 'processing', 'completed', 'failed')),
  attempts int not null default 0,
  max_attempts int not null default 3,
  idempotency_key text not null unique,
  locked_until timestamptz,
  scheduled_at timestamptz not null default now(),
  processed_at timestamptz,
  error_code text,
  error_message text
);

create index if not exists ix_processing_jobs_status_scheduled
  on public.processing_jobs (status, scheduled_at);

create index if not exists ix_processing_jobs_account_lead_type
  on public.processing_jobs (account_id, lead_id, job_type);

create table if not exists public.templates (
  id uuid primary key default gen_random_uuid(),
  account_id uuid not null references public.accounts(id) on delete cascade,
  template_type text not null check (template_type in ('acknowledge', 'qualify', 'urgent', 'after_hours')),
  channel text not null default 'sms' check (channel = 'sms'),
  content text not null,
  locale text not null default 'en-AU',
  is_default boolean not null default false,
  active_version int not null default 1,
  fallback_template_id uuid references public.templates(id),
  variables_schema jsonb not null default '["customer_name","business_name"]'::jsonb,
  is_active boolean not null default true,
  version int not null default 1
);

create index if not exists ix_templates_account_type_active
  on public.templates (account_id, template_type, is_active);

create table if not exists public.messages (
  id uuid primary key default gen_random_uuid(),
  account_id uuid not null references public.accounts(id) on delete cascade,
  lead_id uuid not null references public.leads(id) on delete cascade,
  channel text not null default 'sms' check (channel = 'sms'),
  recipient_type text not null check (recipient_type in ('lead', 'tradie')),
  recipient_value text not null,
  template_id uuid references public.templates(id),
  body text not null,
  status text not null default 'queued'
    check (status in ('queued', 'sent_to_provider', 'delivered', 'failed', 'undelivered')),
  provider text not null default 'twilio',
  provider_message_id text,
  created_at timestamptz not null default now()
);

create index if not exists ix_messages_account_lead_created
  on public.messages (account_id, lead_id, created_at desc);

create index if not exists ix_messages_account_status
  on public.messages (account_id, status);

create table if not exists public.message_attempts (
  id uuid primary key default gen_random_uuid(),
  message_id uuid not null references public.messages(id) on delete cascade,
  attempt_number int not null,
  request_payload_json jsonb,
  provider_response_json jsonb,
  provider_status text,
  error_message text,
  attempted_at timestamptz not null default now()
);

create index if not exists ix_message_attempts_message_attempt
  on public.message_attempts (message_id, attempt_number);

create table if not exists public.delivery_status_events (
  id uuid primary key default gen_random_uuid(),
  account_id uuid not null references public.accounts(id) on delete cascade,
  message_id uuid not null references public.messages(id) on delete cascade,
  provider text not null,
  provider_message_id text,
  status text not null,
  raw_payload_json jsonb,
  received_at timestamptz not null default now()
);

create index if not exists ix_delivery_events_account_message_received
  on public.delivery_status_events (account_id, message_id, received_at desc);

create table if not exists public.subscriptions (
  id uuid primary key default gen_random_uuid(),
  account_id uuid not null references public.accounts(id) on delete cascade,
  provider text not null default 'paddle',
  provider_customer_id text,
  provider_subscription_id text unique,
  status text not null check (status in ('trialing', 'active', 'past_due', 'cancelled')),
  plan_code text check (plan_code is null or plan_code in ('early_adopter', 'standard')),
  trial_ends_at timestamptz,
  current_period_end timestamptz,
  cancel_at_period_end boolean not null default false
);

create index if not exists ix_subscriptions_account_status
  on public.subscriptions (account_id, status);

create table if not exists public.billing_events (
  id uuid primary key default gen_random_uuid(),
  account_id uuid not null references public.accounts(id) on delete cascade,
  event_type text not null,
  provider_event_id text not null unique,
  raw_payload_json jsonb,
  processed_at timestamptz,
  status text not null check (status in ('processed', 'failed'))
);

create index if not exists ix_billing_events_account_processed
  on public.billing_events (account_id, processed_at desc);

create table if not exists public.audit_logs (
  id uuid primary key default gen_random_uuid(),
  account_id uuid not null references public.accounts(id) on delete cascade,
  user_id uuid references public.users(id) on delete set null,
  entity_type text not null,
  entity_id uuid,
  action text not null,
  metadata_json jsonb,
  ip_address text,
  user_agent text,
  created_at timestamptz not null default now()
);

create index if not exists ix_audit_logs_account_entity_created
  on public.audit_logs (account_id, entity_type, created_at desc);

create table if not exists public.rate_limit_buckets (
  bucket_key text not null,
  window_start timestamptz not null,
  request_count int not null default 0,
  expires_at timestamptz not null,
  primary key (bucket_key, window_start)
);

create index if not exists ix_rate_limit_buckets_expires_at
  on public.rate_limit_buckets (expires_at);
