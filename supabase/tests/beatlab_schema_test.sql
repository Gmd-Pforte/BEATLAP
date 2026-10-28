-- Lokale Tests für den Beatlab-Datenbankentwurf.
-- Ablauf: supabase_stub.sql → Migration → diese Datei (psql -v ON_ERROR_STOP=1).
-- Jede Prüfung bricht bei einem Fehler ab; am Ende steht „ALLE TESTS BESTANDEN“.

\set peter  '11111111-1111-1111-1111-111111111111'
\set fremd  '22222222-2222-2222-2222-222222222222'

insert into auth.users values (:'peter'), (:'fremd');

-- Hilfe: erwartet, dass ein Befehl abgelehnt wird
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

create temp table t (name text primary key, val text);
grant all on t to anon, authenticated;

-- ===================== Peter legt ein Projekt an =====================
set role authenticated;
select set_config('request.jwt.claim.sub', :'peter', false);

-- Direktes Anlegen (mit manipulierter Revision) ist gesperrt
select pg_temp.muss_scheitern($$insert into public.beatlab_projects (title, state, revision) values ('Trick', '{}', 999)$$,
  'Projekt direkt anlegen mit Revision 999');

insert into t
select 'projekt', project_id::text from public.beatlab_create_project(
  'Erster Beat',
  '{"bpm":90,"pats":[],"sampleNames":{"kick":"privat_aufnahme.wav"},"score":{"format":"PS-Beatlap-Score-1","tracks":[{"name":"Klavier","notes":[]}]}}',
  '[{"kind":"intro","name":"Intro","bars":4,"energy":2},
    {"kind":"verse","name":"Strophe","bars":8,"energy":4},
    {"kind":"chorus","name":"Refrain","bars":8,"energy":8}]',
  p_bpm => 90::smallint, p_music_key => 9::smallint, p_scale => 'minor', p_style => 'Boom Bap', p_saved_from => 'Samsung');

do $$ begin
  assert (select owner_id from public.beatlab_projects) = auth.uid(), 'Eigentümer Peter';
  assert (select revision from public.beatlab_projects) = 1, 'Start-Revision immer 1';
  assert (select string_agg(name, ',' order by position) from public.beatlab_song_sections) = 'Intro,Strophe,Refrain', 'Songplan angelegt';
  assert (select count(*) from public.beatlab_project_versions) = 1, 'erste Version sofort angelegt';
  raise notice 'OK: Projekt über Funktion angelegt (Revision 1, Songplan, erste Version)';
end $$;

select pg_temp.muss_scheitern($$select public.beatlab_create_project('x', '[]'::jsonb)$$, 'Zustand ist kein Objekt');
select pg_temp.muss_scheitern($$select public.beatlab_create_project('x', '{"score":{"format":"fremd"}}'::jsonb)$$, 'falsches Notensong-Format');
select pg_temp.muss_scheitern($$select public.beatlab_create_project('x', jsonb_build_object('blob', repeat('x', 2100000)))$$, 'Zustand über 2 MB');

-- ===================== Songplan und Versionen nur lesbar =====================
select pg_temp.muss_scheitern($$update public.beatlab_song_sections set energy = 10$$, 'Songplan direkt ändern');
select pg_temp.muss_scheitern($$delete from public.beatlab_song_sections$$, 'Songplan direkt löschen');
select pg_temp.muss_scheitern(format($$insert into public.beatlab_song_sections (project_id, position, name) values (%L, 9, 'x')$$,
  (select val from t where name = 'projekt')), 'Songplan-Block direkt einfügen');
select pg_temp.muss_scheitern($$update public.beatlab_project_versions set label = 'geschummelt'$$, 'Version ändern');
select pg_temp.muss_scheitern($$delete from public.beatlab_project_versions$$, 'Version löschen');
select pg_temp.muss_scheitern(format($$insert into public.beatlab_project_versions (project_id, revision, state) values (%L, 1, '{}')$$,
  (select val from t where name = 'projekt')), 'Version direkt einfügen');

