# PS AI MUSIC – Beatlab

Ein mobiles Musikstudio von **Peter Schleifer (PS AI MUSIC)**, gemeinsam weiterentwickelt mit Claude und ChatGPT.

## Start

Die gesamte Anwendung steckt derzeit in [index.html](index.html).

- **Am Computer:** `index.html` in einem aktuellen Browser öffnen.
- **Auf Android:** die Datei herunterladen und in Chrome öffnen. Für zuverlässige lokale Speicherung und Downloads kann eine HTTPS-Bereitstellung hilfreich sein.
- **GitHub Pages:** später aus dem `main`-Branch aktivierbar, um Beatlab ohne Dateidownload aufzurufen.

## Funktionen (Stand Beatlab 4)

- 16-Schritt-Sequencer mit vier Mustern A–D
- Instrumente, Drum-Sounds und eigene Samples
- Piano Roll und musikalischer Melody Composer
- Song-Arrangement mit Abschnitten
- Mixer mit Effekten
- WAV-Mix und Einzelspuren-Export
- Projektdateien als JSON sichern und laden

## Unsere Zusammenarbeit

**Peter:** Ideen, musikalische Entscheidungen und Tests auf Android.  
**Claude und ChatGPT:** Umsetzung, Fehlerbehebung, musikalische Algorithmen, UI und Code-Review.

### Änderungen sicher einbringen

1. Vor Änderungen die aktuelle `index.html` aus GitHub herunterladen bzw. den neuesten Stand abrufen.
2. Bei größeren Änderungen in einem neuen Branch arbeiten.
3. Nur geprüfte Änderungen per Pull Request nach `main` übernehmen.
4. Peter testet Wiedergabe, Projektladen und WAV-Export auf dem Samsung.
5. Änderungen und bekannte Probleme im Pull Request dokumentieren.

> Wichtig: Wenn Peter eine neue HTML-Version liefert, wird sie vor dem Ersetzen mit dem aktuellen GitHub-Stand verglichen. So gehen Arbeiten von Claude oder ChatGPT nicht verloren.

## Geplante Verbesserungen

- Verlässliche Audio-/WAV-Export-Tests, auch für lange Arrangements und Mobilgeräte
- Mehr musikalische Variation und weniger wiederholte Melodien
- Undo/Redo und robustes Autosave
- Performance und Speicherverbrauch auf Android optimieren
- Besserer Piano-Roll-Editor und komfortableres Song-Arrangement
- Projektformat versionieren und Importfehler verständlich anzeigen
- Optional später: Mehrspur-Aufnahmen, MIDI-Export und PWA-Installation

## Technik

Vanilla HTML, CSS und JavaScript mit Web Audio API – keine Serverpflicht und keine externen JavaScript-Abhängigkeiten. Browser-Funktionen wie lokale Sample-Speicherung und Dateidownload sind vom jeweiligen Browser abhängig.

## Flügel (echt) – PR #13

- `Beatlab-Boom-Bap-Akkorde-VORHER-E-Piano.wav` – Vorlage Boom Bap, Akkorde mit E-Piano (Standard)
- `Beatlab-Boom-Bap-Akkorde-NACHHER-Fluegel-echt.wav` – gleiche Vorlage, Akkorde mit „Flügel (echt)“

Beide mit der bisherigen Klang-Engine (ohne PR #12), 8 Takte. Flügel: Salamander Grand Piano V3 von Alexander Holm, CC BY 3.0.
