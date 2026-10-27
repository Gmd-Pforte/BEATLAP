# PS AI MUSIC Beatlab – Android

Die App ist eine dauerhafte Android-Hülle für das Live-Studio unter
`https://gmd-pforte.github.io/BEATLAP/`.

- **Web-Updates:** Neue HTML/CSS/JS-Versionen werden beim nächsten App-Start aus GitHub Pages geladen. Dafür ist keine neue APK nötig.
- **Android-Updates:** Änderungen an nativen Berechtigungen, der WebView-Brücke oder dem App-Symbol brauchen weiterhin eine neu signierte APK.
- **Downloads:** Die `BeatlabAndroid`-Brücke speichert Audio- und Projektdateien in `Downloads/PS AI MUSIC`. Sie transportiert Blobs in kleinen Base64-Blöcken.
- **Dateiauswahl:** Eigene Samples und Beatlab-Projekte werden über den Android-Dateiauswahldialog importiert.
- **Offline:** Der Service Worker kann bereits besuchte Webinhalte zwischenspeichern; falls noch nichts verfügbar ist, zeigt die App eine Offline-/Erneut-versuchen-Seite. Eine vollständig garantierte Offline-Bibliothek ist noch nicht implementiert.

## Test-APK

Die GitHub Action `Build Android Test APK` baut `app-debug.apk`. Diese **Debug-APK** ist zum Testen gedacht. Für dauerhafte native App-Updates benötigen wir eine stabile private Signatur (nicht ins öffentliche Repo hochladen).

## Lokal bauen

Voraussetzungen: JDK 17, Android SDK 35, Android Build Tools 35, Gradle 8.11.1.

```sh
cd android
gradle assembleDebug
```

Ergebnis: `android/app/build/outputs/apk/debug/app-debug.apk`.

## Vor dem Testen

1. Die Pull-Request-Änderungen auf `main` übernehmen.
2. GitHub Pages in den Repository-Einstellungen auf **GitHub Actions** stellen und das Deployment prüfen.
3. Auf Samsung installieren, Play/Pause, eigene Samples, JSON-Projekte und Mix-/Stem-WAV ausprobieren.
4. Nur über HTTPS veröffentlichen. Die native Download-Brücke ist ausschließlich für die festgelegte Beatlab-Adresse vorgesehen.