-- Zustand, Revision, Eigentümer nicht direkt änderbar; Titel schon
select pg_temp.muss_scheitern($$update public.beatlab_projects set state = '{}'::jsonb$$, 'state direkt ändern');
select pg_temp.muss_scheitern($$update public.beatlab_projects set revision = 99$$, 'revision direkt ändern');
select pg_temp.muss_scheitern($$update public.beatlab_projects set owner_id = gen_random_uuid()$$, 'Eigentümer ändern');
update public.beatlab_projects set title = 'Erster Beat (neu)';
do $$ begin raise notice 'OK: Titel direkt änderbar'; end $$;

-- ===================== Motiv =====================
insert into public.beatlab_motifs (id, project_id, name, music_key, scale, length_beats, notes, favorite)
select 'cccccccc-0000-0000-0000-000000000001', val::uuid, 'Hook-Melodie', 9, 'minor', 8,
       '[{"pitch":"A4","start":0,"duration":1,"velocity":0.8},{"pitch":"C5","start":1,"duration":1,"velocity":0.8}]', true
  from t where name = 'projekt';

-- ===================== Autosave: Zustand + Songplan atomar =====================
do $$
declare r int; p uuid := (select val::uuid from t where name = 'projekt');
begin
  -- Refrain nach vorn, Motiv anheften – in einem Schritt mit dem Zustand
  r := public.beatlab_save_project(p, 1, '{"bpm":92}'::jsonb,
         '[{"kind":"intro","name":"Intro","bars":4,"energy":2},
           {"kind":"chorus","name":"Refrain","bars":8,"energy":9,"motif_id":"cccccccc-0000-0000-0000-000000000001"},
           {"kind":"verse","name":"Strophe","bars":8,"energy":4}]'::jsonb,
         p_bpm => 92::smallint);
  assert r = 2, 'Revision 2';
  assert (select string_agg(name, ',' order by position) from public.beatlab_song_sections) = 'Intro,Refrain,Strophe', 'Songplan umsortiert';
  assert (select motif_id from public.beatlab_song_sections where kind = 'chorus') = 'cccccccc-0000-0000-0000-000000000001', 'Motiv angeheftet';

  -- Ohne Songplan speichern lässt Songplan unverändert
  r := public.beatlab_save_project(p, 2, '{"bpm":93}'::jsonb);
  assert r = 3 and (select count(*) from public.beatlab_song_sections) = 3, 'Songplan bleibt bei null';
  assert (select count(*) from public.beatlab_project_versions) = 1, 'innerhalb 10 Min. keine neue Auto-Version';

  r := public.beatlab_save_project(p, 3, '{
      "bpm":94, "swing":20, "key":9, "scale":"minor", "chain":true,
      "sampleNames":{"kick":"privat_aufnahme.wav"},
      "notiz":"GEHEIM-NOTIZ",
      "pats":[{"kick":[1,0,0,0,1,0,0,0,1,0,0,0,1,0,0,0],"snare":["GEHEIM-STEP",0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],"meinespur":[1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1]}],
      "params":{"kick":{"vol":80,"snd":"kickBoom","quelle":"GEHEIM-PFAD"},"lead":{"vol":70,"snd":"C:/Users/Peter/GEHEIM.wav"},"spion":{"vol":1}},
      "rollLengths":{"0":{"3":{"5":2,"x":"GEHEIM-LEN"}},"y":{"1":{"1":1}}},
      "arrangement":[{"pat":0,"bars":4,"name":"Intro","kommentar":"GEHEIM-ARR"}],
      "score":{"format":"PS-Beatlap-Score-1","title":"Song","bpm":94,"beatsPerBar":4,"lengthBeats":8,
               "sections":[{"name":"Intro","start":0,"x":"GEHEIM-SEC"}],
               "tracks":[{"name":"Klavier","instrument":"piano","volume":0.8,"datei":"GEHEIM-TRACK",
                          "notes":[{"pitch":"A3","start":0,"duration":2,"velocity":0.8,"meta":"GEHEIM-NOTE"},
                                   {"pitch":"GEHEIM-PITCH","start":1,"duration":1,"velocity":0.5}]}]},
      "scoreActive":true
    }'::jsonb, p_snapshot_label => 'Refrain fertig');
  assert (select count(*) from public.beatlab_project_versions where not is_auto and label = 'Refrain fertig') = 1, 'gemerkte Version';
  assert (select sections->1->>'name' from public.beatlab_project_versions where label = 'Refrain fertig') = 'Refrain', 'Songplan steckt in der Version';
  raise notice 'OK: Autosave schreibt Zustand und Songplan gemeinsam, Versionen entstehen automatisch';
