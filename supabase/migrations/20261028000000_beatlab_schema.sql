-- Beatlab – Datenbankentwurf für Supabase-Projekt „Pforte Nexus“
-- Entwurf von Claude, Review durch ChatGPT, Freigabe durch Peter.
-- NOCH NICHT ANGEWENDET.
--
-- Grundidee
--   * Der komplette App-Zustand (Objekt `P` in index.html, inkl. Notensong
--     „PS-Beatlap-Score-1“ mit Spuren und Noten) wird als JSON gespeichert.
--     So bleibt die App die Quelle für das Format und wir müssen nicht jede
--     Formatänderung in Tabellen nachziehen.
--   * Nur was wir abfragen, sortieren oder einzeln bearbeiten wollen, bekommt
--     eigene Tabellen: Projekte, Songplan-Blöcke, Versionen, Motive, Freigaben.
--   * Jede Zeile gehört genau einem Supabase-Auth-Nutzer (Peter). RLS erlaubt
--     nur dem Eigentümer Zugriff. Geteilte Links laufen über eine Funktion.

begin;

-- ---------------------------------------------------------------------------
-- Hilfsfunktion: updated_at automatisch setzen
-- ---------------------------------------------------------------------------
create or replace function public.beatlab_touch_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

-- ---------------------------------------------------------------------------
-- 1. Projekte (mit Autosave-Stand)
-- ---------------------------------------------------------------------------
create table public.beatlab_projects (
  id            uuid primary key default gen_random_uuid(),
  owner_id      uuid not null default auth.uid() references auth.users (id) on delete cascade,
  title         text not null default 'Unbenannter Beat'
                check (char_length(title) between 1 and 90),
  bpm           smallint check (bpm between 40 and 200),
  music_key     smallint check (music_key between 0 and 11),   -- 0 = C … 11 = H
  scale         text check (char_length(scale) <= 30),
  style         text check (char_length(style) <= 40),         -- z. B. „Boom Bap“, „Trap“
  -- Autosave: aktueller Arbeitsstand der App (Objekt P)
  state         jsonb not null default '{}'::jsonb
                check (jsonb_typeof(state) = 'object'
                       and octet_length(state::text) <= 2000000), -- max. ca. 2 MB
  state_format  text not null default 'beatlab-project-1',
  revision      integer not null default 1,                  -- zählt bei jedem Speichern hoch
  saved_from    text check (char_length(saved_from) <= 60),  -- Gerät, z. B. „Samsung“
  archived      boolean not null default false,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

create index beatlab_projects_owner_idx on public.beatlab_projects (owner_id, archived, updated_at desc);

create trigger beatlab_projects_touch
  before update on public.beatlab_projects
  for each row execute function public.beatlab_touch_updated_at();

-- ---------------------------------------------------------------------------
-- 2. Songplan-Blöcke (Intro, Strophe, Refrain … mit Energie 1–10)
-- ---------------------------------------------------------------------------
create table public.beatlab_song_sections (
  id          uuid primary key default gen_random_uuid(),
  project_id  uuid not null references public.beatlab_projects (id) on delete cascade,
  owner_id    uuid not null default auth.uid() references auth.users (id) on delete cascade,
  position    smallint not null check (position between 0 and 63),
  kind        text not null default 'custom'
              check (kind in ('intro','verse','prechorus','chorus','bridge','break','drop','outro','custom')),
  name        text not null check (char_length(name) between 1 and 40),
  bars        smallint not null default 8 check (bars between 1 and 64),
  energy      smallint not null default 5 check (energy between 1 and 10),
  color       text check (color ~ '^#[0-9a-fA-F]{6}$'),
  motif_id    uuid,                                           -- roter Faden, siehe Motive
  settings    jsonb not null default '{}'::jsonb              -- z. B. Instrumente an/aus, Variation
              check (jsonb_typeof(settings) = 'object' and octet_length(settings::text) <= 20000),
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  unique (project_id, position) deferrable initially deferred -- Blöcke umsortieren in einem Schritt
);

create index beatlab_song_sections_owner_idx on public.beatlab_song_sections (owner_id);

create trigger beatlab_song_sections_touch
  before update on public.beatlab_song_sections
  for each row execute function public.beatlab_touch_updated_at();

-- ---------------------------------------------------------------------------
-- 3. Versionen (Schnappschüsse für Verlauf und Wiederherstellen)
-- ---------------------------------------------------------------------------
create table public.beatlab_project_versions (
  id          uuid primary key default gen_random_uuid(),
  project_id  uuid not null references public.beatlab_projects (id) on delete cascade,
  owner_id    uuid not null default auth.uid() references auth.users (id) on delete cascade,
  revision    integer not null,                               -- Projekt-Revision zum Zeitpunkt
  label       text check (char_length(label) <= 80),          -- z. B. „Refrain fertig“
  is_auto     boolean not null default true,                  -- automatisch oder von Peter gemerkt
  state       jsonb not null
              check (jsonb_typeof(state) = 'object' and octet_length(state::text) <= 2000000),
  sections    jsonb not null default '[]'::jsonb              -- Songplan zum Zeitpunkt
              check (jsonb_typeof(sections) = 'array'),
  created_at  timestamptz not null default now()
);

create index beatlab_versions_project_idx on public.beatlab_project_versions (project_id, created_at desc);
create index beatlab_versions_owner_idx on public.beatlab_project_versions (owner_id);

-- ---------------------------------------------------------------------------
-- 4. Motive (Melodien, die Peter gefallen – projektübergreifend nutzbar)
-- ---------------------------------------------------------------------------
create table public.beatlab_motifs (
  id          uuid primary key default gen_random_uuid(),
  owner_id    uuid not null default auth.uid() references auth.users (id) on delete cascade,
  project_id  uuid references public.beatlab_projects (id) on delete set null, -- Herkunft, optional
  name        text not null check (char_length(name) between 1 and 60),
  music_key   smallint check (music_key between 0 and 11),
  scale       text check (char_length(scale) <= 30),
  bpm         smallint check (bpm between 40 and 200),
  length_beats numeric(6,2) not null check (length_beats > 0 and length_beats <= 64),
  notes       jsonb not null                                  -- [{pitch,start,duration,velocity}]
              check (jsonb_typeof(notes) = 'array' and jsonb_array_length(notes) between 1 and 512),
  favorite    boolean not null default false,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create index beatlab_motifs_owner_idx on public.beatlab_motifs (owner_id, favorite desc, created_at desc);
create index beatlab_motifs_project_idx on public.beatlab_motifs (project_id);

create trigger beatlab_motifs_touch
  before update on public.beatlab_motifs
  for each row execute function public.beatlab_touch_updated_at();

alter table public.beatlab_song_sections
  add constraint beatlab_song_sections_motif_fk
  foreign key (motif_id) references public.beatlab_motifs (id) on delete set null;

create index beatlab_song_sections_motif_idx on public.beatlab_song_sections (motif_id);

-- ---------------------------------------------------------------------------
-- 5. Freigabe-Links (Beat im Browser teilen, nur lesen)
-- ---------------------------------------------------------------------------
create table public.beatlab_shares (
  id          uuid primary key default gen_random_uuid(),
  owner_id    uuid not null default auth.uid() references auth.users (id) on delete cascade,
  version_id  uuid not null references public.beatlab_project_versions (id) on delete cascade,
  -- 64 Hex-Zeichen, nicht erratbar
  token       text not null unique default replace(gen_random_uuid()::text || gen_random_uuid()::text, '-', ''),
  expires_at  timestamptz,                                    -- null = kein Ablauf
  revoked     boolean not null default false,
  created_at  timestamptz not null default now()
);

create index beatlab_shares_owner_idx on public.beatlab_shares (owner_id);
create index beatlab_shares_version_idx on public.beatlab_shares (version_id);

-- ---------------------------------------------------------------------------
-- Eigentum über Tabellen hinweg absichern
-- (Kind-Zeilen dürfen nur an eigene Projekte/Versionen gehängt werden)
-- ---------------------------------------------------------------------------
create or replace function public.beatlab_check_parent_owner()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  parent_owner uuid;
begin
  if tg_table_name = 'beatlab_shares' then
    select v.owner_id into parent_owner from public.beatlab_project_versions v where v.id = new.version_id;
  elsif new.project_id is null then
    return new;  -- Motiv ohne Projekt
  else
    select p.owner_id into parent_owner from public.beatlab_projects p where p.id = new.project_id;
  end if;

  if parent_owner is null or parent_owner <> new.owner_id then
    raise exception 'Zugehöriges Projekt/Version gehört nicht diesem Nutzer.' using errcode = '42501';
  end if;

  if tg_table_name = 'beatlab_song_sections' then
    if new.motif_id is not null
       and not exists (select 1 from public.beatlab_motifs m where m.id = new.motif_id and m.owner_id = new.owner_id) then
      raise exception 'Motiv gehört nicht diesem Nutzer.' using errcode = '42501';
    end if;
  end if;
  return new;
end;
$$;

create trigger beatlab_sections_owner_check before insert or update on public.beatlab_song_sections
  for each row execute function public.beatlab_check_parent_owner();
create trigger beatlab_versions_owner_check before insert or update on public.beatlab_project_versions
  for each row execute function public.beatlab_check_parent_owner();
create trigger beatlab_motifs_owner_check before insert or update on public.beatlab_motifs
  for each row execute function public.beatlab_check_parent_owner();
create trigger beatlab_shares_owner_check before insert or update on public.beatlab_shares
  for each row execute function public.beatlab_check_parent_owner();

-- ---------------------------------------------------------------------------
-- Row Level Security: nur der Eigentümer
-- ---------------------------------------------------------------------------
alter table public.beatlab_projects         enable row level security;
alter table public.beatlab_song_sections    enable row level security;
alter table public.beatlab_project_versions enable row level security;
alter table public.beatlab_motifs           enable row level security;
alter table public.beatlab_shares           enable row level security;

create policy "Eigene Projekte" on public.beatlab_projects
  for all to authenticated
  using (owner_id = (select auth.uid()))
  with check (owner_id = (select auth.uid()));

create policy "Eigene Songplan-Blöcke" on public.beatlab_song_sections
  for all to authenticated
  using (owner_id = (select auth.uid()))
  with check (owner_id = (select auth.uid()));

-- Versionen: lesen, anlegen, löschen – aber nie nachträglich verändern
create policy "Eigene Versionen lesen" on public.beatlab_project_versions
  for select to authenticated using (owner_id = (select auth.uid()));
create policy "Eigene Versionen anlegen" on public.beatlab_project_versions
  for insert to authenticated with check (owner_id = (select auth.uid()));
create policy "Eigene Versionen löschen" on public.beatlab_project_versions
  for delete to authenticated using (owner_id = (select auth.uid()));

create policy "Eigene Motive" on public.beatlab_motifs
  for all to authenticated
  using (owner_id = (select auth.uid()))
  with check (owner_id = (select auth.uid()));

create policy "Eigene Freigaben" on public.beatlab_shares
  for all to authenticated
  using (owner_id = (select auth.uid()))
  with check (owner_id = (select auth.uid()));

-- ---------------------------------------------------------------------------
-- Rechte für die Daten-API: nur angemeldete Nutzer, anon bekommt nichts
-- ---------------------------------------------------------------------------
revoke all on public.beatlab_projects, public.beatlab_song_sections, public.beatlab_project_versions,
              public.beatlab_motifs, public.beatlab_shares from anon, authenticated;

-- Projekte: Zustand und Revision nur über beatlab_save_project, direkt nur Titel/Archiv
grant select, insert, delete on public.beatlab_projects to authenticated;
grant update (title, archived) on public.beatlab_projects to authenticated;
grant select, insert, update, delete on public.beatlab_song_sections to authenticated;
grant select, insert, delete         on public.beatlab_project_versions to authenticated;
grant select, insert, update, delete on public.beatlab_motifs        to authenticated;
grant select, insert, update, delete on public.beatlab_shares        to authenticated;

revoke execute on function public.beatlab_touch_updated_at()      from public, anon, authenticated;
revoke execute on function public.beatlab_check_parent_owner()    from public, anon, authenticated;

-- ---------------------------------------------------------------------------
-- Autosave mit Konfliktschutz
-- Die App schickt die Revision mit, die sie zuletzt kannte. Hat ein anderes
-- Gerät inzwischen gespeichert, wird NICHT überschrieben (Fehler 40001),
-- die App kann dann fragen, welcher Stand gelten soll.
-- Alle 10 Minuten (bzw. auf Wunsch) entsteht zusätzlich eine Version.
-- ---------------------------------------------------------------------------
create or replace function public.beatlab_save_project(
  p_project_id        uuid,
  p_expected_revision integer,
  p_state             jsonb,
  p_title             text     default null,
  p_bpm               smallint default null,
  p_music_key         smallint default null,
  p_scale             text     default null,
  p_style             text     default null,
  p_saved_from        text     default null,
  p_snapshot_label    text     default null   -- gesetzt = Version „von Peter gemerkt“
)
returns integer
language plpgsql
security definer              -- darf state/revision setzen, prüft Eigentum selbst
set search_path = ''
as $$
declare
  new_revision  integer;
  last_auto     timestamptz;
  uid           uuid := auth.uid();
begin
  if uid is null then
    raise exception 'Nicht angemeldet.' using errcode = '42501';
  end if;
  if octet_length(p_state::text) > 2000000 then
    raise exception 'Projekt ist zu groß (max. ca. 2 MB).' using errcode = '22023';
  end if;

  update public.beatlab_projects p
     set state      = p_state,
         title      = coalesce(p_title, p.title),
         bpm        = coalesce(p_bpm, p.bpm),
         music_key  = coalesce(p_music_key, p.music_key),
         scale      = coalesce(p_scale, p.scale),
         style      = coalesce(p_style, p.style),
         saved_from = coalesce(p_saved_from, p.saved_from),
         revision   = p.revision + 1
   where p.id = p_project_id
     and p.owner_id = uid
     and p.revision = p_expected_revision
  returning p.revision into new_revision;

  if new_revision is null then
    if exists (select 1 from public.beatlab_projects where id = p_project_id and owner_id = uid) then
      raise exception 'Konflikt: Projekt wurde inzwischen auf einem anderen Gerät gespeichert.'
        using errcode = '40001';
    end if;
    raise exception 'Projekt nicht gefunden.' using errcode = 'P0002';
  end if;

  select max(created_at) into last_auto
    from public.beatlab_project_versions
   where project_id = p_project_id and is_auto;

  if p_snapshot_label is not null or last_auto is null or last_auto < now() - interval '10 minutes' then
    insert into public.beatlab_project_versions (project_id, owner_id, revision, label, is_auto, state, sections)
    select p_project_id, p.owner_id, new_revision, p_snapshot_label, p_snapshot_label is null, p_state,
           coalesce((select jsonb_agg(to_jsonb(s) - 'owner_id' - 'project_id' order by s.position)
                       from public.beatlab_song_sections s where s.project_id = p_project_id), '[]'::jsonb)
      from public.beatlab_projects p where p.id = p_project_id;

    -- nur die letzten 50 automatischen Versionen behalten
    delete from public.beatlab_project_versions v
     where v.project_id = p_project_id and v.is_auto
       and v.id not in (select id from public.beatlab_project_versions
                         where project_id = p_project_id and is_auto
                         order by created_at desc limit 50);
  end if;

  return new_revision;
end;
$$;

revoke execute on function public.beatlab_save_project(uuid, integer, jsonb, text, smallint, smallint, text, text, text, text) from public, anon;
grant  execute on function public.beatlab_save_project(uuid, integer, jsonb, text, smallint, smallint, text, text, text, text) to authenticated;

-- ---------------------------------------------------------------------------
-- Geteilten Beat abrufen (ohne Login, nur mit gültigem Token)
-- ---------------------------------------------------------------------------
create or replace function public.beatlab_get_shared(p_token text)
returns table (title text, bpm smallint, state jsonb, sections jsonb, created_at timestamptz)
language sql
stable
security definer
set search_path = ''
as $$
  select p.title, p.bpm, v.state, v.sections, v.created_at
    from public.beatlab_shares s
    join public.beatlab_project_versions v on v.id = s.version_id
    join public.beatlab_projects p on p.id = v.project_id
   where s.token = p_token
     and char_length(p_token) = 64
     and not s.revoked
     and (s.expires_at is null or s.expires_at > now());
$$;

revoke execute on function public.beatlab_get_shared(text) from public;
grant  execute on function public.beatlab_get_shared(text) to anon, authenticated;

commit;
