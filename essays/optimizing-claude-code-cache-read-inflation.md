---
title: "Optimizing Claude Code Usage: Addressing Cache-Read Inflation and Token Costs"
slug: "optimizing-claude-code-cache-read-inflation"
originally_published: "2026-04"
updated: "2026-05-10"
status: "current"
topics:
  - ai-assisted-development
  - cost-engineering
  - observability
summary: "Long Claude Code sessions get expensive not because individual tool calls are costly, but because large tool outputs stay in context and re-pay cache-read on every subsequent turn — growing quadratically. Three concrete measures (statusline, PreToolUse hook, memory rule) make the cost visible and shift the default toward subagents."
lang: "de"
license: "CC-BY-4.0"
---

Claude Code ist mächtig. Aber wer längere Sessions fährt, zahlt schnell für etwas, das sich im Moment gar nicht teuer anfühlt: wachsenden Kontext.

Das Problem ist nicht der eine `Read`, `Grep` oder `Bash`-Call. Das Problem ist, dass große Tool-Ausgaben und Inline-Analysen aus früheren Turns im Kontext bleiben und bei jedem weiteren Turn erneut als Cache-Read auftauchen. Bei langen Sessions wirkt das schnell quadratisch.

Eine reale Session-Analyse sah so aus:

| Metrik         | Erwartet  | Real    | Faktor |
| -------------- | --------- | ------- | ------ |
| Kosten         | ~$10      | $10.31  | ok     |
| Output-Tokens  | 30–50k    | 90.5k   | ~2×    |
| Cache-Read     | 400k      | 13.5M   | ~30×   |
| Active-Time    | 10–15 min | 23 min  | ~2×    |

Die Kosten lagen am Ende zwar noch im erwarteten Bereich. Aber die Struktur dahinter war eindeutig: Der eigentliche Kostentreiber war nicht Output, sondern Cache-Read-Inflation.

## Das eigentliche Problem: Claude sieht die Rechnung nicht

Claude Code fühlt sich im Tool-Loop oft so an:

> "Ich lese schnell noch diese Datei."
> "Ich greppe noch ein bisschen."
> "Ich analysiere das direkt inline."

Für Claude ist das bequem. Für die Rechnung ist es schlecht.

Denn alles, was groß im Chat landet, bleibt Kontext. Und dieser Kontext wird bei jedem weiteren Turn wieder mitgeschleppt. Aus einem harmlosen großen `Read` wird bei elf weiteren Turns ein dauerhafter Kostenblock.

Subagents wären hier oft günstiger, weil sie mit isoliertem Kontext arbeiten und nur eine Zusammenfassung zurückgeben. In der Praxis werden sie aber zu selten genutzt, weil ihre Reibung sichtbar ist, während die Kosten von Inline-Reads unsichtbar bleiben.

Die Lösung ist deshalb nicht "mehr Disziplin". Das funktioniert nicht zuverlässig.

Die Lösung ist: **Sichtbarkeit, automatische Warnungen und bessere Defaults.**

---

## Drei Maßnahmen gegen Cache-Read-Inflation

### 1. Statusline mit Live-Token-Counter

Die Statusline zeigt direkt in Claude Code:

```
~/p/projekt (✓ main PR#42)  │ ctx 87k · ↻ 1.2M · $0.84
```

Bedeutung:

| Anzeige  | Bedeutung                                                |
| -------- | -------------------------------------------------------- |
| `ctx`    | aktuelle Kontextgröße (absolute Tokens, nicht Prozent)   |
| `↻`      | kumulative Cache-Reads der Session                       |
| `$`      | geschätzte Session-Kosten                                |
| Git-Info | Branch, Dirty-State, PR-Nummer                           |

**Wichtig — die 200k-Schwelle:**