end $$;

-- Ungültiger Block → GAR NICHTS wird gespeichert (weder Zustand noch Songplan noch Revision)
select pg_temp.muss_scheitern(format($$select public.beatlab_save_project(%L, 4, '{"bpm":150}'::jsonb,
  '[{"name":"Laut","energy":11}]'::jsonb)$$, (select val from t where name = 'projekt')), 'Speichern mit ungültigem Block');
do $$ begin
  assert (select revision from public.beatlab_projects) = 4, 'Revision unverändert';
  assert (select state->>'bpm' from public.beatlab_projects) = '94', 'Zustand unverändert';
  assert (select count(*) from public.beatlab_song_sections) = 3, 'Songplan unverändert';
  raise notice 'OK: Fehler beim Songplan → nichts gespeichert (atomar)';
end $$;

-- Zwei Geräte: Handy speichert Songplan, Tablet hat noch alten Stand → Konflikt, nichts überschrieben
select public.beatlab_save_project((select val::uuid from t where name = 'projekt'), 4, '{"bpm":95}'::jsonb,
  '[{"kind":"intro","name":"Intro (Handy)","energy":3}]'::jsonb, p_saved_from => 'Handy');
select pg_temp.muss_scheitern(format($$select public.beatlab_save_project(%L, 4, '{"bpm":80}'::jsonb,
  '[{"kind":"outro","name":"Outro (Tablet)"}]'::jsonb, p_saved_from => 'Tablet')$$, (select val from t where name = 'projekt')),
  'Tablet speichert veralteten Songplan (Konflikt)');
do $$ begin
  assert (select string_agg(name, ',') from public.beatlab_song_sections) = 'Intro (Handy)', 'Songplan vom Handy bleibt';
  raise notice 'OK: Konkurrierende Songplan-Änderung wird als Konflikt erkannt';
end $$;

-- ===================== Aufräumen alter Auto-Versionen =====================
reset role;
insert into public.beatlab_project_versions (project_id, owner_id, revision, is_auto, state, created_at)
select (select val::uuid from t where name = 'projekt'), :'peter', g, true, '{}'::jsonb,
       now() - interval '2 days' + g * interval '1 minute'
  from generate_series(1, 60) g;
update public.beatlab_project_versions set created_at = now() - interval '3 days' where is_auto and revision = 1 and state <> '{}'::jsonb;
set role authenticated;
select public.beatlab_save_project((select val::uuid from t where name = 'projekt'), 5, '{"bpm":96}'::jsonb);
do $$ begin
  assert (select count(*) from public.beatlab_project_versions where is_auto) = 50, 'max. 50 Auto-Versionen';
  assert (select count(*) from public.beatlab_project_versions where not is_auto) = 1, 'gemerkte Version bleibt';
  raise notice 'OK: Nur die letzten 50 automatischen Versionen bleiben, gemerkte bleiben immer';
end $$;

-- ===================== Freigabe-Link =====================
select pg_temp.muss_scheitern(format($$insert into public.beatlab_shares (version_id, token) values (%L, 'leicht-zu-raten')$$,
  (select id from public.beatlab_project_versions where label = 'Refrain fertig')), 'eigenen (schwachen) Token setzen');
