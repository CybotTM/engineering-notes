#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build the engineering-notes site from Markdown sources.

Reads `essays/*.md` (each with YAML front-matter), renders them through
Jinja2 templates, writes self-contained HTML to `public/`. Also writes a
landing `public/index.html` listing every essay reverse-chronologically
with a thesis paragraph from `src/_thesis.md`.

Cross-site identity: emits a `Person` JSON-LD node with @id pointing to
`https://cybottm.github.io/cv/#person`. The CV repo emits the canonical
Person there; both sites declare the same identity, search engines
treat the author as one entity across both URLs.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import markdown
import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

ROOT = Path(__file__).resolve().parent.parent
ESSAYS = ROOT / "essays"
ASSETS = ROOT / "assets"
TEMPLATES = ROOT / "templates"
SRC = ROOT / "src"
PUBLIC = ROOT / "public"

SITE_BASE = "https://cybottm.github.io/engineering-notes"
CV_BASE = "https://cybottm.github.io/cv"

AUTHOR = {
    "name": "Sebastian Mendel",
    "first_name": "Sebastian",
    "last_name": "Mendel",
    "linkedin": "https://linkedin.com/in/sebastian-mendel",
    "github": "https://github.com/CybotTM",
}

# Identity anchor — same @id as the CV repo's Person node so search engines
# treat both sites as one entity. This Person definition is the canonical
# public profile for cross-site linking; the CV repo embeds the fuller
# version with knowsAbout, hasOccupation, alumniOf, etc.
PERSON_ID = f"{CV_BASE}/#person"

PERSON_JSONLD = {
    "@type": "Person",
    "@id": PERSON_ID,
    "name": AUTHOR["name"],
    "givenName": AUTHOR["first_name"],
    "familyName": AUTHOR["last_name"],
    "url": f"{CV_BASE}/",
    "sameAs": [AUTHOR["linkedin"], AUTHOR["github"]],
}

WEBSITE_ID = f"{SITE_BASE}/#website"

WEBSITE_JSONLD = {
    "@type": "WebSite",
    "@id": WEBSITE_ID,
    "url": f"{SITE_BASE}/",
    "name": f"{AUTHOR['name']} — Engineering Notes",
    "inLanguage": ["de", "en"],
    "publisher": {"@id": PERSON_ID},
}

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


@dataclass
class Essay:
    """A single essay rendered from one Markdown source file."""

    slug: str
    front: dict
    body_md: str
    source_path: Path

    @property
    def url(self) -> str:
        return f"essays/{self.slug}.html"

    @property
    def canonical(self) -> str:
        return f"{SITE_BASE}/essays/{self.slug}.html"

    @property
    def article_id(self) -> str:
        return f"{self.canonical}#article"

    @property
    def source_url(self) -> str:
        rel = self.source_path.relative_to(ROOT).as_posix()
        return f"https://github.com/CybotTM/engineering-notes/blob/main/{rel}"


def parse_essay(path: Path) -> Essay:
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if not match:
        raise SystemExit(f"{path}: missing YAML front-matter (--- ... ---)")
    front = yaml.safe_load(match.group(1)) or {}
    for required in ("title", "originally_published", "summary"):
        if not front.get(required):
            raise SystemExit(f"{path}: missing required front-matter '{required}'")
    body = match.group(2)
    slug = front.get("slug") or path.stem
    return Essay(slug=slug, front=front, body_md=body, source_path=path)


def render_md(body: str) -> str:
    md = markdown.Markdown(
        extensions=["extra", "smarty", "sane_lists", "attr_list", "abbr", "toc"],
        output_format="html5",
    )
    return md.convert(body)


def load_inline_css(font_url_prefix: str) -> str:
    """Read assets/style.css and rewrite font URLs for inlining into HTML.

    The on-disk CSS at `assets/style.css` references fonts as
    `url("fonts/...")` — relative to the CSS file. When that CSS is
    *inlined* into an HTML page via <style>, the browser resolves
    `url(...)` relative to the HTML page, not the CSS file. So the
    rewrite has to match the HTML's depth on the site:

      depth 0 (e.g. /index.html)             →  font_url_prefix = "assets/fonts/"
      depth 1 (e.g. /essays/<slug>.html)     →  font_url_prefix = "../assets/fonts/"

    The preload hints emitted by the template use the same prefix via the
    `asset()` helper, so the preloaded font URL matches the @font-face
    URL exactly and the preload is reused.
    """
    css = (ASSETS / "style.css").read_text(encoding="utf-8")
    return re.sub(r'url\((\s*"?)fonts/', rf'url(\1{font_url_prefix}', css)


def load_abbreviations() -> str:
    path = SRC / "_abbreviations.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def load_thesis_html() -> str:
    """Render `src/_thesis.md` to HTML (no front-matter expected)."""
    path = SRC / "_thesis.md"
    if not path.exists():
        return ""
    return render_md(path.read_text(encoding="utf-8"))


def essay_jsonld(essay: Essay, breadcrumb: dict) -> dict:
    front = essay.front
    article = {
        "@type": "BlogPosting",
        "@id": essay.article_id,
        "url": essay.canonical,
        "mainEntityOfPage": essay.canonical,
        "headline": front["title"],
        "description": front["summary"],
        "datePublished": front["originally_published"],
        "dateModified": front.get("updated", front["originally_published"]),
        "inLanguage": front.get("lang", "de"),
        "author": {"@id": PERSON_ID},
        "publisher": {"@id": PERSON_ID},
        "isPartOf": {"@id": WEBSITE_ID},
        "breadcrumb": {"@id": breadcrumb["@id"]},
    }
    if front.get("topics"):
        article["keywords"] = ", ".join(front["topics"])
    if front.get("license"):
        article["license"] = front["license"]
    graph = [article, PERSON_JSONLD, WEBSITE_JSONLD, breadcrumb]
    return {"@context": "https://schema.org", "@graph": graph}


