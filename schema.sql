-- Ballon d’Or Battle — schéma Supabase pour l'application Streamlit
-- À exécuter dans Supabase > SQL Editor.
-- Cette version remplace l'ancien schéma à 2 joueurs (slot 1/2).
-- Avant d'exécuter, exporte les anciennes données si tu souhaites les conserver.

create extension if not exists pgcrypto;

create table if not exists public.profiles (
    id uuid primary key default gen_random_uuid(),
    nickname text not null,
    nickname_key text not null unique,
    pin_hash text not null,
    created_at timestamptz not null default now()
);

create table if not exists public.games (
    id uuid primary key default gen_random_uuid(),
    code text not null unique,
    name text not null,
    admin_player_id uuid not null references public.profiles(id) on delete restrict,
    status text not null default 'open' check (status in ('open', 'closed')),
    created_at timestamptz not null default now(),
    closed_at timestamptz
);

create table if not exists public.game_players (
    id uuid primary key default gen_random_uuid(),
    game_id uuid not null references public.games(id) on delete cascade,
    player_id uuid not null references public.profiles(id) on delete cascade,
    joined_at timestamptz not null default now(),
    unique (game_id, player_id)
);

create table if not exists public.picks (
    id uuid primary key default gen_random_uuid(),
    game_id uuid not null references public.games(id) on delete cascade,
    player_id uuid not null references public.profiles(id) on delete cascade,
    predicted_rank integer not null check (predicted_rank between 1 and 10),
    nominee_name text not null,
    created_at timestamptz not null default now(),
    unique (game_id, player_id, predicted_rank),
    unique (game_id, player_id, nominee_name)
);

create table if not exists public.official_results (
    id uuid primary key default gen_random_uuid(),
    game_id uuid not null references public.games(id) on delete cascade,
    rank integer not null check (rank between 1 and 10),
    nominee_name text not null,
    updated_at timestamptz not null default now(),
    unique (game_id, rank),
    unique (game_id, nominee_name)
);

create index if not exists game_players_player_id_idx on public.game_players(player_id);
create index if not exists game_players_game_id_idx on public.game_players(game_id);
create index if not exists picks_game_player_idx on public.picks(game_id, player_id);
create index if not exists official_results_game_idx on public.official_results(game_id);

-- Important security model:
-- The Streamlit server uses SUPABASE_SERVICE_ROLE_KEY, stored only in Streamlit Secrets.
-- The service-role key bypasses RLS, so app.py performs profile/PIN checks and admin checks.
-- RLS prevents direct access through the public anon key. Never expose the service-role key
-- in a repository, browser code, screenshot, or message.
alter table public.profiles enable row level security;
alter table public.games enable row level security;
alter table public.game_players enable row level security;
alter table public.picks enable row level security;
alter table public.official_results enable row level security;

-- Remove public/anon/authenticated table privileges; server-side service role still works.
revoke all on table public.profiles from anon, authenticated;
revoke all on table public.games from anon, authenticated;
revoke all on table public.game_players from anon, authenticated;
revoke all on table public.picks from anon, authenticated;
revoke all on table public.official_results from anon, authenticated;