insert into public.beatlab_shares (version_id)
select id from public.beatlab_project_versions where label = 'Refrain fertig';

-- ===================== Fremder Nutzer =====================
select set_config('request.jwt.claim.sub', :'fremd', false);
do $$ begin
  assert (select count(*) from public.beatlab_projects) = 0, 'sieht keine Projekte';
  assert (select count(*) from public.beatlab_song_sections) = 0, 'sieht keine Blöcke';
  assert (select count(*) from public.beatlab_project_versions) = 0, 'sieht keine Versionen';
  assert (select count(*) from public.beatlab_motifs) = 0, 'sieht keine Motive';
  assert (select count(*) from public.beatlab_shares) = 0, 'sieht keine Freigaben';
  raise notice 'OK: Fremder Nutzer sieht nichts von Peter';
end $$;
select pg_temp.muss_scheitern(format($$select public.beatlab_save_project(%L, 6, '{"gehackt":true}'::jsonb)$$,
  (select val from t where name = 'projekt')), 'Fremder speichert in Peters Projekt');
select pg_temp.muss_scheitern(format($$insert into public.beatlab_motifs (project_id, name, length_beats, notes) values (%L, 'x', 1, '[{"pitch":"C4"}]')$$,
  (select val from t where name = 'projekt')), 'Fremder hängt Motiv an Peters Projekt');

-- Fremder legt eigenes Projekt an und versucht, Peters Motiv anzuheften
insert into t select 'fremdprojekt', project_id::text from public.beatlab_create_project('Fremd', '{}'::jsonb);
do $$ begin
  assert (select count(*) from public.beatlab_song_sections) = 0, 'leerer Songplan beim Anlegen erlaubt';
  raise notice 'OK: Neues Projekt mit leerem Songplan erlaubt (wie dokumentiert)';
end $$;
select pg_temp.muss_scheitern(format($$select public.beatlab_save_project(%L, 1, '{}'::jsonb,
  '[{"name":"Klau","motif_id":"cccccccc-0000-0000-0000-000000000001"}]'::jsonb)$$, (select val from t where name = 'fremdprojekt')),
  'Fremder heftet Peters Motiv an');
select pg_temp.muss_scheitern($$select public.beatlab_create_project('Fremd 2', '{}'::jsonb,
  '[{"name":"Klau","motif_id":"cccccccc-0000-0000-0000-000000000001"}]'::jsonb)$$, 'Fremder heftet Peters Motiv beim Anlegen an');
-- Interne Helfer sind auch für angemeldete Nutzer gesperrt (sonst Umgehung der Revision)
select pg_temp.muss_scheitern(format($$select beatlab_private.write_sections(%L, auth.uid(), '[]')$$,
  (select val from t where name = 'fremdprojekt')), 'angemeldet: internen Songplan-Helfer direkt aufrufen');
select pg_temp.muss_scheitern(format($$select beatlab_private.snapshot(%L, auth.uid(), 1, '{}', 'x', true)$$,
  (select val from t where name = 'fremdprojekt')), 'angemeldet: Version über internen Helfer erzeugen');
-- Fremdes Motiv per Update auf Peters Projekt umhängen
insert into public.beatlab_motifs (id, name, length_beats, notes) values ('dddddddd-0000-0000-0000-000000000001', 'Fremd-Motiv', 1, '[{"pitch":"C4"}]');
select pg_temp.muss_scheitern(format($$update public.beatlab_motifs set project_id = %L where id = 'dddddddd-0000-0000-0000-000000000001'$$,
  (select val from t where name = 'projekt')), 'Fremdes Motiv per Update an Peters Projekt hängen');

