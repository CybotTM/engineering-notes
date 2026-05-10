---
title: "Vom Feature zum Fundament: Warum AI in TYPO3 von unten gebaut wird (vault → llm → cowriter)"
slug: "typo3-ai-stack-vault-llm-cowriter"
originally_published: "2026-05-10"
updated: "2026-05-10"
status: "current"
topics:
  - typo3
  - ai-assisted-development
  - architecture
  - secrets-management
  - open-source-maintainership
summary: "Drei TYPO3-Extensions, ein Stack: nr-vault verschlüsselt Geheimnisse, nr-llm abstrahiert Provider, t3x-cowriter ist das sichtbare Feature im CKEditor. Warum man so etwas von unten baut – und nicht vom Editor-Button aus."
lang: "de"
license: "CC-BY-4.0"
---

Der Use Case klingt harmlos: Redakteurinnen wollen einen Knopf im Rich-Text-Editor, der Texte verbessert, kürzt, übersetzt, Alt-Texte aus Bildern generiert. Ein paar API-Calls gegen OpenAI, ein CKEditor-Plugin – fertig.

Dieser Artikel ist die Erklärung, warum das nicht funktioniert. Genauer: warum aus „ein paar API-Calls" sehr schnell drei Extensions werden, sobald man das Ding in einer realen Agentur-Realität betreibt – mit mehreren TYPO3-Instanzen, mehreren Erweiterungen, mehreren Anbietern, mehreren Mandanten und einem Auditor, der wissen will, wo welcher API-Key liegt.

Die drei Extensions sind:

