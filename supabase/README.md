# Beatlab-Datenbank (Supabase „Pforte Nexus“)

**Status:** Entwurf von Claude, Review durch ChatGPT. **Noch nicht in Supabase angewendet** – erst nach Peters Freigabe.

## Überblick

```
beatlab_projects ──┬── beatlab_song_sections ──► beatlab_motifs
 (Autosave-Stand)  │    (Songplan-Blöcke)          (Motiv-Bibliothek)
                   └── beatlab_project_versions ──► beatlab_shares
                        (Verlauf / Schnappschüsse)   (Teilen-Links)
```

| Tabelle | Wofür | Wichtigste Felder |
|---|---|---|
| `beatlab_projects` | Ein Beat/Song inkl. aktuellem Arbeitsstand | `title`, `bpm`, `music_key`, `scale`, `style`, `state` (kompletter App-Zustand `P`), `revision` |
| `beatlab_song_sections` | Die bunten Blöcke im Songplan | `position`, `kind` (intro, verse, chorus …), `name`, `bars`, `energy` 1–10, `color`, `motif_id` |
| `beatlab_project_versions` | Verlauf zum Wiederherstellen | `revision`, `label`, `is_auto`, `state`, `sections` |
| `beatlab_motifs` | Melodien, die Peter mag, projektübergreifend | `name`, `notes` (wie im Notensong-Format), `length_beats`, `favorite` |
| `beatlab_shares` | Link zum Anhören im Browser | `token`, `expires_at`, `revoked` |

## Entscheidungen

- **Spuren und Noten bleiben im JSON** (`state`, bzw. `score.tracks` im Format `PS-Beatlap-Score-1`). Die App bestimmt das Format; eine eigene Tabelle pro Spur/Note würde jede Formatänderung doppelt nötig machen und das Speichern auf dem Handy verlangsamen. Eigene Tabellen gibt es nur für Dinge, die wir einzeln anfassen, sortieren oder wiederverwenden.
- **Autosave mit Konfliktschutz:** Die App speichert nur über `beatlab_save_project(projekt, erwartete_revision, state, …)`. Hat inzwischen ein anderes Gerät gespeichert, wird nichts überschrieben, sondern ein Konflikt gemeldet (Fehlercode `40001`). `state` und `revision` lassen sich nicht direkt ändern.
- **Versionen automatisch:** höchstens alle 10 Minuten eine automatische Version, die letzten 50 bleiben. Mit `p_snapshot_label` („Refrain fertig“) merkt Peter sich eine Version dauerhaft. Versionen sind unveränderlich.
- **Sicherheit:** RLS auf allen Tabellen, nur der Eigentümer (Supabase-Login) sieht und ändert seine Daten. Kind-Zeilen können nicht an fremde Projekte gehängt werden. Ohne Login (`anon`) gibt es keinen Tabellenzugriff, nur `beatlab_get_shared(token)` für gültige, nicht widerrufene Links.
- **Grenzen:** Projekt-JSON max. ca. 2 MB, 1–64 Blöcke, Energie 1–10, Motive bis 512 Noten.

## Lokal testen

Die Tests laufen gegen ein normales PostgreSQL mit einem kleinen Supabase-Nachbau (`tests/supabase_stub.sql`, **nicht** auf Supabase ausführen):

```sh
createdb beatlab_test
psql -v ON_ERROR_STOP=1 -d beatlab_test -f supabase/tests/supabase_stub.sql
psql -v ON_ERROR_STOP=1 -d beatlab_test -f supabase/migrations/20261028000000_beatlab_schema.sql
psql -v ON_ERROR_STOP=1 -d beatlab_test -f supabase/tests/beatlab_schema_test.sql
```

Abgedeckt: Anlegen, Songplan umsortieren, Motiv anheften, Autosave und Revisionen, Konflikt bei veraltetem Stand, Versions-Aufräumen, Unveränderlichkeit, fremder Nutzer, nicht angemeldet, Teilen-Link inkl. Widerruf, Löschen.

## Nächste Schritte (nach Freigabe)

1. ChatGPT prüft Struktur, Sicherheit und Erweiterbarkeit.
2. Peter gibt frei → Migration wird auf „Pforte Nexus“ angewendet, danach Supabase-Sicherheitsprüfung (Advisors).
3. In Supabase: E-Mail-Login (Magic Link) für Peter aktivieren.
4. App-Anbindung in `index.html`: Login, Autosave, Projektliste, Songplan-Blöcke – Schritt für Schritt, jeweils am Samsung getestet.
