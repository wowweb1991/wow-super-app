-- Run in Supabase SQL Editor. Uses authenticated user ownership and RLS.
create extension if not exists pgcrypto;
create table if not exists public.products (id uuid primary key default gen_random_uuid(),user_id uuid not null references auth.users(id) on delete cascade,title text not null,description text not null,price numeric(12,2) not null check(price>=0),image_url text default '',contact text not null,created_at timestamptz default now());
create table if not exists public.posts (id uuid primary key default gen_random_uuid(),user_id uuid not null references auth.users(id) on delete cascade,body text not null,created_at timestamptz default now());
create table if not exists public.comments (id uuid primary key default gen_random_uuid(),user_id uuid not null references auth.users(id) on delete cascade,post_id uuid not null references public.posts(id) on delete cascade,body text not null,created_at timestamptz default now());
create table if not exists public.likes (id uuid primary key default gen_random_uuid(),user_id uuid not null references auth.users(id) on delete cascade,post_id uuid not null references public.posts(id) on delete cascade,created_at timestamptz default now(),unique(user_id,post_id));
create table if not exists public.services (id uuid primary key default gen_random_uuid(),user_id uuid not null references auth.users(id) on delete cascade,title text not null,description text not null,contact text not null,created_at timestamptz default now());
create table if not exists public.inquiries (id uuid primary key default gen_random_uuid(),user_id uuid not null references auth.users(id) on delete cascade,service_id uuid not null references public.services(id) on delete cascade,message text not null,created_at timestamptz default now());
alter table public.products enable row level security;
alter table public.posts enable row level security;
alter table public.comments enable row level security;
alter table public.likes enable row level security;
alter table public.services enable row level security;
alter table public.inquiries enable row level security;
-- Safe to rerun policies
DO $$ DECLARE t text; BEGIN FOREACH t IN ARRAY ARRAY['products','posts','comments','likes','services'] LOOP
EXECUTE format('drop policy if exists read_authenticated on public.%I',t);
EXECUTE format('create policy read_authenticated on public.%I for select to authenticated using (true)',t);
EXECUTE format('drop policy if exists insert_own on public.%I',t);
EXECUTE format('create policy insert_own on public.%I for insert to authenticated with check (user_id = (select auth.uid()))',t);
EXECUTE format('drop policy if exists delete_own on public.%I',t);
EXECUTE format('create policy delete_own on public.%I for delete to authenticated using (user_id = (select auth.uid()))',t);
END LOOP; END $$;
drop policy if exists inquiry_read on public.inquiries;
create policy inquiry_read on public.inquiries for select to authenticated using (user_id=(select auth.uid()) or exists(select 1 from public.services s where s.id=service_id and s.user_id=(select auth.uid())));
drop policy if exists inquiry_insert on public.inquiries;
create policy inquiry_insert on public.inquiries for insert to authenticated with check (user_id=(select auth.uid()));