-- ===================== Nicht angemeldet (anon) =====================
reset role;
insert into t select 'token', token from public.beatlab_shares;
set role anon;
select set_config('request.jwt.claim.sub', '', false);
select pg_temp.muss_scheitern($$select * from public.beatlab_projects$$, 'anon liest Projekte');
select pg_temp.muss_scheitern($$select * from public.beatlab_project_versions$$, 'anon liest Versionen');
select pg_temp.muss_scheitern($$select public.beatlab_create_project('x', '{}'::jsonb)$$, 'anon legt Projekt an');
select pg_temp.muss_scheitern($$select beatlab_private.write_sections(gen_random_uuid(), gen_random_uuid(), '[]')$$, 'anon ruft internen Helfer');
select pg_temp.muss_scheitern($$select beatlab_private.public_player('{}')$$, 'anon nutzt privates Schema');
do $$
declare r record;
begin
  select * into r from public.beatlab_get_shared((select val from t where name = 'token'));
  assert r.title = 'Erster Beat (neu)', 'Titel stimmt';
  assert r.player->>'format' = 'beatlab-player-1', 'öffentliches Format';
  assert r.player->>'bpm' = '94', 'Abspieldaten der gemerkten Version';
  assert r.player::text not like '%GEHEIM%', 'KEINE verschachtelten privaten Werte: ' || r.player::text;
  assert r.player::text not like '%privat_aufnahme%', 'kein privater Dateiname';
  assert not (r.player ? 'sampleNames') and not (r.player ? 'notiz'), 'unbekannte Felder fehlen';
  assert r.player->'pats'->0->'kick' = '[1,0,0,0,1,0,0,0,1,0,0,0,1,0,0,0]', 'Muster bleibt abspielbar';
  assert r.player->'pats'->0->'snare'->>0 = '0', 'Text im Muster wird zu 0';
  assert not (r.player->'pats'->0 ? 'meinespur'), 'unbekannte Spur fehlt';
  assert r.player->'params'->'kick'->>'snd' = 'kickBoom', 'gültige Sound-ID bleibt';
  assert not (r.player->'params'->'lead' ? 'snd'), 'Dateipfad als Sound-ID fällt weg';
  assert not (r.player->'params' ? 'spion'), 'unbekannte Mixer-Spur fehlt';
  assert r.player->'rollLengths' = '{"0":{"3":{"5":2}}}', 'Notenlängen nur Zahlen';
  assert r.player->'arrangement'->0 = '{"pat":0,"bars":4,"name":"Intro"}', 'Arrangement bereinigt';
  assert r.player->'score'->'tracks'->0->'notes'->0 = '{"pitch":"A3","start":0,"duration":2,"velocity":0.8}', 'Note bereinigt';
  assert jsonb_array_length(r.player->'score'->'tracks'->0->'notes') = 1, 'Note mit ungültiger Tonhöhe fällt ganz weg';
  assert jsonb_array_length(r.sections) = 3, 'Songplan dabei';
  assert not (r.sections->0 ? 'id') and not (r.sections->0 ? 'motif_id') and not (r.sections->0 ? 'settings'), 'Songplan ohne interne Felder';
  assert r.sections->1->>'name' = 'Refrain', 'Songplan-Reihenfolge stimmt';
  assert (select count(*) from public.beatlab_get_shared('falsch')) = 0, 'falscher Token liefert nichts';
  raise notice 'OK: Geteilter Link liefert nur Abspieldaten, keine privaten Infos';
end $$;

-- Widerrufen → Link tot
reset role;
set role authenticated;
select set_config('request.jwt.claim.sub', :'peter', false);
update public.beatlab_shares set revoked = true;
set role anon;
do $$ begin
  assert (select count(*) from public.beatlab_get_shared((select val from t where name = 'token'))) = 0, 'widerrufener Link liefert nichts';
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
  assert (select count(*) from public.beatlab_shares) = 0, 'Freigaben mitgelöscht';
  assert (select count(*) from public.beatlab_motifs) = 1, 'Motiv bleibt in der Bibliothek';
  assert (select project_id from public.beatlab_motifs) is null, 'Motiv-Herkunft auf null';
  raise notice 'OK: Projekt löschen räumt auf, Motive bleiben in der Bibliothek';
end $$;

reset role;
do $$ begin raise notice '======== ALLE TESTS BESTANDEN ========'; end $$;