def index_jsonld(essays: list[Essay]) -> dict:
    blog_id = f"{SITE_BASE}/#blog"
    blog = {
        "@type": "Blog",
        "@id": blog_id,
        "url": f"{SITE_BASE}/",
        "name": f"{AUTHOR['name']} — Engineering Notes",
        "inLanguage": ["de", "en"],
        "publisher": {"@id": PERSON_ID},
        "blogPost": [{"@id": e.article_id} for e in essays],
    }
    collection = {
        "@type": "CollectionPage",
        "@id": f"{SITE_BASE}/#collectionpage",
        "url": f"{SITE_BASE}/",
        "name": f"{AUTHOR['name']} — Engineering Notes",
        "inLanguage": ["de", "en"],
        "isPartOf": {"@id": WEBSITE_ID},
        "about": {"@id": PERSON_ID},
        "mainEntity": {"@id": blog_id},
    }
    return {
        "@context": "https://schema.org",
        "@graph": [collection, blog, PERSON_JSONLD, WEBSITE_JSONLD],
    }


def essay_breadcrumb(essay: Essay) -> dict:
    return {
        "@type": "BreadcrumbList",
        "@id": f"{essay.canonical}#breadcrumb",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": 1,
                "name": "Engineering Notes",
                "item": f"{SITE_BASE}/",
            },
            {
                "@type": "ListItem",
                "position": 2,
                "name": "Essays",
                "item": f"{SITE_BASE}/",
            },
            {
                "@type": "ListItem",
                "position": 3,
                "name": essay.front["title"],
                "item": essay.canonical,
            },
        ],
    }


def render_essay(env: Environment, essay: Essay, abbr_block: str) -> str:
    front = essay.front
    body_md_with_abbr = essay.body_md + "\n\n" + abbr_block
    breadcrumb = essay_breadcrumb(essay)
    jsonld = essay_jsonld(essay, breadcrumb)
    tpl = env.get_template("essay.html.j2")
    return tpl.render(
        lang=front.get("lang", "de"),
        title=front["title"],
        description=front["summary"],
        canonical=essay.canonical,
        og_type="article",
        og_locale="de_DE" if front.get("lang", "de") == "de" else "en_US",
        author=AUTHOR,
        jsonld=json.dumps(jsonld, ensure_ascii=False),
        body=render_md(body_md_with_abbr),
        title_only=front["title"],
        originally_published=front["originally_published"],
        updated=front.get("updated"),
        status=front.get("status", "current"),
        topics=front.get("topics") or [],
        source_url=essay.source_url,
        home_url=f"{SITE_BASE}/",
        index_url=f"{SITE_BASE}/",
        inline_css=load_inline_css("../assets/fonts/"),
        asset=lambda p: f"../assets/{p}",
    )


def render_index(env: Environment, essays: list[Essay], thesis_html: str,
                 build_iso: str) -> str:
    jsonld = index_jsonld(essays)
    tpl = env.get_template("index.html.j2")
    return tpl.render(
        lang="de",
        title=f"{AUTHOR['name']} — Engineering Notes",
        description=(
            "Essays, field notes and technical reflections by "
            f"{AUTHOR['name']} on durable software systems, engineering "
            "governance, AI-assisted development, platform engineering, "
            "open source maintainership, security and documentation culture."
        ),
        canonical=f"{SITE_BASE}/",
        og_type="website",
        og_locale="de_DE",
        author=AUTHOR,
        jsonld=json.dumps(jsonld, ensure_ascii=False),
        thesis=thesis_html,
        essays=[
            {
                "title": e.front["title"],
                "summary": e.front["summary"],
                "url": e.url,
                "originally_published": e.front["originally_published"],
                "updated": e.front.get("updated"),
                "status": e.front.get("status", "current"),
                "topics": e.front.get("topics") or [],
            }
            for e in essays
        ],
        build_iso=build_iso,
        inline_css=load_inline_css("assets/fonts/"),
        asset=lambda p: f"assets/{p}",
    )


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()

    if PUBLIC.exists():
        shutil.rmtree(PUBLIC)
    PUBLIC.mkdir(parents=True)
    (PUBLIC / "essays").mkdir()

    shutil.copytree(ASSETS, PUBLIC / "assets")
    favicon = ASSETS / "favicon.svg"
    if favicon.exists():
        shutil.copy2(favicon, PUBLIC / "favicon.svg")

    sources = sorted(ESSAYS.glob("*.md"))
    if not sources:
        print("warning: no essays found under essays/; index will be empty")
    essays = [parse_essay(p) for p in sources]
    # Reverse chronological by originally_published — most recent first.
    essays.sort(key=lambda e: e.front["originally_published"], reverse=True)

    env = Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=True,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )

    abbr_block = load_abbreviations()
    thesis_html = load_thesis_html()
    now = datetime.now(timezone.utc).replace(microsecond=0)
    build_iso = now.isoformat()

    for essay in essays:
        html = render_essay(env, essay, abbr_block)
        out = PUBLIC / "essays" / f"{essay.slug}.html"
        out.write_text(html, encoding="utf-8")
        print(f"wrote {out.relative_to(ROOT)}")

    index_html = render_index(env, essays, thesis_html, build_iso)
    (PUBLIC / "index.html").write_text(index_html, encoding="utf-8")
    print(f"wrote public/index.html ({len(essays)} essays)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
