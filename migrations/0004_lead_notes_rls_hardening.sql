alter table public.lead_notes enable row level security;

drop policy if exists lead_notes_member_select on public.lead_notes;
drop policy if exists lead_notes_member_insert on public.lead_notes;
drop policy if exists lead_notes_account_isolation on public.lead_notes;

create policy lead_notes_account_isolation on public.lead_notes
for all
using (
  account_id = nullif(current_setting('app.current_account_id', true), '')::uuid
)
with check (
  account_id = nullif(current_setting('app.current_account_id', true), '')::uuid
);
