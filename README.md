# Engineering Notes

A collection of essays, field notes and technical reflections on building
durable software systems, reducing knowledge silos, improving engineering
governance, and making complex technology understandable and maintainable.

These texts reflect my long-term interests: resilient teams, shared technical
knowledge, Open-Source maintainership, platform engineering, security, privacy,
and the pragmatic use of AI-assisted development. They are deliberately
curated and lightly maintained — every essay carries an *originally published*
date, an *updated* date when revised, and a status (`current`, `revised`,
`archived`, `historical`) so the reader can tell at a glance which pieces
still represent my current thinking.

— Sebastian Mendel, CTO at Netresearch DTT GmbH · [CV](https://cybottm.github.io/cv/) · [GitHub](https://github.com/CybotTM)

**Published site:** <https://cybottm.github.io/engineering-notes/>

## Layout

| Path | Purpose |
|---|---|
| `essays/<slug>.md` | One essay per file (Markdown + YAML front-matter) |
| `src/_thesis.md` | The thesis paragraph rendered on the index |
| `src/_abbreviations.md` | Markdown `abbr`-extension dictionary, appended to every essay before render |
| `templates/base.html.j2` | Jinja2 base layout (`<head>`, OG, JSON-LD, font preloads, inlined CSS) |
| `templates/essay.html.j2` | Single essay page |
| `templates/index.html.j2` | Reverse-chronological listing |
| `assets/style.css` | Editorial CSS, screen + print |
| `assets/fonts/*.woff2` | Self-hosted Source Serif 4 + Inter (variable, OFL) |
| `scripts/build.py` | The whole build: Markdown → HTML, JSON-LD per page |
| `requirements.txt` | Python deps (pinned) |
| `Makefile` | Convenience targets (`build`, `serve`, `lighthouse`, `clean`) |
| `.github/workflows/build.yml` | GitHub Actions: build, Lighthouse-CI on PRs, Pages deploy |
| `public/` | **Build artifact** — generated, not committed |

## Front-matter spec

Every essay starts with a YAML front-matter block. Required and optional
fields:

```yaml
---
# required
title: "Optimizing Claude Code Usage: Cache-Read Inflation"
originally_published: "2026-04"     # ISO date or YYYY-MM
summary: "One- to two-sentence description used in the essay's <meta description>, social previews, and the index card."

# optional, sensible defaults
slug: "optimizing-claude-code-cache-read-inflation"   # default = filename stem
updated: "2026-05-10"                                 # default = originally_published
status: "current"                                     # current | revised | archived | historical
topics:                                               # short slug-ish strings; rendered as topic chips and as JSON-LD keywords
  - ai-assisted-development
  - cost-engineering
lang: "de"                                            # default "de"; may be "en"
license: "CC-BY-4.0"                                  # default CC-BY-4.0 for prose; pin per-essay if different
---
```

Body is plain Markdown. The `<h1>` is rendered from `title:` in the
template, so the body should start at H2 (`## …`). Markdown's `abbr`
extension is on, so any token defined in `src/_abbreviations.md` (e.g.
`CTO`, `RFC`, `LDAP`) is automatically wrapped in `<abbr title="…">`.

## Build locally

You need Python 3.13+.

```bash
make install   # creates .venv/ and installs requirements.txt
make build     # writes public/index.html and public/essays/<slug>.html
make serve     # builds, then serves public/ on http://localhost:8000
```

## CI / publishing

- Every push and PR builds the site.
- PRs additionally run [`treosh/lighthouse-ci-action`](https://github.com/treosh/lighthouse-ci-action) and post results.
- Pushes to `main` deploy to GitHub Pages.

## License

Split license:

- **Code** — build pipeline, templates, stylesheet, configuration — under the
  **MIT License** (see [`LICENSE-MIT`](LICENSE-MIT)).
- **Essay content** — every Markdown file under `essays/`, plus
  `src/_thesis.md` and `src/_abbreviations.md` — under
  **Creative Commons Attribution 4.0 International** (CC-BY-4.0; see
  [`LICENSE-CC-BY-4.0`](LICENSE-CC-BY-4.0)).

When in doubt, **file extension wins**: `.py` / `.j2` / `.css` / `.svg` /
`.yml` / `.yaml` / `.json` / `.toml` / `Makefile` / `requirements.txt` are
under MIT; everything ending in `.md` is under CC-BY-4.0. Code files carry
an `SPDX-License-Identifier: MIT` header; essay front-matter optionally
carries a `license:` field.

Bundled fonts (Source Serif 4 and Inter) are distributed under the SIL Open
Font License 1.1 by their respective copyright holders.