- **Pro Turn linear, kumulativ quadratisch**. Bei 200k Kontext zahlt jeder Folge-Turn 200k Cache-Read. Über N Turns wächst der kumulative Verbrauch mit O(N²) — also immer schneller, je länger die Session läuft. Bei 50k Kontext ist die Brenngeschwindigkeit ein Viertel.
- **Context-Rot**. Anthropic dokumentiert selbst: „as token count grows, accuracy and recall degrade". 200k ist keine harte Grenze, aber im Bereich darüber werden Korrektur-Turns sichtbar häufiger — und jeder zusätzliche Turn multipliziert den Quadratterm weiter.
- **Tooling-Erbe**. Subagents, Skills, Memory-Setups und viele RAG-Integrationen sind für 200k gebaut. Past 200k truncieren manche Pfade leise.

Die Statusline zeigt das in drei Bändern:

| Kontext    | Anzeige                                          | Bedeutung                                                  |
| ---------- | ------------------------------------------------ | ---------------------------------------------------------- |
| `< 150k`   | grün `ctx 87k`                                   | unauffällig                                                |
| `150–200k` | gelb `ctx 175k`                                  | Session wird fett — Aufräumen lohnt                        |
| `≥ 200k`   | **fett weiß auf rot** `⚠ ctx 215k OVER 200k`     | Aufwand wächst quadratisch — `/compact` oder neue Session  |

Das Ziel ist simpel: Wenn ↻ plötzlich um 2M springt, sieht man es sofort. Und wenn `ctx` die Schwelle überschreitet, lässt es sich nicht ignorieren.

### 2. PreToolUse-Hook für große Reads

Der Hook warnt automatisch, wenn Claude eine Datei mit mindestens 500 Zeilen komplett lesen will.

Er verhindert nichts hart. Er macht aber sichtbar, dass gerade ein teurer Reflex passiert:

```
Large-file warning: /path/foo.py has 1200 lines.
Reading the whole file inflates the context and re-pays cache-read cost on every subsequent turn.
Prefer Serena, Explore agent, Grep, jq/yq or Read with offset+limit.
```

Das ist wichtig: Claude soll nicht "aus Versehen" große Dateien komplett in den Kontext ziehen.

### 3. Memory-Regel: Multi-Step-Recherche standardmäßig an Subagents

Die Memory-Regel verschiebt den Default:

- mehr als zwei erwartete Tool-Calls → Subagent
- große Outputs → Datei schreiben, Pfad referenzieren
- große Code-Dateien → Serena/Grep statt Full-Read
- strukturierte Daten → `jq`, `yq`, `xmlstarlet`, Miller statt kompletter Kontext
- One-Off-Lookups bleiben direkt

Das ist der eigentliche Hebel. Die Statusline zeigt das Problem. Der Hook bremst den Reflex. Die Memory-Regel verändert das Verhalten dauerhaft.

---

## Setup in 5 Minuten

Die folgenden Beispiele nutzen `$HOME` und laufen direkt unter Linux, WSL und macOS.

### 1. Statusline-Skript anlegen

