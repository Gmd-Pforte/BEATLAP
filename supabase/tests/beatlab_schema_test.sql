-- Lokale Tests für den Beatlab-Datenbankentwurf.
-- Ablauf: supabase_stub.sql → Migration → diese Datei (psql -v ON_ERROR_STOP=1).
-- Jede Prüfung bricht bei einem Fehler ab; am Ende steht „ALLE TESTS BESTANDEN“.

\set peter  '11111111-1111-1111-1111-111111111111'
\set fremd  '22222222-2222-2222-2222-222222222222'

insert into auth.users values (:'peter'), (:'fremd');

-- Kleine Hilfe: erwartet, dass ein Befehl mit Fehler scheitert
create or replace function pg_temp.muss_scheitern(sql text, was text) returns void language plpgsql as $$
begin
  begin
    execute sql;
  exception when others then
    raise notice 'OK (abgelehnt): % → %', was, sqlerrm;
    return;
  end;
  raise exception 'FEHLER: % wurde NICHT abgelehnt', was;
end $$;
grant execute on function pg_temp.muss_scheitern(text, text) to anon, authenticated;

-- ===================== Peter legt ein Projekt an =====================
set role authenticated;
select set_config('request.jwt.claim.sub', :'peter', false);

insert into public.beatlab_projects (id, title, bpm, music_key, scale, style, state)
values ('aaaaaaaa-0000-0000-0000-000000000001', 'Erster Beat', 90, 9, 'minor', 'Boom Bap',
        '{"bpm":90,"pats":[],"score":{"format":"PS-Beatlap-Score-1","tracks":[{"name":"Klavier","notes":[]}]}}');

do $$ begin
  assert (select owner_id from public.beatlab_projects) = auth.uid(), 'owner_id automatisch gesetzt';
  assert (select revision from public.beatlab_projects) = 1, 'Start-Revision 1';
  raise notice 'OK: Projekt angelegt, Eigentümer automatisch Peter';
end $$;

-- ===================== Songplan-Blöcke =====================
insert into public.beatlab_song_sections (project_id, position, kind, name, bars, energy) values
  ('aaaaaaaa-0000-0000-0000-000000000001', 0, 'intro',  'Intro',   4, 2),
  ('aaaaaaaa-0000-0000-0000-000000000001', 1, 'verse',  'Strophe', 8, 4),
  ('aaaaaaaa-0000-0000-0000-000000000001', 2, 'chorus', 'Refrain', 8, 8);

-- Umsortieren in einer Transaktion (Positionen tauschen) muss klappen
begin;
update public.beatlab_song_sections set position = 1 where name = 'Refrain';
update public.beatlab_song_sections set position = 2 where name = 'Strophe';
commit;

do $$ begin
  assert (select string_agg(name, ',' order by position) from public.beatlab_song_sections) = 'Intro,Refrain,Strophe',
    'Blöcke umsortiert';
  raise notice 'OK: Songplan-Blöcke angelegt und umsortiert';
end $$;

select pg_temp.muss_scheitern($$insert into public.beatlab_song_sections (project_id, position, name, energy)
  values ('aaaaaaaa-0000-0000-0000-000000000001', 5, 'Zu laut', 11)$$, 'Energie über 10');

-- ===================== Motiv =====================
insert into public.beatlab_motifs (id, project_id, name, music_key, scale, length_beats, notes, favorite)
values ('cccccccc-0000-0000-0000-000000000001', 'aaaaaaaa-0000-0000-0000-000000000001', 'Hook-Melodie', 9, 'minor', 8,
        '[{"pitch":"A4","start":0,"duration":1,"velocity":0.8},{"pitch":"C5","start":1,"duration":1,"velocity":0.8}]', true);
update public.beatlab_song_sections set motif_id = 'cccccccc-0000-0000-0000-000000000001' where kind = 'chorus';
do $$ begin raise notice 'OK: Motiv gespeichert und an Refrain angeheftet'; end $$;

-- ===================== Autosave mit Revision =====================
do $$
declare r int;
begin
  r := public.beatlab_save_project('aaaaaaaa-0000-0000-0000-000000000001', 1, '{"bpm":92}'::jsonb, p_bpm => 92::smallint, p_saved_from => 'Samsung');
  assert r = 2, 'Revision 2 nach erstem Speichern';
  assert (select count(*) from public.beatlab_project_versions) = 1, 'erste automatische Version angelegt';
  assert (select jsonb_array_length(sections) from public.beatlab_project_versions) = 3, 'Songplan in Version enthalten';

  r := public.beatlab_save_project('aaaaaaaa-0000-0000-0000-000000000001', 2, '{"bpm":93}'::jsonb);
  assert r = 3, 'Revision 3';
  assert (select count(*) from public.beatlab_project_versions) = 1, 'innerhalb 10 Min. keine neue Auto-Version';

  r := public.beatlab_save_project('aaaaaaaa-0000-0000-0000-000000000001', 3, '{"bpm":94}'::jsonb, p_snapshot_label => 'Refrain fertig');
  assert (select count(*) from public.beatlab_project_versions where not is_auto and label = 'Refrain fertig') = 1, 'gemerkte Version';
  assert (select bpm from public.beatlab_projects) = 92, 'BPM-Spalte aus erstem Speichern';
  raise notice 'OK: Autosave zählt Revision hoch und legt Versionen an';
end $$;

-- Veralteter Stand von einem zweiten Gerät darf NICHT überschreiben
select pg_temp.muss_scheitern($$select public.beatlab_save_project('aaaaaaaa-0000-0000-0000-000000000001', 2, '{"alt":true}'::jsonb)$$,
  'Speichern mit veralteter Revision (Konflikt)');

