-- DocuVision trial PoC schema (RLS-ready for Phase 1a)
-- Apply via Supabase SQL editor or: supabase db push

create extension if not exists "pgcrypto";

create table if not exists public.documents (
  id uuid primary key default gen_random_uuid(),
  job_id text not null,
  filename text not null default '',
  status text not null default 'pending_validation',
  raw_result jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.transactions (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references public.documents(id) on delete cascade,
  row_index int not null default 0,
  payload jsonb not null default '{}'::jsonb,
  internal_code text,
  created_at timestamptz not null default now()
);

create index if not exists idx_transactions_document_id on public.transactions(document_id);
create index if not exists idx_documents_created_at on public.documents(created_at desc);

alter table public.documents enable row level security;
alter table public.transactions enable row level security;

-- Phase 1a no-login dashboard: read-only anon access (adjust for production)
drop policy if exists "anon_read_documents" on public.documents;
create policy "anon_read_documents"
  on public.documents for select
  to anon
  using (true);

drop policy if exists "anon_read_transactions" on public.transactions;
create policy "anon_read_transactions"
  on public.transactions for select
  to anon
  using (true);

drop policy if exists "service_insert_documents" on public.documents;
create policy "service_insert_documents"
  on public.documents for insert
  to service_role
  with check (true);

drop policy if exists "service_insert_transactions" on public.transactions;
create policy "service_insert_transactions"
  on public.transactions for insert
  to service_role
  with check (true);

create or replace view public.validation_dashboard as
select
  d.id as document_id,
  d.filename,
  d.status,
  d.created_at,
  count(t.id) as transaction_count
from public.documents d
left join public.transactions t on t.document_id = d.id
group by d.id, d.filename, d.status, d.created_at
order by d.created_at desc;