```bash
mkdir -p ~/.claude/hooks

cat > ~/.claude/statusline.sh <<'SCRIPT'
#!/bin/bash
# Statusline: cwd + venv + git + token usage + estimated cost
# Format: ~/path (venv) (✓ branch PR#42)  │ ctx 87k · ↻ 1.2M · $0.84
# Bei ctx >= 200k: rote Warnung wegen Opus 1M-Tier-Kosten-Klippe.

input=$(cat)
transcript=$(jq -r '.transcript_path // empty' <<<"$input")

p=${PWD/#$HOME/\~}
v=""
[ -n "$VIRTUAL_ENV" ] && v=" (${VIRTUAL_ENV##*/})"

g=""
if git rev-parse --git-dir &>/dev/null; then
    b=$(git branch --show-current 2>/dev/null || echo HEAD)
    s="✓"
    [ -n "$(git status -s 2>/dev/null)" ] && s="●"
    pr=""
    n=$(gh pr view --json number -q .number 2>/dev/null) && [ -n "$n" ] && pr=" PR#$n"
    g=" ($s $b$pr)"
fi

# ANSI colors via bash $'...' (real ESC byte) — passed into jq as --arg.
RED=$'\e[1;97;41m'   # bold white on red — 200k cost-cliff warning
YEL=$'\e[33m'        # yellow — approaching cliff
RST=$'\e[0m'

# Pricing (Opus 4 approx, USD/M tokens): in $15, out $75, cache_write $22, cache_read $1.50
# Für Sonnet: in/out durch 5 teilen ($3/$15)
tokens=""
if [[ -n "$transcript" && -f "$transcript" ]]; then
    tokens=$(jq -rs --arg red "$RED" --arg yel "$YEL" --arg rst "$RST" '
        [.[] | .message.usage // empty] |
        if length == 0 then ""
        else
            (last.input_tokens // 0) as $li |
            (last.cache_read_input_tokens // 0) as $lcr |
            (last.cache_creation_input_tokens // 0) as $lcw |
            ($li + $lcr + $lcw) as $ctx |

            ([.[] | .cache_read_input_tokens // 0]     | add) as $cr |
            ([.[] | .output_tokens // 0]                | add) as $out |
            ([.[] | .input_tokens // 0]                 | add) as $in |
            ([.[] | .cache_creation_input_tokens // 0] | add) as $cw |

            (($in * 15 + $out * 75 + $cw * 22 + $cr * 1.5) / 1000000) as $cost |

            def fmt(n):
              if n >= 1000000 then "\(((n/100000)|floor)/10)M"
              elif n >= 1000  then "\((n/1000)|floor)k"
              else (n|tostring) end;

            (if   $ctx >= 200000 then "\($red)⚠ ctx \(fmt($ctx)) OVER 200k\($rst)"
             elif $ctx >= 150000 then "\($yel)ctx \(fmt($ctx))\($rst)"
             else "ctx \(fmt($ctx))" end) as $ctx_disp |

            "  │ \($ctx_disp) · ↻ \(fmt($cr)) · $\(((($cost*100)|floor)/100))"
        end
    ' "$transcript" 2>/dev/null)
fi

echo "$p$v$g$tokens"
SCRIPT

chmod +x ~/.claude/statusline.sh
```

### 2. PreRead-Hook anlegen

```bash
cat > ~/.claude/hooks/pre-read-warn.sh <<'SCRIPT'
#!/bin/bash
# PreToolUse hook for Read: warn at >=500 lines, suggest cheaper alternatives.
set -e

input=$(cat)

file_path=$(jq -r '.tool_input.file_path // empty' <<<"$input")
[[ -z "$file_path" || ! -f "$file_path" ]] && exit 0

# Skip if user already specified offset/limit (intentional partial read)
limit=$(jq -r '.tool_input.limit // empty' <<<"$input")
[[ -n "$limit" ]] && exit 0

lines=$(wc -l <"$file_path" 2>/dev/null || echo 0)
[[ "$lines" -lt 500 ]] && exit 0

ext="${file_path##*.}"

case "$ext" in
    py|js|ts|tsx|jsx|mjs|cjs|go|rs|java|php|rb|c|cpp|cc|h|hpp|cs|swift|kt|scala|lua|elm|ex|exs)
        sugg="Prefer Serena (find_symbol, get_symbols_overview, find_referencing_symbols) for targeted code lookup, the Explore agent for multi-file investigation, or Grep for specific patterns. Use Read with offset+limit if you only need a section." ;;
    md|rst|txt|adoc|tex)
        sugg="Prefer the Explore agent for content search, Grep for specific terms, or Read with offset+limit for sections." ;;
    json|yaml|yml|toml|xml|csv|tsv|ndjson|jsonl)
        sugg="Prefer the data-tools skill (jq/yq/xmlstarlet/miller) for structured queries instead of reading the whole file." ;;
    log|out|err)
        sugg="Prefer tail/grep via Bash, or Read with offset to read recent entries only." ;;
    sql)
        sugg="Prefer Grep for specific table/column names, or Read with offset+limit." ;;
    *)
        sugg="Prefer the Explore agent for investigation, Grep for patterns, or Read with offset+limit for sections." ;;
esac

lines_disp=$lines
[[ $lines -ge 10000 ]] && lines_disp="$((lines / 1000))k"

jq -nc --arg msg "Large-file warning: ${file_path} has ${lines_disp} lines. Reading the whole file inflates the context and re-pays cache-read cost on every subsequent turn. ${sugg} If you genuinely need the full file, proceed — otherwise switch approach." '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    additionalContext: $msg
  }
}'
SCRIPT

chmod +x ~/.claude/hooks/pre-read-warn.sh
```

