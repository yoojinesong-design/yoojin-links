-- Music Persona Hub — Supabase Schema
-- Run this in your Supabase SQL Editor to set up the database

-- Enable UUID generation
create extension if not exists "uuid-ossp";

-- Users table (extends Supabase auth.users)
create table public.profiles (
  id uuid references auth.users on delete cascade primary key,
  display_name text,
  avatar_url text,
  distributor text default 'distrokid',
  plan text default 'free',
  created_at timestamptz default now()
);

alter table public.profiles enable row level security;
create policy "Users can view own profile" on public.profiles
  for select using (auth.uid() = id);
create policy "Users can update own profile" on public.profiles
  for update using (auth.uid() = id);

-- Personas (artist identities)
create table public.personas (
  id uuid default uuid_generate_v4() primary key,
  user_id uuid references public.profiles(id) on delete cascade not null,
  name text not null,
  genre text,
  subgenre text,
  bio text,
  avatar_url text,
  cover_style text,
  social_links jsonb default '{}',
  distributor_slot text,
  ai_default_disclosure jsonb default '{}',
  color text default '#7C3AED',
  is_active boolean default true,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

alter table public.personas enable row level security;
create policy "Users can CRUD own personas" on public.personas
  for all using (auth.uid() = user_id);

create index idx_personas_user on public.personas(user_id);

-- Releases
create table public.releases (
  id uuid default uuid_generate_v4() primary key,
  user_id uuid references public.profiles(id) on delete cascade not null,
  persona_id uuid references public.personas(id) on delete cascade not null,
  title text not null,
  release_type text default 'single',
  release_date date,
  status text default 'draft',
  platforms jsonb default '["spotify","apple_music","youtube_music"]',
  ai_disclosure jsonb default '{}',
  isrc text,
  upc text,
  notes text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

alter table public.releases enable row level security;
create policy "Users can CRUD own releases" on public.releases
  for all using (auth.uid() = user_id);

create index idx_releases_user on public.releases(user_id);
create index idx_releases_persona on public.releases(persona_id);
create index idx_releases_date on public.releases(release_date);

-- Revenue entries (parsed from CSV uploads)
create table public.revenue (
  id uuid default uuid_generate_v4() primary key,
  user_id uuid references public.profiles(id) on delete cascade not null,
  persona_id uuid references public.personas(id) on delete set null,
  period text not null,
  platform text,
  track_title text,
  streams bigint default 0,
  revenue_usd numeric(10,4) default 0,
  currency text default 'USD',
  source_file text,
  created_at timestamptz default now()
);

alter table public.revenue enable row level security;
create policy "Users can CRUD own revenue" on public.revenue
  for all using (auth.uid() = user_id);

create index idx_revenue_user on public.revenue(user_id);
create index idx_revenue_persona on public.revenue(persona_id);

-- AI Disclosure log (compliance audit trail)
create table public.ai_disclosures (
  id uuid default uuid_generate_v4() primary key,
  user_id uuid references public.profiles(id) on delete cascade not null,
  release_id uuid references public.releases(id) on delete cascade not null,
  ddex_is_ai_generated boolean default false,
  ddex_ai_component_type text[],
  ddex_ai_training_disclosure text,
  eu_article50_compliant boolean default false,
  c2pa_watermark_present boolean default false,
  spotify_ai_credit_opted boolean default false,
  platform_disclosures jsonb default '{}',
  verified_at timestamptz,
  created_at timestamptz default now()
);

alter table public.ai_disclosures enable row level security;
create policy "Users can CRUD own disclosures" on public.ai_disclosures
  for all using (auth.uid() = user_id);

-- Function to auto-create profile on signup
create or replace function public.handle_new_user()
returns trigger as $$
begin
  insert into public.profiles (id, display_name, avatar_url)
  values (
    new.id,
    coalesce(new.raw_user_meta_data->>'full_name', new.email),
    new.raw_user_meta_data->>'avatar_url'
  );
  return new;
end;
$$ language plpgsql security definer;

create or replace trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();
