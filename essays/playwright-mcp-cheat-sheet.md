---
title: "Playwright MCP – Cheat Sheet"
slug: "playwright-mcp-cheat-sheet"
originally_published: "2025-08-07"
updated: "2026-05-10"
status: "current"
topics:
  - mcp
  - browser-testing
  - tooling-reference
summary: "Praxisnahes Cheat Sheet zum Playwright MCP Server: Was MCP wirklich bedeutet, wie das offizielle Docker-Image funktioniert, wann manuelles Mounting nötig ist und wie sich der Server in Agenten-Editoren und CI/CD-Pipelines einbinden lässt."
lang: "de"
license: "CC-BY-4.0"
---

> Dieses Cheat Sheet richtet sich an Entwickler:innen, DevOps-Teams und Tool-Integratoren, die den **Playwright MCP Server** zur browsergestützten Webautomatisierung über LLMs (Sprachmodelle) einsetzen möchten. *Stand: August 2025 — bei browser-spezifischen Aussagen lohnt sich vor dem Einsatz ein Blick in die aktuellen Release Notes.*

---

## Integration mit Agenten-/Editor-Umgebungen

> **Hinweis:** Agentenfähige Entwicklungsumgebungen (z. B. LLM-gesteuerte Editoren oder Tools mit integrierter MCP-Unterstützung) mounten das Projektverzeichnis beim Start des MCP-Containers in der Regel **automatisch**.
> ➔ Ein *manuelles Mounting* ist nur erforderlich, wenn du MCP direkt über Docker oder eigene Pipelines betreibst.

| Verhalten | Erklärung |
| --- | --- |
| Projekt-Mount | Automatisch durch Editor oder Agentenumgebung |
| `playwright.config.ts` | Muss im Projektverzeichnis vorhanden sein |
| Zusatzflags (`-v`, `-w`) | Nicht erforderlich bei automatischer Mount-Logik |
| Eigene Nutzung (Shell, CI, Docker direkt) | Manuelles Mounting notwendig |

➔ In unterstützten Umgebungen erkennt der Agent das Projektverzeichnis automatisch und stellt es MCP zur Verfügung.

---

## Begriffsklärung: Was bedeutet MCP?

| Kontext | Bedeutung |
| --- | --- |
| **Playwright MCP** (offiziell) | **Model Context Protocol** |
| Modular Control Plane | *nicht* gemeint im Kontext dieses Projekts |
| Zweck | Verbindung von LLM-Agenten mit browserbasierter Webautomatisierung über ein standardisiertes Protokoll |

Quelle: [GitHub – microsoft/playwright-mcp](https://github.com/microsoft/playwright-mcp)

---

## Was ist das Model Context Protocol?

- Standardisiertes **JSON-RPC-Protokoll**
- Ermöglicht Sprachmodellen Zugriff auf Werkzeuge (Browser, Filesystem, Git, Shell etc.)
- Playwright fungiert als **Tool Server**, der über MCP Webautomation ausführt
- Typische Nutzung: *LLM-Agent klickt/scrollt/füllt Formulare aus* via Browser

---

## Docker: `mcr.microsoft.com/playwright/mcp`

| Komponente | Enthalten? | Hinweis |
| --- | --- | --- |
| `@playwright/mcp` | Ja | MCP-Server |
| Playwright Core | Ja | Playwright CLI & API |
| Browser (Chrome etc.) | Nur *headless Chromium* (Stand August 2025) | siehe Hinweis unten |
| Tests deines Projekts | Nein | müssen *gemountet* werden (siehe oben) |

### Manuelles Mounting

```bash
# Führt den MCP-Server aus und bindet das Projektverzeichnis ein
docker run --rm -p 3000:3000 \
  -v $(pwd):/tests \
  -w /tests \
  mcr.microsoft.com/playwright/mcp
```

> **Wichtig (Stand August 2025):** Das Docker-Image unterstützt zu diesem Zeitpunkt **nur headless Chromium**. Andere Browser oder headed mode sind nicht verfügbar. Aktueller Stand: [GitHub – Hinweis zur Docker-Einschränkung](https://github.com/microsoft/playwright-mcp#note-the-docker-implementation-only-supports-headless-chromium-at-the-moment).

---

## CI/CD-Pipelines mit MCP verwenden

Ja – das offizielle Docker-Image ist **CI-tauglich**.

- Kann in GitHub Actions, GitLab CI, Jenkins etc. verwendet werden
- Du musst:
  - das Projektverzeichnis mounten (`-v`)
  - oder dein Repo im Container clonen
- Du verwendest dabei **nicht das System-Playwright**, sondern **das im Container vorinstallierte Playwright + Browser**

Beispiel-Step in der Pipeline (GitHub Actions):

```yaml
- name: Run MCP server
  run: docker run --rm -v ${{ github.workspace }}:/tests -w /tests mcr.microsoft.com/playwright/mcp
```

---

## Häufige Missverständnisse

| Aussage | Status | Erklärung |
| --- | --- | --- |
| „MCP = Modular Control Plane" | falsch | Nicht im Kontext dieses Projekts vorhanden |
| „Container sieht meine Tests automatisch" | nur mit Mounting | manuell oder automatisch durch Agenten |
| „MCP = Test Runner" | nein | Fokus liegt auf *Automation via LLM*, nicht auf klassischer Testverteilung |

---

## Manuelles Setup lokal (ohne Agent)

```bash
npx @playwright/mcp@latest                 # MCP lokal starten
npx playwright install chrome              # Browser manuell installieren
docker run -v $(pwd):/tests -w /tests mcr.microsoft.com/playwright/mcp
```

---

## Ressourcen

- GitHub: <https://github.com/microsoft/playwright-mcp>
- MCP-Protokoll: <https://modelcontextprotocol.io/>
- Docker Image: <https://mcr.microsoft.com/en-us/product/playwright/mcp>

---

## TL;DR

- **MCP = Model Context Protocol**, nicht Modular Control Plane
- Container ist vollständig, aber **sieht Tests nur mit Mount**
- Automatisches Mounting bei unterstützten Entwicklungsumgebungen
- Direkt nutzbar in **CI/CD** – verwendet das im Container integrierte Playwright + Browser-Setup
- *Stand August 2025: Nur headless Chromium wird im Docker-Image unterstützt — vor Einsatz in 2026+ aktuelle Release Notes prüfen*

---

## Glossar

| Begriff | Erklärung |
| --- | --- |
| **MCP** | *Model Context Protocol* – ein JSON-RPC-Standard zur Kommunikation zwischen Sprachmodellen und Tools |
| **Playwright** | Framework zur Automatisierung von Browser-Interaktionen (ähnlich wie Puppeteer) |
| **Headless** | Ausführung eines Browsers ohne sichtbare Benutzeroberfläche (GUI) |
| **Tool Server** | Ein Prozess, der über MCP Kommandos empfängt und in Tools ausführt (z. B. Browseraktionen) |
| **Mounting** | Das Einbinden eines lokalen Verzeichnisses in einen Container per Docker (`-v`) |
| **CI/CD** | *Continuous Integration / Continuous Deployment* – automatisierte Build-, Test- und Deploymentprozesse |
| **LLM-Agent** | Ein KI-Modell (z. B. GPT), das über Protokolle wie MCP externe Aktionen auslöst |

---

*Originally published as an internal Netresearch wiki article in August 2025. Republished here lightly edited for public context.*
