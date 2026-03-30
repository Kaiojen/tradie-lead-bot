alter table public.accounts
  add column if not exists business_hours_start time not null default '08:00',
  add column if not exists business_hours_end time not null default '18:00',
  add column if not exists business_hours_tz text not null default 'Australia/Brisbane';

create table if not exists public.lead_notes (
  id uuid primary key default gen_random_uuid(),
  account_id uuid not null references public.accounts(id) on delete cascade,
  lead_id uuid not null references public.leads(id) on delete cascade,
  user_id uuid not null references public.users(id) on delete cascade,
  content text not null,
  created_at timestamptz not null default now()
);

create index if not exists ix_lead_notes_account_lead_created
  on public.lead_notes (account_id, lead_id, created_at desc);

create table if not exists public.billing_events_unresolved (
  id uuid primary key default gen_random_uuid(),
  provider_event_id text not null unique,
  raw_payload_json jsonb not null,
  received_at timestamptz not null default now()
);

alter table public.lead_notes enable row level security;

drop policy if exists lead_notes_member_select on public.lead_notes;
create policy lead_notes_member_select on public.lead_notes
for select using (public.is_account_member(account_id));

drop policy if exists lead_notes_member_insert on public.lead_notes;
create policy lead_notes_member_insert on public.lead_notes
for insert with check (public.is_account_member(account_id));