-- Zustand und Revision nicht direkt änderbar, nur über save_project
select pg_temp.muss_scheitern($$update public.beatlab_projects set state = '{}'::jsonb$$, 'direktes Ändern von state');
select pg_temp.muss_scheitern($$update public.beatlab_projects set revision = 99$$, 'direktes Ändern von revision');
select pg_temp.muss_scheitern($$update public.beatlab_projects set owner_id = gen_random_uuid()$$, 'Eigentümer ändern');
update public.beatlab_projects set title = 'Erster Beat (neu)';
do $$ begin raise notice 'OK: Titel direkt änderbar'; end $$;

-- Versionen sind unveränderlich
select pg_temp.muss_scheitern($$update public.beatlab_project_versions set label = 'geschummelt'$$, 'Version nachträglich ändern');

-- ===================== Aufräumen alter Auto-Versionen =====================
reset role;
insert into public.beatlab_project_versions (project_id, owner_id, revision, is_auto, state, created_at)
select 'aaaaaaaa-0000-0000-0000-000000000001', :'peter', g, true, '{}'::jsonb, now() - interval '2 days' + g * interval '1 minute'
from generate_series(1, 60) g;
update public.beatlab_project_versions set created_at = now() - interval '1 hour' where is_auto and revision = 2;
set role authenticated;
select public.beatlab_save_project('aaaaaaaa-0000-0000-0000-000000000001', 4, '{"bpm":95}'::jsonb);
do $$ begin
  assert (select count(*) from public.beatlab_project_versions where is_auto) = 50, 'max. 50 Auto-Versionen';
  assert (select count(*) from public.beatlab_project_versions where not is_auto) = 1, 'gemerkte Version bleibt';
  raise notice 'OK: Nur die letzten 50 automatischen Versionen bleiben, gemerkte bleiben immer';
end $$;

-- ===================== Freigabe-Link =====================
insert into public.beatlab_shares (version_id)
select id from public.beatlab_project_versions where label = 'Refrain fertig';

-- ===================== Fremder Nutzer =====================
select set_config('request.jwt.claim.sub', :'fremd', false);
do $$ begin
  assert (select count(*) from public.beatlab_projects) = 0, 'Fremder sieht keine Projekte';
  assert (select count(*) from public.beatlab_project_versions) = 0, 'Fremder sieht keine Versionen';
  assert (select count(*) from public.beatlab_shares) = 0, 'Fremder sieht keine Freigaben';
  raise notice 'OK: Fremder Nutzer sieht nichts von Peter';
end $$;
select pg_temp.muss_scheitern($$select public.beatlab_save_project('aaaaaaaa-0000-0000-0000-000000000001', 5, '{"gehackt":true}'::jsonb)$$,
  'Fremder speichert in Peters Projekt');
select pg_temp.muss_scheitern($$insert into public.beatlab_song_sections (project_id, position, name)
  values ('aaaaaaaa-0000-0000-0000-000000000001', 9, 'Untergeschoben')$$, 'Fremder hängt Block an Peters Projekt');
select pg_temp.muss_scheitern($$insert into public.beatlab_motifs (project_id, name, length_beats, notes)
  values ('aaaaaaaa-0000-0000-0000-000000000001', 'x', 1, '[{"pitch":"C4"}]')$$, 'Fremder hängt Motiv an Peters Projekt');

-- ===================== Nicht angemeldet (anon) =====================
reset role;
create temp table share_token as select token from public.beatlab_shares;
grant select on share_token to anon;
set role anon;
select set_config('request.jwt.claim.sub', '', false);
select pg_temp.muss_scheitern($$select * from public.beatlab_projects$$, 'anon liest Projekte');
select pg_temp.muss_scheitern($$select public.beatlab_save_project('aaaaaaaa-0000-0000-0000-000000000001', 5, '{}'::jsonb)$$, 'anon speichert');
do $$ begin
  assert (select count(*) from public.beatlab_get_shared((select token from share_token))) = 1, 'gültiger Link liefert Beat';
  assert (select title from public.beatlab_get_shared((select token from share_token))) = 'Erster Beat (neu)', 'Titel stimmt';
  assert (select count(*) from public.beatlab_get_shared('falsch')) = 0, 'falscher Token liefert nichts';
  raise notice 'OK: Geteilter Link funktioniert ohne Login, falscher Token liefert nichts';
end $$;

-- Widerrufen → Link tot
reset role;
set role authenticated;
select set_config('request.jwt.claim.sub', :'peter', false);
update public.beatlab_shares set revoked = true;
set role anon;
do $$ begin
  assert (select count(*) from public.beatlab_get_shared((select token from share_token))) = 0, 'widerrufener Link liefert nichts';
  raise notice 'OK: Widerrufener Link funktioniert nicht mehr';
end $$;

-- ===================== Löschen kaskadiert =====================
reset role;
set role authenticated;
select set_config('request.jwt.claim.sub', :'peter', false);
delete from public.beatlab_projects;
do $$ begin
  assert (select count(*) from public.beatlab_song_sections) = 0, 'Blöcke mitgelöscht';
  assert (select count(*) from public.beatlab_project_versions) = 0, 'Versionen mitgelöscht';
  assert (select count(*) from public.beatlab_motifs) = 1, 'Motiv bleibt in der Bibliothek erhalten';
  assert (select project_id from public.beatlab_motifs) is null, 'Motiv-Herkunft auf null gesetzt';
  raise notice 'OK: Projekt löschen räumt auf, Motive bleiben in der Bibliothek';
end $$;

reset role;
do $$ begin raise notice '======== ALLE TESTS BESTANDEN ========'; end $$;
