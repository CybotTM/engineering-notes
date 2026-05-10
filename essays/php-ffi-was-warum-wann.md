---
title: "PHP FFI – was, warum, wann?"
slug: "php-ffi-was-warum-wann"
originally_published: "2025-11"
updated: "2026-05-10"
status: "current"
topics:
  - php
  - rust
  - ffi
  - performance-engineering
  - language-fundamentals
summary: "Wann sich PHP FFI lohnt – am Beispiel eines XLIFF-Imports, der von ORM (~1.400/s) über DBAL Bulk (~5–7k/s) auf eine All-in-Rust-Variante via FFI (~35.320/s) skaliert wird."
lang: "de"
license: "CC-BY-4.0"
---

PHP FFI ist das unscheinbare Werkzeug, das den Elefanten aus seinem Gehege lässt. Statt umständlich über Extensions oder unhandliche C-Wrapperschichten zu gehen, öffnet FFI eine direkte Tür zu nativen Bibliotheken. Bedeutet: Performance, wo man sie braucht. Kontrolle, wenn sie zählt. Und Freiheit, ohne jedes Mal einen kompletten Build-Prozess anzuschmeißen.

Nutzen? Immer dann, wenn:

- PHP zu langsam ist,
- ein bestehender High-Performance-Code existiert,
- Low-Level-Operationen gefragt sind,
- oder wenn man schlicht Spaß daran hat, sich neue Möglichkeiten im PHP-Ökosystem zu erschließen.

<https://www.php.net/manual/en/intro.ffi.php>

---

## Was ist Rust?

Rust ist die Programmiersprache, die Entwickler zurücklässt mit dem Gefühl: „Warum habe ich das nicht früher benutzt?" Sie kombiniert:

- **Performance** auf C/C++-Niveau,
- **Speichersicherheit** ohne Garbage Collector,
- **Null-Cost Abstractions**,
- ein Tooling, das einfach funktioniert,
- und eine Community, die Qualität liebt.

Rust zwingt dich, gute Entscheidungen zu treffen – und belohnt dich mit Geschwindigkeit und Robustheit, die man sonst nur durch jahrelange Feinmechanik erreicht.

<https://rust-lang.org/>

---

## Ausgangssituation: langsamer Import einer Übersetzungs-Datenbank via ORM

Importprozesse über ein ORM sind bequem. Lesbar. Stabil. Aber eben auch: langsam. Besonders wenn fünf- oder sechsstellige Datensätze hereinschneien und jede Instanz einzeln über das ORM geschoben wird.

Das Setup: ein klassischer XLIFF-Import in eine TYPO3-Übersetzungs-Datenbank. Viele Datensätze. Viel Overhead. Viel Geduld.

Die Herausforderung: nicht warten wollen.

---

## Zwischenstufe: direkter Import via DBAL Bulk Operations

Bevor eskaliert wird, fair bleiben. DBAL Bulk Operations sind bereits ein ordentlicher Performance-Booster. Weniger Overhead, weniger Magie, mehr Durchsatz.

Vergleichbar mit: gleiche Strecke, aber statt Familienkombi jetzt ein solider Turbo-Diesel.

Beispielhafte Umsetzung als Pull Request: <https://github.com/netresearch/t3x-nr-textdb/pull/57>

Gut? Ja. Schnell? Auch. Aber warum hier aufhören?

---

## Ziel/Experiment: Import mittels PHP FFI und Rust

Jetzt wird's spannend. Die Idee: Die wirklich harte Arbeit – Parsing, Validierung, Strukturierung, Batch-Verarbeitung – wird von Rust erledigt. PHP orchestriert nur noch.

PHP ruft genau **eine** FFI-Funktion auf: `xliff_import_file_to_db()`. Diese Funktion läuft komplett in Rust: XLIFF einlesen, parsen, validieren, Bulk-Lookups und Bulk-INSERT/UPDATE in der Datenbank. PHP sieht davon nur noch eine kompakte Statistik (Anzahl Inserts/Updates/Fehler, Laufzeit) und kümmert sich um UI, Logging und Fehlerkommunikation.

Beispielhafte Umsetzung als Pull Request: <https://github.com/netresearch/t3x-nr-textdb/pull/60>

Klingt ungewöhnlich? Ist es. Macht es Spaß? Definitiv.

---

## Ergebnisse: ORM vs. DBAL Bulk vs. PHP FFI + Rust

### Performance im Vergleich

```
Datensätze pro Sekunde

ORM         | ████▌                          | ~1.400/s
DBAL Bulk   | ██████████████▌                | ~5.000–7.000/s
Rust (FFI)  | ██████████████████████████▌    | ~35.320/s
```

### Laufzeitvergleich

```
Gesamtzeit für 419.428 Einträge

Rust (FFI)  | ██                             | 11,88 s
DBAL Bulk   | ████████████                   | 60–80 s
ORM         | ████████████████████████████   | 300+ s
```

### Pipeline-Flow (Import-Prozess)

