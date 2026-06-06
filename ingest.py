"""
ingest.py — Milestone 3: Document ingestion and chunking.

Pipeline stages implemented here (see planning.md → Architecture):
    Document Ingestion  ->  Chunking

What this script does:
    1. load_documents() : fetch each source URL, strip HTML/boilerplate down to
       plain text, and cache the result as a .txt file in documents/.
    2. chunk_text()     : split each document into overlapping chunks using a
       recursive character splitter (chunk size 600, overlap 50 — per planning.md).
    3. main()           : run both stages and write chunks.json (chunks + source
       metadata) for the embedding stage (Milestone 4) to consume.

Run:
    python ingest.py            # fetch only missing sources, then chunk
    python ingest.py --no-fetch # never fetch; chunk whatever .txt is in documents/
    python ingest.py --refetch  # force re-download of all web sources (overwrites)

Fetching is incremental by default: a source is downloaded only when its
documents/<slug>.txt is missing or empty. Existing files — including ones you
have hand-cleaned — are left untouched, so re-running never clobbers your edits.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

DOCS_DIR = Path("documents")
CHUNKS_FILE = Path("chunks.json")

CHUNK_SIZE = 600   # characters, per planning.md → Chunking Strategy
CHUNK_OVERLAP = 50  # characters

# Recursive splitter separators, tried in order from coarsest to finest.
# This keeps paragraphs / sentences intact when a chunk would otherwise be
# split mid-thought.
SEPARATORS = ["\n\n", "\n", ". ", " ", ""]

# A real browser UA — several of these sites return 403 to the default
# python-requests agent.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


@dataclass
class Source:
    """One row of the Documents table in planning.md."""
    slug: str            # used as the .txt filename and chunk metadata id
    name: str            # human-readable source name
    url: str
    manual: bool = False  # True = never auto-fetch; always read the curated
    #                       documents/<slug>.txt (the site blocks scraping or
    #                       is JS-rendered, so the file was added by hand).


# The 10 sources from planning.md → Documents.
SOURCES: list[Source] = [
    Source(
        "student-activities-list",
        "Student Activities List",
        "https://studentactivities.brown.edu/student-groups/undergraduate-student-groups",
        manual=True,  # JS-rendered group list; curated by hand
    ),
    Source(
        "category-breakdown",
        "Category Breakdown",
        "https://www.brownucs.org/category-breakdown",
    ),
    Source(
        "reddit-club-recommendations",
        "Reddit: Club Recommendations",
        "https://www.reddit.com/r/BrownU/comments/14dig65/any_ideas_for_clubs_to_join_or_extracurriculars/",
        manual=True,  # Reddit blocks scraping (403); curated by hand
    ),
    Source(
        "club-culture",
        "Club culture",
        "https://www.browndailyherald.com/article/2024/10/cutthroat-or-collaborative-is-browns-club-culture-competitive",
    ),
    Source(
        "most-prestigious-clubs",
        "Most Prestigious Clubs",
        "https://www.collegevine.com/faq/154640/what-are-the-most-prestigious-student-organizations-at-brown-university",
        manual=True,  # hand-cleaned (CollegeVine chancing-widget boilerplate)
    ),
    Source(
        "hercampus-guide",
        "HerCampus Guide",
        "https://www.hercampus.com/school/brown/a-guide-to-clubs-at-brown-two-tips-for-success/",
    ),
    Source(
        "overview-faq",
        "Overview / FAQ",
        "https://admissionsight.com/brown-university-clubs/",
        manual=True,  # hand-cleaned
    ),
    Source(
        "application-process",
        "Application Process",
        "https://www.browndailyherald.com/article/2020/01/schmidt-21-university-student-organizations-have-room-to-be-more-inclusive",
    ),
    Source(
        "pre-professional-selectivity",
        "Pre-Professional Club Selectivity",
        "https://www.browndailyherald.com/article/2025/10/pre-professional-club-leaders-note-influx-of-eager-first-year-applicants",
    ),
    Source(
        "activities-fair-experience",
        "Activities Fair Experience",
        "https://www.browndailyherald.com/article/2025/09/student-activities-fair-welcomes-first-years-with-music-treats-and-pirate-games",
    ),
]


# --------------------------------------------------------------------------- #
# Stage 1: Document ingestion
# --------------------------------------------------------------------------- #

def fetch_url(url: str) -> bytes:
    """Return the raw bytes for a URL.

    Returning bytes (not str) lets BeautifulSoup detect the real encoding from
    the page's <meta charset>, which avoids the mojibake you get when requests
    guesses wrong on smart quotes/apostrophes.

    Google Docs 'edit' links are rewritten to the plain-text export endpoint so
    we get the document body instead of the editor shell.
    """
    m = re.search(r"docs\.google\.com/document/d/([A-Za-z0-9_-]+)", url)
    if m:
        url = f"https://docs.google.com/document/d/{m.group(1)}/export?format=txt"

    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.content


def fetch_reddit(url: str) -> str:
    """Fetch a Reddit thread via its public .json endpoint and flatten the post
    plus comment bodies into plain text. Reddit blocks plain HTML scraping, but
    the JSON API responds to a descriptive User-Agent."""
    json_url = url.rstrip("/") + ".json"
    resp = requests.get(
        json_url,
        headers={**HEADERS, "User-Agent": "brown-clubs-guide/1.0 (course project)"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    parts: list[str] = []

    def walk(node):
        """Recursively pull selftext/body fields out of the comment tree."""
        if isinstance(node, list):
            for item in node:
                walk(item)
            return
        if not isinstance(node, dict):
            return
        kind = node.get("kind")
        d = node.get("data", {})
        if kind == "t3":  # the post itself
            if d.get("title"):
                parts.append(d["title"])
            if d.get("selftext"):
                parts.append(d["selftext"])
        elif kind == "t1" and d.get("body"):  # a comment
            parts.append(d["body"])
        if isinstance(d, dict):
            walk(d.get("children"))
            walk(d.get("replies"))

    walk(data)
    return clean_text("\n\n".join(parts))


# Elements whose class / id / role / aria-label match this are page "chrome"
# (menus, cookie banners, ads, share bars, comment widgets, related-content
# rails, etc.) rather than article content, so we drop them before extraction.
_BOILERPLATE_ATTR = re.compile(
    r"nav|menu|footer|header|masthead|topbar|toolbar|"
    r"cookie|consent|gdpr|privacy|"
    r"banner|advert|\bads?\b|sponsor|promo|"
    r"share|social|follow|subscribe|newsletter|signup|sign-up|"
    r"breadcrumb|sidebar|widget|related|recirc|recommend|popular|trending|"
    r"comment|disqus|reply|"
    r"modal|popup|overlay|paywall|skip|sr-only|screen-reader|visually-hidden|"
    r"site-header|site-footer|global-",
    re.IGNORECASE,
)

# Whole lines (after trimming) that are pure page furniture. Matched
# case-insensitively against the entire line, so sentences that merely contain
# one of these words are kept.
_JUNK_LINE = re.compile(
    r"""^(?:
        skip\ to.* | content | navigation | footer | header |
        about | join(\ us)? | contact(\ us)? | advertise(ment)? | sponsored |
        subscribe.* | donate | newsletter.* | sign\ ?(up|in).* | log\ ?in.* |
        register.* | follow(\ us)?.* | meet\ the\ team |
        opinions? | more(\ from.*)? | popular | trending | latest | recommended |
        related\ (articles|posts|stories).* | you\ might\ also\ like.* |
        powered\ by.* | solutions\ by.* |
        menu | home | search | close | back\ to\ top | next | previous | prev |
        read\ more.* | show\ more.* | load\ more.* | see\ more.* |
        continue\ reading.* |
        share(\ this)?(\ (article|story|post))? | tweet | facebook | linkedin |
        whatsapp | pinterest | instagram | youtube | copy\ link | print | email |
        \d+\ ?comments? | (leave|add|post)\ a\ comment.* | view\ (all\ )?comments?.* |
        we\ use\ cookies.* | accept(\ all)?(\ cookies)? | cookie.* |
        by\ continuing.* | manage\ (cookies|preferences).* | privacy\ policy.* |
        terms\ of\ (use|service).* |
        all\ content\ ©.* | ©.* | copyright.* | all\ rights\ reserved.* |
        photo\ by.* | image:.* | getty\ images.* | unsplash.* |
        loading\W* | by | \|
    )$""",
    re.IGNORECASE | re.VERBOSE,
)


def _is_boilerplate_node(tag) -> bool:
    """True if a tag's class/id/role/aria attributes mark it as page chrome.

    Guards against false positives: an element is only treated as chrome if it
    holds little text. The main content is sometimes inside a wrapper whose
    class coincidentally matches (e.g. a 'header'/'promo'/'recommend' wrapper),
    and real chrome (nav bars, share buttons, cookie notices) is always short.
    """
    ident = " ".join(filter(None, [
        " ".join(tag.get("class", []) or []),
        tag.get("id") or "",
        tag.get("role") or "",
        tag.get("aria-label") or "",
    ]))
    if not (ident and _BOILERPLATE_ATTR.search(ident)):
        return False
    return len(tag.get_text(strip=True)) <= 300


def strip_boilerplate_lines(text: str) -> str:
    """Drop whole lines that are navigation/share/cookie/footer furniture.

    Removes lines matching the curated junk patterns above, plus lines that
    contain no letters or digits (stray punctuation like '.', ',', '|', '>').
    Content lines — full sentences and list items like club names — are kept.
    """
    kept: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if _JUNK_LINE.match(s):
            continue
        if not re.search(r"[A-Za-z0-9]", s):
            continue
        kept.append(line)
    return "\n".join(kept)


def html_to_text(html) -> str:
    """Convert an HTML page into clean plain text.

    Removes scripts/styles, structural boilerplate (nav/header/footer/aside),
    and any element flagged as page chrome by its attributes; extracts the main
    content; then strips residual junk lines and normalizes whitespace.
    """
    soup = BeautifulSoup(html, "html.parser")

    # 1. Remove non-content elements outright.
    for tag in soup(["script", "style", "noscript", "nav", "header",
                     "footer", "aside", "form", "button", "svg", "iframe",
                     "figure", "figcaption"]):
        tag.decompose()

    # 2. Remove elements whose attributes mark them as chrome (cookie banners,
    #    share bars, ad slots, comment widgets, related-content rails, ...).
    for tag in soup.find_all(_is_boilerplate_node):
        if not tag.decomposed:
            tag.decompose()

    # 3. Build several candidate extractions and keep the longest. News sites
    #    often wrap a short teaser in <article>, so we also try the
    #    concatenated <p> text and the full <body> as fallbacks.
    candidates: list[str] = []
    for container in (soup.find("article"), soup.find("main"), soup.body):
        if container is not None:
            candidates.append(container.get_text(separator="\n"))
    paragraphs = "\n".join(p.get_text(separator=" ") for p in soup.find_all("p"))
    if paragraphs:
        candidates.append(paragraphs)

    best = max((clean_text(c) for c in candidates), key=len, default="")

    # 4. Strip residual junk lines that survived element removal.
    return strip_boilerplate_lines(best)


def clean_text(text: str) -> str:
    """Normalize whitespace: trim lines, drop blanks, collapse runs of spaces."""
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    # Collapse 3+ consecutive identical lines (menu/footer repetition) to one.
    cleaned: list[str] = []
    for line in lines:
        if len(cleaned) >= 2 and cleaned[-1] == line and cleaned[-2] == line:
            continue
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def load_documents(fetch: bool = True, refetch: bool = False) -> list[dict]:
    """Fetch + clean every source, caching plain text to documents/<slug>.txt.

    Fetching is incremental: a source is only downloaded when it has no usable
    cached .txt yet. Existing files (including ones you've hand-cleaned) are
    left untouched, so re-running the script never clobbers your edits. Pass
    refetch=True to force a fresh download of every web source.

    Returns a list of {slug, name, url, path, text} dicts for sources that
    yielded usable text. Sources that fail (blocked, image-only, etc.) are
    reported and skipped so the rest of the pipeline can still run.
    """
    DOCS_DIR.mkdir(exist_ok=True)
    documents: list[dict] = []
    failures: list[tuple[str, str]] = []

    for src in SOURCES:
        txt_path = DOCS_DIR / f"{src.slug}.txt"
        cached = txt_path.read_text(encoding="utf-8") if txt_path.exists() else ""
        has_cache = bool(cached.strip())

        # Decide whether to hit the network for this source:
        #   - manual sources are never fetched (curated by hand);
        #   - with --no-fetch (fetch=False) nothing is fetched;
        #   - otherwise fetch only if there's no usable cache yet, unless
        #     --refetch was passed to force a fresh download.
        do_fetch = fetch and not src.manual and (refetch or not has_cache)

        if do_fetch:
            try:
                print(f"  fetching  {src.name} ...", flush=True)
                if "reddit.com" in src.url:
                    text = fetch_reddit(src.url)
                else:
                    raw = fetch_url(src.url)
                    if "docs.google.com" in src.url:
                        # Google Docs export is already plain UTF-8 text.
                        text = clean_text(raw.decode("utf-8", errors="replace"))
                    else:
                        text = html_to_text(raw)
                if len(text) < 200:
                    raise ValueError(
                        f"only {len(text)} chars extracted (likely blocked "
                        "or image-only)"
                    )
                txt_path.write_text(text, encoding="utf-8")
                time.sleep(1)  # be polite between requests
            except Exception as exc:  # noqa: BLE001 — report and continue
                failures.append((src.name, str(exc)))
                if not has_cache:
                    continue
                text = cached  # fall back to the previously cached copy
        elif has_cache:
            label = "cached" if not src.manual else "manual"
            print(f"  {label:<8}  {src.name}", flush=True)
            text = cached
        else:
            failures.append((
                src.name,
                "missing — add it by hand" if src.manual
                else "no cached .txt (remove --no-fetch to download)",
            ))
            continue

        preview = text[:200].replace("\n", " ")
        print(f"  loaded    {src.name}: {len(text):>6} chars | {preview!r}")
        documents.append({
            "slug": src.slug,
            "name": src.name,
            "url": src.url,
            "path": str(txt_path),
            "text": text,
            "manual": src.manual,
        })

    if failures:
        print("\n  [!] sources that could not be auto-ingested:")
        for name, why in failures:
            print(f"      - {name}: {why}")
        print("    (download these manually into documents/<slug>.txt, then "
              "re-run with --no-fetch)")

    return documents


def drop_cross_page_boilerplate(documents: list[dict]) -> set[str]:
    """Remove short lines that recur across multiple pages of the *same* site.

    This catches the "appears on every page" boilerplate that survives per-page
    cleaning — newsletter prompts, footer nav, social rails repeated on every
    Brown Daily Herald article, etc. Deduping is scoped to a single domain so
    that genuine content which legitimately appears across *different* sources
    (e.g. a club name listed on several sites) is never removed.

    Manual sources are left untouched. Mutates each affected doc's "text" in
    place and returns the set of slugs that changed.
    """
    by_domain: dict[str, list[dict]] = defaultdict(list)
    for doc in documents:
        if doc.get("manual"):
            continue
        by_domain[urlparse(doc["url"]).netloc].append(doc)

    changed: set[str] = set()
    for docs in by_domain.values():
        if len(docs) < 2:
            continue  # nothing to compare against on a single-page site

        # Count how many of this site's pages each distinct line appears on.
        page_counts: dict[str, int] = defaultdict(int)
        for doc in docs:
            for line in {ln.strip() for ln in doc["text"].splitlines() if ln.strip()}:
                page_counts[line] += 1

        # Furniture = short lines present on 2+ pages. The length cap protects
        # any long sentence that might coincidentally repeat.
        boilerplate = {ln for ln, n in page_counts.items()
                       if n >= 2 and len(ln) <= 120}
        if not boilerplate:
            continue

        for doc in docs:
            kept = [ln for ln in doc["text"].splitlines()
                    if ln.strip() not in boilerplate]
            new_text = "\n".join(kept).strip()
            if new_text != doc["text"]:
                doc["text"] = new_text
                changed.add(doc["slug"])
    return changed


# --------------------------------------------------------------------------- #
# Stage 2: Chunking (recursive character splitter)
# --------------------------------------------------------------------------- #

def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
    separators: list[str] | None = None,
) -> list[str]:
    """Split text into <= chunk_size pieces, recursively, with overlap.

    Recursive strategy (per planning.md): try to split on the coarsest
    separator first (paragraph breaks), and only fall back to finer separators
    (lines, sentences, words, characters) for spans that are still too big.
    This keeps related sentences together when possible. Adjacent chunks share
    `overlap` characters so context isn't lost at boundaries.
    """
    if separators is None:
        separators = SEPARATORS

    pieces = _recursive_split(text.strip(), chunk_size, separators)
    return _merge_with_overlap(pieces, chunk_size, overlap)


def _recursive_split(text: str, chunk_size: int, separators: list[str]) -> list[str]:
    """Break text into atomic segments no larger than chunk_size."""
    if len(text) <= chunk_size:
        return [text] if text else []

    sep = separators[0] if separators else ""
    rest = separators[1:] if len(separators) > 1 else [""]

    # Base case: no separator left — hard-split on character count.
    if sep == "":
        return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

    segments: list[str] = []
    for part in text.split(sep):
        if not part:
            continue
        part = part + sep if sep not in ("",) else part
        if len(part) <= chunk_size:
            segments.append(part)
        else:
            segments.extend(_recursive_split(part, chunk_size, rest))
    return segments


def _merge_with_overlap(segments: list[str], chunk_size: int, overlap: int) -> list[str]:
    """Greedily pack atomic segments into chunks, carrying an overlap tail."""
    chunks: list[str] = []
    current = ""

    for seg in segments:
        if not current:
            current = seg
        elif len(current) + len(seg) <= chunk_size:
            current += seg
        else:
            chunks.append(current.strip())
            tail = current[-overlap:] if overlap and len(current) > overlap else ""
            current = tail + seg

    if current.strip():
        chunks.append(current.strip())
    return [c for c in chunks if c]


# Matches a whole line that is just an email address.
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def chunk_activities_list(text: str) -> list[str]:
    """One chunk per club for the Student Activities directory.

    The directory is a flat alphabetical list of "club name" / "email" line
    pairs. Packed into multi-club blobs (as the generic recursive chunker
    does), a specific club name gets diluted among ~30 unrelated names and
    embeds far from a name query — so a lookup like "Alexander Hamilton
    Society" fails to retrieve. Splitting one entry per club, with its email,
    makes each chunk a tight, specific target for retrieval.

    Each email line is paired with the immediately preceding non-empty line
    (the club name); header lines without a following email are skipped.
    """
    chunks: list[str] = []
    name: str | None = None
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if _EMAIL_RE.fullmatch(s):
            if name:
                chunks.append(f"{name} — {s}")
            name = None
        else:
            name = s
    return chunks


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main() -> int:
    # Windows consoles default to cp1252 and choke on curly quotes / accents
    # in previews. Force UTF-8 so output matches the (correct) saved files.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    parser = argparse.ArgumentParser(description="Ingest and chunk documents.")
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="never download; chunk the .txt files already in documents/",
    )
    parser.add_argument(
        "--refetch",
        action="store_true",
        help="force a fresh download of every web source, overwriting cached "
             ".txt files (your hand-cleaned edits will be lost)",
    )
    args = parser.parse_args()

    print("Stage 1: loading documents")
    documents = load_documents(fetch=not args.no_fetch, refetch=args.refetch)
    if not documents:
        print("\nNo documents loaded — nothing to chunk.", file=sys.stderr)
        return 1

    # Remove site-wide boilerplate that recurs across pages of the same domain,
    # then persist the cleaned text so documents/<slug>.txt matches chunks.json.
    changed = drop_cross_page_boilerplate(documents)
    for doc in documents:
        if doc["slug"] in changed:
            Path(doc["path"]).write_text(doc["text"], encoding="utf-8")
    if changed:
        print(f"  stripped cross-page boilerplate from {len(changed)} file(s)")

    print(f"\nStage 2: chunking (size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")
    all_chunks: list[dict] = []
    for doc in documents:
        # The Student Activities directory is chunked one club per chunk; every
        # other source uses the generic recursive chunker.
        if doc["slug"] == "student-activities-list":
            chunks = chunk_activities_list(doc["text"])
        else:
            chunks = chunk_text(doc["text"])
        for i, chunk in enumerate(chunks):
            all_chunks.append({
                "id": f"{doc['slug']}-{i}",
                "source": doc["name"],
                "url": doc["url"],
                "chunk_index": i,
                "text": chunk,
            })
        print(f"  {doc['name']:<34} -> {len(chunks):>3} chunks")

    CHUNKS_FILE.write_text(
        json.dumps(all_chunks, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    sizes = [len(c["text"]) for c in all_chunks]
    print(f"\nDone. {len(all_chunks)} chunks from {len(documents)} documents "
          f"-> {CHUNKS_FILE}")
    if sizes:
        print(f"chunk size: min={min(sizes)}  avg={sum(sizes)//len(sizes)}  "
              f"max={max(sizes)}")
        sample = all_chunks[len(all_chunks) // 2]
        print(f"\nsample chunk [{sample['id']}]:\n{sample['text']!r}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
