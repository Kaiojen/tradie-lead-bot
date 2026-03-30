alter table public.users enable row level security;
alter table public.accounts enable row level security;
alter table public.account_memberships enable row level security;
alter table public.lead_sources enable row level security;
alter table public.leads enable row level security;
alter table public.lead_events enable row level security;
alter table public.messages enable row level security;
alter table public.templates enable row level security;
alter table public.subscriptions enable row level security;
alter table public.billing_events enable row level security;
alter table public.audit_logs enable row level security;

create or replace function public.is_account_member(target_account_id uuid)
returns boolean
language sql
stable
as $$
  select exists (
    select 1
    from public.account_memberships membership
    where membership.account_id = target_account_id
      and membership.user_id = auth.uid()
  );
$$;

create or replace function public.is_account_owner(target_account_id uuid)
returns boolean
language sql
stable
as $$
  select exists (
    select 1
    from public.account_memberships membership
    where membership.account_id = target_account_id
      and membership.user_id = auth.uid()
      and membership.role = 'owner'
  );
$$;

drop policy if exists users_self_select on public.users;
create policy users_self_select on public.users
for select using (id = auth.uid());

drop policy if exists users_self_update on public.users;
create policy users_self_update on public.users
for update using (id = auth.uid());

drop policy if exists accounts_member_select on public.accounts;
create policy accounts_member_select on public.accounts
for select using (public.is_account_member(id));

drop policy if exists accounts_owner_update on public.accounts;
create policy accounts_owner_update on public.accounts
for update using (public.is_account_owner(id));

drop policy if exists account_memberships_member_select on public.account_memberships;
create policy account_memberships_member_select on public.account_memberships
for select using (public.is_account_member(account_id));

drop policy if exists account_memberships_owner_write on public.account_memberships;
create policy account_memberships_owner_write on public.account_memberships
for all using (public.is_account_owner(account_id))
with check (public.is_account_owner(account_id));

drop policy if exists lead_sources_member_select on public.lead_sources;
create policy lead_sources_member_select on public.lead_sources
for select using (public.is_account_member(account_id));

drop policy if exists lead_sources_owner_write on public.lead_sources;
create policy lead_sources_owner_write on public.lead_sources
for all using (public.is_account_owner(account_id))
with check (public.is_account_owner(account_id));

drop policy if exists leads_member_select on public.leads;
create policy leads_member_select on public.leads
for select using (public.is_account_member(account_id));

drop policy if exists leads_member_write on public.leads;
create policy leads_member_write on public.leads
for all using (public.is_account_member(account_id))
with check (public.is_account_member(account_id));

drop policy if exists lead_events_member_select on public.lead_events;
create policy lead_events_member_select on public.lead_events
for select using (public.is_account_member(account_id));

drop policy if exists lead_events_member_write on public.lead_events;
create policy lead_events_member_write on public.lead_events
for insert with check (public.is_account_member(account_id));

drop policy if exists messages_member_select on public.messages;
create policy messages_member_select on public.messages
for select using (public.is_account_member(account_id));

drop policy if exists messages_member_write on public.messages;
create policy messages_member_write on public.messages
for all using (public.is_account_member(account_id))
with check (public.is_account_member(account_id));

drop policy if exists templates_member_select on public.templates;
create policy templates_member_select on public.templates
for select using (public.is_account_member(account_id));

drop policy if exists templates_member_write on public.templates;
create policy templates_member_write on public.templates
for all using (public.is_account_member(account_id))
with check (public.is_account_member(account_id));

drop policy if exists subscriptions_member_select on public.subscriptions;
create policy subscriptions_member_select on public.subscriptions
for select using (public.is_account_member(account_id));

drop policy if exists subscriptions_owner_write on public.subscriptions;
create policy subscriptions_owner_write on public.subscriptions
for all using (public.is_account_owner(account_id))
with check (public.is_account_owner(account_id));

drop policy if exists billing_events_owner_select on public.billing_events;
create policy billing_events_owner_select on public.billing_events
for select using (public.is_account_owner(account_id));

drop policy if exists audit_logs_owner_select on public.audit_logs;
create policy audit_logs_owner_select on public.audit_logs
for select using (public.is_account_owner(account_id));