```
PHP → FFI → Rust
             ↓
         [Parsing]
             ↓
    [Existing-Key-Lookup]
             ↓
      [Batch Builder]
             ↓
    [Bulk INSERT/UPDATE]
             ↓
    [Stats zurück an PHP]
```

**Datengrundlage**

- XLIFF-Datei mit 419.428 Übersetzungseinträgen
- identische Umgebung für alle drei Varianten

**Gemessene Laufzeiten und Durchsatz**

- **Variante 1 – klassisches ORM** (Stand vor Optimierung)
  - ~300+ Sekunden Gesamtzeit
  - ~1.400 Datensätze/Sekunde
  - sauber, aber massiv überlastet durch Hydration, Events & Kontextverwaltung.
- **Variante 2 – PHP DBAL Bulk**
  - ~60–80 Sekunden
  - ~5.000–7.000 Datensätze/Sekunde
  - je nach Umgebung und Dateigröße 6–33x schneller als das ORM; Architektur bleibt komplett in PHP, aber mit klar getrenntem Bulk-Pfad.
- **Variante 3 – All-in-Rust via PHP FFI**
  - 11,88 Sekunden Gesamtzeit
  - 35.320 Datensätze/Sekunde
  - ca. 25x schneller als die ursprüngliche ORM-Implementierung und typischerweise 5–6x schneller als die DBAL-Bulk-Variante.

**Zeitanteile in der Rust-Variante (419k Datensätze)**

- Parsing: ~0,48 s (~4 %)
- Konvertierung/Mapping: ~0,18 s (~1,5 %)
- DB-Import: ~11,2 s (~94 %)

Die Parse-Phase ist damit praktisch „aus der Gleichung raus" – der Flaschenhals ist ausschließlich noch die Datenbank-I/O. Genau dort will man bei solchen Workloads am Ende ankommen.

---

## Technische Details

### Timeline der Optimierungsphasen

```
─────────────┬────────────────────┬──────────────────────────────────────
             │                    │
   Phase 1   │        Phase 2     │        Phase 3
   ORM       │      DBAL Bulk     │   All-in-Rust via FFI
             │                    │
   langsam   │ 6–33x schneller    │ >25x schneller vs ORM
             │                    │ Parsing: <0,5 s statt 45 s
```

### Zeitanteile im Rust-Import

```
Parsing       | █                     | 0,48 s (~4 %)
Mapping       | █                     | 0,18 s (~1,5 %)
DB-Import     | ███████████████████   | 11,2 s (~94 %)
```

### Batch-Größen und SQL-Reduktion

```
419.428 Einträge
    ↓
~700–900 UPDATE-Batches (CASE-WHEN)
    ↓
~400 INSERT-Batches
```

---

### Architekturvergleich

| Eigenschaft       | ORM         | DBAL Bulk      | Rust FFI                            |
| ----------------- | ----------- | -------------- | ----------------------------------- |
| Performance       | langsam     | mittel         | extrem schnell                      |
| Sicherheit        | ok          | ok             | speichersicher (Rust)               |
| Code-Komplexität  | niedrig     | mittel         | höher (zwei Sprachen)               |
| Deploy-Aufwand    | niedrig     | niedrig        | einmaliger Build der `.so`          |
| Debuggability     | hoch        | hoch           | mittel (Rust-Compiler hilft viel)   |
| Skalierung        | schlecht    | gut            | exzellent                           |
| DB-Last           | hoch        | mittel         | optimal (Batches)                   |

### Architektur „All-in-Rust"

- zentrales Entry-Point in Rust: `xliff_import_file_to_db()` als `extern "C"` exportiert
- PHP erstellt eine FFI-Binding-Signatur und übergibt:
  - Pfad zur XLIFF-Datei,
  - DB-Konfiguration (Host, Port, Benutzer, Passwort, DB-Name …),
  - Environment/Language-Kontext,
  - eine Stats-Struktur, die von Rust gefüllt wird (`inserted`, `updated`, `errors`, `duration`).
- Rust übernimmt den kompletten Import:
  1. Datei streamend lesen (1-MB-Puffer statt kleiner Standard-Buffer),
  2. XLIFF parsen und normalisieren,
  3. bestehende Übersetzungen in Batches nachschlagen,
  4. neue Datensätze und Updates in Batches aufbereiten,
  5. Bulk-INSERTs und CASE-WHEN-UPDATEs ausführen.

Ein Aufruf aus PHP sieht vereinfacht so aus:

```php
$stats = $ffi->xliff_import_file_to_db(
    $filePath,
    FFI::addr($config),    // DB-Konfiguration
    $environment,
    $languageUid,
    FFI::addr($stats)      // wird von Rust gefüllt
);
```

PHP selbst fasst die Ergebnisse nur noch zusammen und kümmert sich um UI/Logging.

### Parser-Optimierungen in Rust

- größerer `BufReader` (1 MB) reduziert Syscalls drastisch
- Voralloziierung von Vektoren und Strings für IDs und Übersetzungstexte
- Fast-Path für UTF-8-Decoding
- strikt sequentielles, allokationsarmes Parsing