### 3. `settings.json` patchen

In `~/.claude/settings.json` diese beiden Blöcke ergänzen.

Wichtig: **nicht blind ersetzen**, sondern in bestehende Konfiguration mergen.

```json
{
  "statusLine": {
    "type": "command",
    "command": "bash $HOME/.claude/statusline.sh"
  },
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Read",
        "hooks": [
          {
            "type": "command",
            "command": "bash $HOME/.claude/hooks/pre-read-warn.sh",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

Danach validieren:

```bash
jq empty ~/.claude/settings.json && echo "JSON OK"
jq -r '.hooks.PreToolUse[] | "matcher=\(.matcher)"' ~/.claude/settings.json
```

### 4. Memory-Regel ergänzen

Der Memory-Pfad ist projektabhängig:

```bash
ls -d ~/.claude/projects/*/memory/ 2>/dev/null
```

Dann den passenden Pfad setzen:

```bash
MEM_DIR=~/.claude/projects/-home-$USER-p/memory  # ggf. anpassen
mkdir -p "$MEM_DIR"
```

Memory-Datei anlegen:

```bash
cat > "$MEM_DIR/feedback_subagent-default.md" <<'EOF'
---
name: subagent-default-multistep
description: Default to Explore/general-purpose subagent for multi-step research; write large outputs to files. Reduces cache-read inflation across subsequent turns.
type: feedback
---

For any multi-step research/lookup task (>2 anticipated tool calls), default to a subagent (Explore for searches, general-purpose for multi-step research) rather than running Grep/Read/Glob inline. Same for large outputs (>~100 lines) — write to a file, reference the path in chat.

**Why:** Cost analysis showed 13.5M cumulative cache-reads (~30× higher than expected) driven by large tool outputs and long inline analyses staying in context across all subsequent turns. With N retained turns × growing context, cache-read cost grows quadratically. Subagents have isolated context — only their summary returns. Token cost is invisible at runtime, so without this hard default Claude drifts toward inline work that *feels* lighter but isn't.

**How to apply:**
- Multi-step search/analysis (>2 tool calls anticipated) → Explore/general-purpose agent default, not inline Read/Grep/Glob.
- Large/repetitive outputs → write to file, reference the path in chat.
- For large code files: prefer Serena symbol-ops or Grep over Read of the whole file.
- For structured data: data-tools skill (jq/yq) for targeted queries.
- One-off direct lookups still use the direct tool — this rule is about multi-step work.
- The PreToolUse hook on large Reads (≥500 lines) enforces this; treat its warning as the rule firing, not advice.
EOF
```

In `MEMORY.md` indexieren:

```bash
echo "- [feedback_subagent-default.md](feedback_subagent-default.md) — Multi-step research → subagent default; large outputs → files, not inline." >> "$MEM_DIR/MEMORY.md"
```

---

## Was man danach sieht

### Statusline

Im grünen Bereich:

```
~/p/projekt (✓ main PR#42)  │ ctx 87k · ↻ 1.2M · $0.84
```

In der Annäherungszone (gelb ab 150k):

```
~/p/projekt (✓ main PR#42)  │ ctx 175k · ↻ 4.8M · $4.20
```

Über der Klippe (fett weiß auf rot ab 200k):

```
~/p/projekt (✓ main PR#42)  │ ⚠ ctx 215k OVER 200k · ↻ 6.3M · $9.10
```

| Wert  | Interpretation                                                       |
| ----- | -------------------------------------------------------------------- |
| `ctx` | aktuelle Kontextgröße in Tokens, die bei Folge-Turns wieder relevant wird |
| `↻`   | kumulative Cache-Reads über die Session                              |
| `$`   | grobe Kostenschätzung auf Basis der hinterlegten Preise              |

### Hook-Warnung

Sobald Claude eine große Datei komplett lesen möchte:

```
Large-file warning: /path/foo.py has 1200 lines.
Reading the whole file inflates the context and re-pays cache-read cost on every subsequent turn.
Prefer Serena, Explore agent, Grep, jq/yq or Read with offset+limit.
```

Das ist kein Verbot. Aber es ist der richtige Moment, die Arbeitsweise zu wechseln.

---

## Daumenregeln für die Praxis

| Signal                                            | Bedeutung                                                              | Reaktion                                              |
| ------------------------------------------------- | ---------------------------------------------------------------------- | ----------------------------------------------------- |
| `↻ < 500k`, langsam steigend                      | normal                                                                 | weiterarbeiten                                        |
| `↻` springt um `> 500k` in einem Turn             | großer Tool-Output kam zurück                                          | prüfen, ob Inline wirklich nötig war                  |
| `ctx ≥ 150k` (gelb)                               | Per-Turn-Last steigt merklich                                          | Ausgaben prüfen, ggf. `/compact`                      |
| `ctx ≥ 200k` (⚠ rot)                              | jeder Folge-Turn zahlt voll auf den großen Kontext, Context-Rot setzt ein | sofort `/compact` oder neue Session                |
| `$ > $5`                                          | wahrscheinlich zu viel inline gemacht                                  | mehr delegieren, Session kürzen                       |
| große Datei ohne `limit`                          | Kontext wird unnötig aufgeblasen                                       | `offset+limit`, Grep, Serena oder Subagent            |
| Multi-Step-Recherche                              | Inline-Tooling wird teuer                                              | Explore/general-purpose Subagent                      |

---

## Weitere Regeln, die sich bewährt haben

### Nutzt Claude Code nur dort, wo Claude Code wirklich gebraucht wird

Wenn ihr nicht direkt am Code arbeitet, ist Claude Code oft das falsche Werkzeug.

Für Recherche, Dokumentation, Analyse, Zusammenfassungen oder Architektur-Denken reichen häufig:

- ChatGPT
- [Google AI](https://www.google.com/search?udm=50)
- [Gemini](https://gemini.google.com/app)
- [Google AI Studio](https://aistudio.google.com/)
- [NotebookLM](https://notebooklm.google.com/)
- klassische Web-Recherche
- Atlassian Rovo

Claude Code ist stark, wenn es im Repository arbeitet. Für reine Denk- und Textarbeit ist es oft unnötig teuer.

### Sonnet als Arbeitsmodell, Opus als Advisor

Pragmatischer Default:

```
/model Sonnet
/advisor Opus
```

Sonnet erledigt die laufende Arbeit günstiger. Opus kommt dazu, wenn Urteil, Architektur oder Review-Qualität wichtiger sind als Rohdurchsatz.

### Sessions kurz halten

Lange Sessions sind bequem, aber teuer.

Jede große Ausgabe, jede Zwischenanalyse, jede Datei im Kontext erhöht die Folgekosten. Deshalb:

- häufiger `/compact`
- bei Themenwechsel neue Session
- große Analyseergebnisse in Dateien schreiben
- Subagents statt Inline-Recherche
- keine langen "noch kurz"-Ketten

"Eine Session für alles" ist fast immer die falsche Kostenstrategie.

### Skills und CLI-Tools bereitstellen

Claude wird günstiger, wenn es präzise Werkzeuge nutzen kann.

Beispiele:

| Aufgabe                    | Besseres Werkzeug    |
| -------------------------- | -------------------- |
| JSON analysieren           | `jq`                 |
| YAML analysieren           | `yq`                 |
| XML analysieren            | `xmlstarlet`         |
| CSV/TSV analysieren        | Miller / `mlr`       |
| Code-Struktur finden       | Serena               |
| Textmuster finden          | Grep / ripgrep       |
| große Recherche            | Explore/Subagent     |
| wiederkehrende Projektlogik | Skill               |

Der schlechteste Weg ist oft: komplette Datei lesen und dann im Chat "verstehen".

### `/insights` und `/status` nutzen

Fragt regelmäßig:

```
/insights mit fokus auf tokenverbrauch
```

um zu sehen, wo Tokens hingegangen sind.

Achtet außerdem auf:

```
/status
```

und dort insbesondere auf die Usage-Hinweise.

Diese Befehle sind keine Deko. Sie sind Feedback-Loops. Ohne Feedback optimiert man nur nach Gefühl — und Gefühl ist bei Tokenkosten unzuverlässig.

### Am Ende eine kurze Retro machen

Am Session-Ende lohnt sich eine Mini-Retro:

- Welche Reads waren unnötig groß?
- Welche Greps hätten Subagents sein sollen?
- Welche Outputs hätten in Dateien gehört?
- Welche Skills haben Tokens gespart?
- Welche Skills fehlen noch?
- Wo ist der Kontext unnötig gewachsen?
- Was sollte als Skill-Verbesserung oder Memory-Regel persistiert werden?

Ziel ist nicht Selbstbeschäftigung. Ziel ist, die nächste Session billiger und präziser zu machen.

---

## Anpassungen

### Zeilenschwelle ändern

Standard ist 500 Zeilen:

```bash
[[ "$lines" -lt 500 ]] && exit 0
```

Für strengere Setups z. B. auf 300 setzen.

### ctx-Warnschwellen ändern

Defaults sind 150k (gelb) und 200k (rote Warnung). Im jq-Block der Statusline anpassen:

```
(if   $ctx >= 200000 then "\($red)⚠ ctx \(fmt($ctx)) OVER 200k\($rst)"
 elif $ctx >= 150000 then "\($yel)ctx \(fmt($ctx))\($rst)"
 else "ctx \(fmt($ctx))" end) as $ctx_disp |
```

Schwellen, Farben und Text lassen sich frei ändern.

### Pricing ändern

Im Statusline-Skript sind die Default-Werte auf Opus ausgelegt:

```
input        $15 / M tokens
output       $75 / M tokens
cache write  $22 / M tokens
cache read   $1.50 / M tokens
```

Für Sonnet die Input-/Output-Werte entsprechend reduzieren, z. B.:

```
input  $3
output $15
```

### Hook deaktivieren

Entweder den `PreToolUse`-Eintrag aus `settings.json` entfernen oder in Claude Code über `/hooks` toggeln.

### Hot Reload

`settings.json` wird in der Regel live übernommen. Falls nicht:

```
/hooks
```

öffnen oder die Session neu starten.

---

## Warum diese Kombination funktioniert

Die drei Maßnahmen greifen auf unterschiedlichen Ebenen:

| Maßnahme     | Ebene           | Wirkung                                                              |
| ------------ | --------------- | -------------------------------------------------------------------- |
| Statusline   | Sichtbarkeit    | macht Kontext und Cache-Reads sichtbar; markiert die 200k-Kosten-Klippe |
| Hook         | Reflexkontrolle | warnt bei teuren Standardhandlungen                                  |
| Memory-Regel | Verhalten       | verschiebt den Default auf Subagents und Dateien                     |

Einzeln hilft jede Maßnahme. Zusammen entsteht ein robusteres System.

Die wichtigste Erkenntnis ist unbequem, aber simpel:

> Claude Code wird nicht teuer, weil ein einzelner Tool-Call teuer ist.
> Claude Code wird teuer, weil große Zwischenergebnisse im Kontext bleiben und in langen Sessions immer wieder mitbezahlt werden.

Wer das sichtbar macht und die Defaults ändert, spart nicht nur Geld. Die Arbeit wird auch sauberer: weniger Chat-Müll, weniger Kontextballast, bessere Recherchetrennung, klarere Session-Grenzen.

Der beste Kosten-Hack ist nicht ein billigeres Modell.
Der beste Kosten-Hack ist weniger unnötiger Kontext.

---

*Originally published as an internal Netresearch wiki article in April 2026. Republished here lightly edited for public context.*
