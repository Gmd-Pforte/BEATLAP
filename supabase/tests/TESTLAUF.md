# Letzter Testlauf

PostgreSQL 16.15, lokal mit `supabase_stub.sql`, 28.10.2026 (Claude).

```text
OK (abgelehnt): Projekt direkt anlegen mit Revision 999 → permission denied for table beatlab_projects
OK: Projekt über Funktion angelegt (Revision 1, Songplan, erste Version)
OK (abgelehnt): Zustand ist kein Objekt → Projektzustand muss ein JSON-Objekt sein.
OK (abgelehnt): falsches Notensong-Format → Unbekanntes Notensong-Format.
OK (abgelehnt): Zustand über 2 MB → Projekt ist zu groß (max. ca. 2 MB).
OK (abgelehnt): Songplan direkt ändern → permission denied for table beatlab_song_sections
OK (abgelehnt): Songplan direkt löschen → permission denied for table beatlab_song_sections
OK (abgelehnt): Songplan-Block direkt einfügen → permission denied for table beatlab_song_sections
OK (abgelehnt): Version ändern → permission denied for table beatlab_project_versions
OK (abgelehnt): Version löschen → permission denied for table beatlab_project_versions
OK (abgelehnt): Version direkt einfügen → permission denied for table beatlab_project_versions
OK (abgelehnt): state direkt ändern → permission denied for table beatlab_projects
OK (abgelehnt): revision direkt ändern → permission denied for table beatlab_projects
OK (abgelehnt): Eigentümer ändern → permission denied for table beatlab_projects
OK: Titel direkt änderbar
OK: Autosave schreibt Zustand und Songplan gemeinsam, Versionen entstehen automatisch
OK (abgelehnt): Speichern mit ungültigem Block → new row for relation "beatlab_song_sections" violates check constraint "beatlab_song_sections_energy_check"
OK: Fehler beim Songplan → nichts gespeichert (atomar)
OK (abgelehnt): Tablet speichert veralteten Songplan (Konflikt) → Konflikt: Projekt wurde inzwischen auf einem anderen Gerät gespeichert.
OK: Konkurrierende Songplan-Änderung wird als Konflikt erkannt
OK: Nur die letzten 50 automatischen Versionen bleiben, gemerkte bleiben immer
OK (abgelehnt): eigenen (schwachen) Token setzen → permission denied for table beatlab_shares
OK: Fremder Nutzer sieht nichts von Peter
OK (abgelehnt): Fremder speichert in Peters Projekt → Projekt nicht gefunden.
OK (abgelehnt): Fremder hängt Motiv an Peters Projekt → Zugehöriges Projekt/Version gehört nicht diesem Nutzer.
OK (abgelehnt): Fremder heftet Peters Motiv an → Motiv gehört nicht diesem Nutzer.
OK (abgelehnt): Fremder heftet Peters Motiv beim Anlegen an → Motiv gehört nicht diesem Nutzer.
OK (abgelehnt): angemeldet: internen Songplan-Helfer direkt aufrufen → permission denied for function beatlab_write_sections
OK (abgelehnt): angemeldet: Version über internen Helfer erzeugen → permission denied for function beatlab_snapshot
OK (abgelehnt): Fremdes Motiv per Update an Peters Projekt hängen → Zugehöriges Projekt/Version gehört nicht diesem Nutzer.
OK (abgelehnt): anon liest Projekte → permission denied for table beatlab_projects
OK (abgelehnt): anon liest Versionen → permission denied for table beatlab_project_versions
OK (abgelehnt): anon legt Projekt an → permission denied for function beatlab_create_project
OK (abgelehnt): anon ruft internen Helfer → permission denied for function beatlab_write_sections
OK: Geteilter Link liefert nur Abspieldaten, keine privaten Infos
OK: Widerrufener Link funktioniert nicht mehr
OK: Projekt löschen räumt auf, Motive bleiben in der Bibliothek
======== ALLE TESTS BESTANDEN ========
```