- **[`netresearch/nr-vault`](https://github.com/netresearch/t3x-nr-vault)** – Geheimnisse, verschlüsselt, mit Audit-Trail, im TYPO3-Backend rotierbar.
- **[`netresearch/nr-llm`](https://github.com/netresearch/t3x-nr-llm)** – geteilte LLM-Infrastruktur. Ein Setup, alle Erweiterungen, alle Anbieter.
- **[`netresearch/t3x-cowriter`](https://github.com/netresearch/t3x-cowriter)** – das, was man am Ende sieht: ein KI-Assistent in CKEditor 5.

Die Abhängigkeitsrichtung ist eindeutig: cowriter braucht nr-llm, nr-llm nutzt nr-vault. Die Bau-Reihenfolge war es ebenfalls – nur eben umgekehrt zu dem, was Stakeholder zuerst sehen wollen. Und genau das ist der Punkt.

## Das Anti-Muster: vom Editor-Button aus nach unten

Man kennt das Muster aus zu vielen Codebases: Ein Feature-Request landet im Backlog („KI-Schreibhilfe im RTE"), eine Extension wird gestartet, sie holt sich einen `OPENAI_API_KEY` aus den Extension-Settings, baut ein bisschen HTTP-Client-Code, ein bisschen Fehlerbehandlung, ein bisschen Streaming – und das Feature funktioniert.

Sechs Monate später kommt die zweite KI-Erweiterung – Meta-Description-Generator für SEO. Die zweite Extension hat ihren eigenen Settings-Dialog, ihren eigenen API-Key, ihren eigenen HTTP-Client, ihre eigene Fehlerbehandlung. Niemand hat einen Überblick darüber, was wo wie viel kostet.

Drei Monate später soll wegen Datenschutz auf einen Anbieter mit deutschem Hosting (oder ein lokales Ollama) gewechselt werden. Beide Extensions müssen einzeln umgebaut werden. Die Keys liegen in `LocalConfiguration.php` oder in der Datenbank im Klartext – egal wo, beim nächsten Datenbank-Dump sind sie weg.

Das ist nicht ein Bug einer konkreten Extension. Das ist eine Folge der Reihenfolge: Wer das *sichtbare* Feature zuerst baut, schmiert die Querschnittsthemen – Geheimnisse, Anbieterabstraktion, Budgets, Audit – über jede einzelne Integration.

Die andere Reihenfolge funktioniert besser. Erst das Fundament, dann die geteilte Infrastruktur, dann das Feature. Klingt nach Wasserfall, ist aber etwas anderes: Es ist die Erkenntnis, dass es Schichten gibt, die *vor* dem Feature gelöst sein müssen, weil sie sonst N-mal gelöst werden – und zwar jedes Mal anders.

## Schicht 1: nr-vault – Geheimnisse zuerst

Die erste Frage, bevor irgendein KI-Feature in TYPO3 sinnvoll diskutiert wird: Wo liegt der API-Key?

Die ehrliche Antwort in den meisten Bestandssystemen lautet: in `LocalConfiguration.php`, oder im Klartext in einer Extension-Konfigurationstabelle, oder hartcodiert in irgendeinem `services.yaml`. Jede dieser Antworten bedeutet: Wenn der Datenbank-Dump leakt, leakt auch der Key. Eine Rotation bedeutet einen Deployment-Zyklus.

`nr-vault` löst das mit **Envelope Encryption** – demselben Muster, das AWS KMS, Google Cloud KMS und in der Tendenz auch HashiCorp Vault nutzen, nur eben in der TYPO3-Datenbank statt in einem externen Service:

- Ein **Master Key** liegt außerhalb der Datenbank (Datei, ENV, abgeleitet).
- Pro Geheimnis wird ein eigener **Data Encryption Key (DEK)** erzeugt.
- Der DEK verschlüsselt das eigentliche Geheimnis.
- Der DEK selbst wird vom Master Key verschlüsselt – und so in der Datenbank gespeichert.

Das Verfahren: AES-256-GCM via `libsodium`, mit Fallback auf XChaCha20-Poly1305, falls AES-NI auf der CPU nicht verfügbar ist.

Warum so umständlich, warum nicht direkt mit dem Master Key arbeiten? Weil eine **Master-Key-Rotation** dann die Re-Verschlüsselung *aller* Geheimnisse erfordern würde. Im Envelope-Modell wird nur die DEK-Schicht neu verschlüsselt – die DEKs selbst bleiben dieselben, die Geheimnisse müssen nicht angefasst werden. Der CLI-Befehl heißt entsprechend `vault:rotate-master-key` und arbeitet auf der DEK-Tabelle, nicht auf den Klartexten.

Warum kein HashiCorp Vault Sidecar, kein Kubernetes-Secret? Weil die meisten TYPO3-Installationen in einer Welt leben, in der „eine zusätzliche Infrastruktur-Komponente" einen Eskalationsprozess auslöst, der das Feature um ein Quartal verzögert. `nr-vault` braucht: PHP 8.2, `ext-sodium` (sowieso vorhanden), eine Datenbanktabelle. Nichts sonst. Das ist bewusst die Designentscheidung – nicht weil ein externer Vault schlechter wäre, sondern weil die Realität von Mittelstand und Agentur-Hosting ein Plugin braucht, kein Sidecar.

Der Trick, der `nr-vault` für Anwendungscode angenehm macht, ist der **`VaultHttpClientInterface`** mit einem `SecretPlacement`-Enum: `Bearer`, `BasicAuth`, `Header`, `QueryParam`, `BodyField`, `ApiKey`, `OAuth2`. Anwendungscode konfiguriert einmal, *wo* das Geheimnis im HTTP-Request landen soll – und sieht den Klartext nie:

```php
$client = $this->httpClient->withAuthentication('stripe_api_key', SecretPlacement::Bearer);
$response = $client->sendRequest($request);
```

Der Stripe-Key wird zur Laufzeit aus dem Vault geholt, in den `Authorization`-Header injiziert, im Stack-Trace nicht sichtbar, im Log nicht sichtbar, im Speicher des Anwendungscodes ebenfalls nicht. Das ist die kleine, aber entscheidende Geste, die aus „verschlüsselte Datenbankspalte" eine vernünftige Secrets-API macht.

Dazu kommt: Backend-Modul mit Rotations-UI, Audit-Log mit Hash-Chain (tamper-evident), TCA-Feldtyp `vaultSecret`, der sich in jede Extension einbinden lässt. Und perspektivisch (Roadmap Phase 6) die externen Adapter – HashiCorp, AWS, Azure – hinter derselben Schnittstelle, sodass größere Setups nachziehen können, ohne dass der Anwendungscode angepasst werden muss.

## Schicht 2: nr-llm – einmal konfigurieren, von jeder Erweiterung nutzbar

Mit nr-vault ist der erste Footgun entfernt: API-Keys liegen nicht mehr im Klartext. Das löst aber das eigentliche Skalierungsproblem nicht – nämlich dass jede KI-Erweiterung weiterhin ihre eigene Provider-Integration baut.

`nr-llm` ist die Antwort darauf: eine geteilte Schicht für LLM-Zugriff, vergleichbar mit dem TYPO3-Caching-Framework, nur eben für Sprachmodelle. Administratoren konfigurieren Provider, Modelle und Use-Case-Presets *einmal*; jede Erweiterung im System nutzt sie via Dependency Injection.

Die Architektur ist drei Ebenen tief und das ist keine Spielerei – sie spiegelt eine reale Trennung:

```
CONFIGURATION (use-case)   "blog-summarizer"  → system_prompt, temperature, max_tokens
        ↓
MODEL                      "gpt-5.3-instant"  → model_id, capabilities, pricing
        ↓
PROVIDER                   "openai-prod"      → endpoint, api_key (encrypted)
```

Mehrere API-Keys pro Provider-Typ (Prod/Dev/Backup), mehrere Use-Cases pro Modell, klare Trennung. Wer das einmal selbst gebaut hat, weiß, warum Configuration und Model nicht dasselbe sind.

Auf dem Provider-Layer abstrahiert eine `ProviderInterface` mit Capability-Interfaces (`EmbeddingCapableInterface`, `VisionCapableInterface`, `StreamingCapableInterface`, `ToolCapableInterface`) die Eigenheiten von OpenAI, Anthropic, Gemini, Ollama, OpenRouter, Mistral, Groq, Azure OpenAI weg ([ADR-001](https://github.com/netresearch/t3x-nr-llm/blob/main/Documentation/Adr/Adr001ProviderAbstractionLayer.rst)). Eine Erweiterung programmiert gegen die Schnittstelle, nicht gegen den Anbieter – was bedeutet: Der Wechsel von OpenAI zu Anthropic oder zu lokalem Ollama ist eine Admin-Einstellung, kein Code-Change.

Der ADR-Korpus ist hier der eigentliche Wert. Aktuell 28 Architecture Decision Records – das ist viel, und es ist Absicht. Drei davon sind im Kontext dieses Stacks besonders relevant:

- **[ADR-012](https://github.com/netresearch/t3x-nr-llm/blob/main/Documentation/Adr/Adr012ApiKeyEncryption.rst): API key encryption at application level** – Status: *Superseded*. Das war der ursprüngliche Ansatz: Verschlüsselung in nr-llm selbst. Wurde abgelöst, sobald nr-vault verfügbar war. Der ADR ist nicht gelöscht, sondern als „superseded" markiert – eine nachvollziehbare Spur, *warum* heute nr-vault zuständig ist und nicht ein eigenes Krypto-Modul. Das ist gelebte ADR-Kultur: Entscheidungen nicht überschreiben, sondern abschichten.
- **[ADR-021](https://github.com/netresearch/t3x-nr-llm/blob/main/Documentation/Adr/Adr021ProviderFallbackChain.rst): Provider Fallback Chain** – Eine Configuration kann eine geordnete Liste anderer Configurations als Fallback-Kette deklarieren. Bei *retryable* Fehlern (Connection Timeout, HTTP 5xx, HTTP 429) springt ein `FallbackChainExecutor` zur nächsten Stufe. „Retryable" ist explizit eng definiert: Authentifizierungsfehler, fehlerhafte Requests, fehlende Capabilities werden *nicht* gefallback-t – ein anderer Anbieter würde denselben Fehler liefern. Streaming wird bewusst nicht eingeschlossen: Sobald der erste Chunk geyielded wurde, lässt sich der Provider nicht mehr im Flug tauschen.
- **[ADR-025](https://github.com/netresearch/t3x-nr-llm/blob/main/Documentation/Adr/Adr025PerUserBudgets.rst): Per-User AI Budgets** – Sechs unabhängige Schwellwerte pro Backend-User: Requests / Tokens / Kosten, jeweils täglich / monatlich. `0` heißt unbegrenzt. Das Tabellen-Design ist die wichtige Stelle: Der Datensatz speichert *Obergrenzen*, nicht *Zähler* – die tatsächliche Nutzung wird bei Bedarf aus `tx_nrllm_service_usage` aggregiert. Es gibt keinen zweiten Schreibvorgang pro Request, keine zwei Quellen, die divergieren können. Pure Pre-Flight-Prüfung.

Erwähnenswert noch [ADR-023](https://github.com/netresearch/t3x-nr-llm/blob/main/Documentation/Adr/Adr023BackendCapabilityPermissions.rst) (jede Capability als nativer TYPO3-Backend-Permission-Eintrag in `customPermOptions['nrllm']`, sodass ein Admin per Checkbox Vision oder Tool-Calling site-weit für eine Gruppe abdrehen kann) und [ADR-026](https://github.com/netresearch/t3x-nr-llm/blob/main/Documentation/Adr/Adr026ProviderMiddlewarePipeline.rst) (Konsolidierung der Querschnittsthemen Fallback, Budget, Usage-Tracking, Cache in eine Middleware-Pipeline statt verstreuter `try/catch`-Loops).

Der ADR-Korpus ist nicht Selbstzweck. Er ist der Grund, warum die zweite und dritte KI-Erweiterung auf demselben Stack landen können, ohne dass jemand „mündlich überliefert" werden muss, warum eine bestimmte Designentscheidung so aussieht.

## Schicht 3: t3x-cowriter – das Feature, das alles motiviert hat

`cowriter` ist die Erweiterung, die für Endanwender sichtbar ist – ein KI-Assistent als CKEditor-5-Plugin. Vier Toolbar-Komponenten: das Haupt-Dialog für aufgabenbasierte Bearbeitung (Verbessern, Zusammenfassen, Erweitern, Grammatik, Übersetzen), Vision (Alt-Texte aus Bildern), Translation (Dropdown mit über zehn Sprachen) und Templates (wiederverwendbare Prompt-Vorlagen aus dem Backend).

Die Architektur, von außen nach innen:

```
CKEditor Toolbar  →  AIService.js  →  AjaxController/VisionController/...
                                            ↓
                                  LlmServiceManagerInterface (nr-llm)
                                            ↓
                                       Provider-Adapter
                                            ↓
                                       External LLM API
```

Jeder Request wird **durch das TYPO3-Backend geproxyed**. Das Browser-Frontend hat zu keiner Zeit einen API-Key gesehen. Authentifizierung läuft via TYPO3-Backend-Session und Nonce-basiertem Routen-Token. Rate-Limit ist 20 Requests pro Minute pro Backend-User. Streaming via Server-Sent Events. Inhalts-Sanitisierung über CKEditors HTML-Processing-Pipeline.

Das Interessante an cowriter ist, was *nicht* in cowriter steht: keine API-Key-Konfiguration, keine Provider-Auswahl, keine Fallback-Logik, keine Budget-Verwaltung, keine Usage-Tabelle. Alles, was in einer naiven Implementierung der schwierige Teil wäre, ist eine Zeile Dependency Injection:

```php
public function __construct(
    private readonly LlmServiceManagerInterface $llm,
) {}
```

Die Migration auf Version 3.0 ist die empirische Bestätigung dieses Designs: cowriter v2.x war ein eigenständiges CKEditor-4-Frontend-Plugin mit eigener API-Key-Verwaltung in den Extension-Settings. v3.0 entfernt die Frontend-Architektur komplett, schreibt auf CKEditor 5 und Backend-Proxy um – und nimmt die nr-llm-Abhängigkeit mit. Dieselbe Funktionalität, deutlich weniger Code in cowriter selbst, dafür Verschlüsselung, Fallbacks, Budgets gratis.

## Warum die Reihenfolge zählt

Die drei Extensions sind in der inversen Reihenfolge der Sichtbarkeit gebaut: vault, dann llm, dann cowriter. Das ist die Behauptung dieses Texts: Wer den Editor-Button zuerst baut, schmiert Geheimnisse, Provider-Konfiguration, Budgets und Audit über jede einzelne Integration. Wer das Fundament zuerst baut, hat einen kleinen Editor-Button.

Konkret in Zahlen, die sich am Code ablesen lassen:

- cowriter braucht **keine eigene Krypto** – nr-vault liefert sie.
- cowriter braucht **keinen eigenen HTTP-Client** für sieben verschiedene Provider – nr-llm liefert ihn.
- cowriter braucht **keine eigene Budget-Tabelle** – ADR-025 in nr-llm liefert sie.
- cowriter braucht **keine eigene Audit-Spur** – die liegt in nr-vault (für Geheimniszugriffe) und in `tx_nrllm_service_usage` (für Provider-Nutzung).

Eine zweite KI-Erweiterung – Meta-Description-Generator, semantische Suche, Klassifikator für Eingangskorrespondenz, was auch immer – kostet drei Zeilen Constructor Injection. Nicht ein neues HTTP-Client-Modul, nicht eine neue Settings-Maske, nicht ein neuer Audit-Pfad.

Das ist der Punkt der „resilient structures"-Idee, die sich durch andere Texte hier zieht: Implizite Abhängigkeiten reduzieren. Wenn jede neue KI-Erweiterung implizit voraussetzt, dass *sie* die Verschlüsselung lösen muss, *sie* den Provider auswählen muss, *sie* das Audit machen muss, dann skaliert das System nicht. Sobald diese Annahmen explizit in eine Schicht gebündelt sind, wird die nächste Erweiterung kleiner, nicht größer.

## Was bleibt zu tun

Der Stack ist live, alle drei Extensions sind als GPL-2.0 / GPL-3.0 veröffentlicht, mit SLSA-Level-3-Provenance, OpenSSF-Scorecard-Badge, signierten Artefakten und SBOMs in SPDX und CycloneDX. PHPStan Level 10. CI-Matrix über TYPO3 v13.4 und v14, PHP 8.2+. Das ist nicht das Interessante.

Das Interessante ist die nächste Erweiterung. Wer eine TYPO3-Extension baut, in der ein LLM eine Rolle spielt, hat heute eine Wahl: gegen `OPENAI_API_KEY` aus den Extension-Settings programmieren – oder gegen `LlmServiceManagerInterface` aus nr-llm. Die zweite Option ist nicht nur sauberer, sie ist auch kürzer.

Und das ist – am Ende – das einzige Argument für *jede* geteilte Infrastruktur, die etwas taugt: Sie macht die Sache, die sie löst, kleiner, nicht größer.

---

*Source code:* [`netresearch/t3x-nr-vault`](https://github.com/netresearch/t3x-nr-vault) · [`netresearch/t3x-nr-llm`](https://github.com/netresearch/t3x-nr-llm) · [`netresearch/t3x-cowriter`](https://github.com/netresearch/t3x-cowriter)