Der ursprüngliche PHP-SimpleXML-Parse im Hybrid-Ansatz lag bei grob 45 Sekunden; mit der optimierten Rust-Variante liegt das Parsing im Bereich von unter einer halben Sekunde.

### Bulk-Update-Strategie

- statt Hunderttausender einzelner UPDATEs werden IDs gebündelt
- pro Batch wird ein Statement der Form `UPDATE … SET value = CASE uid … END WHERE uid IN (…)` generiert
- aus ~419.000 Einzel-Queries werden so unter 1.000 Bulk-Updates

Damit skaliert der Import nahezu linear mit der Datensatzanzahl, bis die Datenbank selbst zum limitierenden Faktor wird.

---

## Vor- und Nachteile

### Vorteile

- **Geschwindigkeit:** Rust erledigt das, was CPU-lastig ist – und das brutal effizient.
- **Sicherheit:** Rust verhindert ganze Klassen von Fehlern.
- **Flexibilität:** FFI macht das Ganze containerfreundlich und infrastrukturell leichtgewichtig.
- **Einmaliger Aufwand:** Bibliothek bauen, FFI anbinden – fertig.

### Nachteile

- **Neue Technologie:** Rust ist nicht trivial. Man lernt.
- **Build-Prozess:** einmaliger Aufwand für die `.so`/`.dll`.
- **Debugging-Switch:** man springt zwischen zwei Sprachen.

Aber: In Containern ist das alles lösbar. Einmal bauen – überall nutzen.

---

## Ergänzende technische Details

### PHP-Integration: wie FFI tatsächlich verdrahtet wird

Der FFI-Call ist keine Magie. Das ist schnörkelloser PHP-Code. Entwicklerfreundlich, auditierbar, reproduzierbar.

#### FFI-Binding (vereinfacht)

```php
$this->ffi = FFI::cdef(
    file_get_contents(__DIR__ . '/ffi/xliff_import.h'),
    __DIR__ . '/../../rust/target/release/libnr_textdb_import.so'
);
```

#### Datenbank-Config als C-Struktur

```php
// Hinweis: stark vereinfachtes Beispiel — produktiv unbedingt
// Längen prüfen und Zugangsdaten nicht über stack-allokierte
// char[256]-Buffer übergeben.
$config = $ffi->new('db_config');
$config->host = FFI::new('char[256]', false);
FFI::memcpy($config->host, $host, strlen($host));
$config->port = $port;
$config->user = $ffi->new('char[256]', false);
FFI::memcpy($config->user, $user, strlen($user));
// usw.
```

#### Der eigentliche Import-Aufruf

```php
$stats = $ffi->new('import_stats');

$ffi->xliff_import_file_to_db(
    $pathToFile,
    FFI::addr($config),
    $environment,
    $languageUid,
    FFI::addr($stats)
);
```

#### Rückgabe in PHP sichtbar machen

```php
echo sprintf(
    "Inserts: %d, Updates: %d, Errors: %d, Duration: %.2fs",
    $stats->inserted,
    $stats->updated,
    $stats->errors,
    $stats->duration
);
```

Ohne „Magic", ohne „Hidden Layers". Klar, direkt, nachvollziehbar.

---

### Container- und Runtime-Anpassungen

Damit das Ganze sauber auf jedem System läuft, müssen im Stack nur wenige Dinge angepasst werden.

#### 1. Dockerfile

- Rust-Toolchain nur im **Builder-Stage** (Multi-Stage-Build)
- Ergebnis: schlankes Image, keine Rust-Compilerreste

```dockerfile
FROM rust:1.91 AS builder
WORKDIR /build
COPY rust/ .
RUN cargo build --release

FROM php:8.4-fpm
COPY --from=builder /build/target/release/libnr_textdb_import.so /usr/local/lib/
```

#### 2. PHP-FPM

- `ffi.enable = true`
- Bindung auf die spezifische `.so`

```ini
php_admin_value[ffi.preload]="/var/www/html/ffi/xliff_import.h"
```

#### 3. Backend-Integration

- neuer „Import"-Button im Backend-Modul
- Fortschrittsanzeige wird mit Rust-Stats gefüllt
- Fehlerlisten werden per Rust-Struct geliefert und im Backend gerendert
- Logging auf zwei Ebenen:
  - Rust gibt Maschinenwerte
  - PHP generiert daraus lesbare Meldungen für Redakteure

Dadurch bleibt das Feature für Nicht-Techniker **identisch nutzbar**, während die Engine komplett ersetzt wurde.

---

## Referenzen

- DBAL-Bulk-Variante: <https://github.com/netresearch/t3x-nr-textdb/pull/57>
- All-in-Rust-Variante via PHP FFI: <https://github.com/netresearch/t3x-nr-textdb/pull/60>
- PHP-Manual zu FFI: <https://www.php.net/manual/en/intro.ffi.php>
- Rust: <https://rust-lang.org/>

---

## Diskussion

Ideen, Kritik, Wünsche? Andere Einsatzszenarien für Rust + PHP FFI?
Immer her damit.

---

*Originally published as an internal Netresearch wiki article in November 2025. Republished here lightly edited for public context.*
