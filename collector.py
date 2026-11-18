#!/usr/bin/env python3
"""Phase-1 official update collector: standard-library only, auditable by design."""
from __future__ import annotations

import argparse, csv, hashlib, json, re, sys
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent
UTC = timezone.utc
USER_AGENT = "official-update-pilot/0.1 (+https://github.com/)"

class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.links = []; self._href = None; self._text = []
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href = dict(attrs).get("href"); self._text = []
    def handle_data(self, data):
        if self._href is not None: self._text.append(data)
    def handle_endtag(self, tag):
        if tag == "a" and self._href:
            text = " ".join(" ".join(self._text).split())
            if text: self.links.append((self._href, text))
            self._href = None; self._text = []

def now_iso(): return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
def clean(text): return " ".join(unescape(text or "").split())
def item_id(source_id, url, title): return hashlib.sha256(f"{source_id}|{url}|{title}".encode()).hexdigest()

def fetch(url, timeout=30):
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/atom+xml, text/xml, text/html;q=0.9, */*;q=0.1"})
    with urlopen(request, timeout=timeout) as response:
        raw = response.read()
        return response.geturl(), response.status, response.headers.get_content_type(), raw.decode(response.headers.get_content_charset() or "utf-8", errors="replace")

def parse_date(value):
    if not value: return None
    value = clean(value)
    try: return parsedate_to_datetime(value).astimezone(UTC).isoformat().replace("+00:00", "Z")
    except (TypeError, ValueError): pass
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d", "%B %d, %Y", "%d %B %Y"):
        try: return datetime.strptime(value, fmt).replace(tzinfo=UTC).isoformat().replace("+00:00", "Z")
        except ValueError: continue
    return None

def child_text(node, names):
    for child in list(node):
        if child.tag.split("}")[-1] in names and child.text: return clean(child.text)
    return ""

def parse_feed(source, body):
    root = ET.fromstring(body)
    nodes = [n for n in root.iter() if n.tag.split("}")[-1] in ("item", "entry")]
    results = []
    for n in nodes:
        title = child_text(n, {"title"})
        link = child_text(n, {"link"})
        if not link:
            for c in list(n):
                if c.tag.split("}")[-1] == "link" and c.attrib.get("href"):
                    link = c.attrib["href"]; break
        date = child_text(n, {"pubDate", "published", "updated", "date"})
        if title and link: results.append({"title": title, "url": link, "published_at": parse_date(date), "updated_at": parse_date(date), "date_raw": date})
    return results

def parse_jsonld_page_metadata(source, body, final_url):
    """Return only the source page's own declared metadata, never its nav links."""
    blocks = re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', body, re.I | re.S)
    items = []
    for block in blocks:
        try: values = json.loads(block)
        except json.JSONDecodeError: continue
        if isinstance(values, dict): values = values.get("@graph", [values])
        if not isinstance(values, list): continue
        for value in values:
            if not isinstance(value, dict): continue
            title = clean(value.get("headline") or value.get("name"))
            if title:
                date = value.get("dateModified") or value.get("datePublished")
                items.append({"title": title, "url": value.get("url") or final_url,
                              "published_at": parse_date(value.get("datePublished")),
                              "updated_at": parse_date(value.get("dateModified")),
                              "date_raw": date, "_quality": "page_metadata"})
    return items[:1]

def parse_dotdigital_release_notes(source, body, final_url):
    """Dotdigital exposes dated release-note titles on its official help page."""
    parser = LinkParser(); parser.feed(body)
    date_pattern = re.compile(r"\b(?:\d{1,2}\s+)?(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+20\d{2}\b", re.I)
    results = []
    for href, title in parser.links:
        match = date_pattern.search(title)
        if not match or "release note" not in title.lower(): continue
        date_raw = match.group(0)
        results.append({"title": title, "url": urljoin(final_url, href), "published_at": parse_date(date_raw),
                        "updated_at": None, "date_raw": date_raw, "_quality": "dated_update"})
    return results[:50]

def parse_html(source, body, final_url):
    # These handlers intentionally do less than a generic page scraper.  A source
    # whose public HTML is client-rendered is audited as accessible but unparsed.
    if source["id"] == "dotdigital_personalization":
        return parse_dotdigital_release_notes(source, body, final_url)
    if source["id"] == "adobe_experience_cloud":
        return parse_jsonld_page_metadata(source, body, final_url)
    return []

def load_json(path, fallback):
    if not path.exists(): return fallback
    return json.loads(path.read_text(encoding="utf-8"))

def write_json(path, data): path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def append_csv(path, rows, fields):
    exists = path.exists()
    with path.open("a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        if not exists: writer.writeheader()
        writer.writerows(rows)

def valid_domain(url, expected):
    host = (urlparse(url).hostname or "").lower()
    return host == expected or host.endswith("." + expected)

def run(config_path, data_dir, dry_run):
    discovered_at = now_iso(); config = load_json(config_path, {})
    sources = config.get("sources", [])
    if not sources: raise RuntimeError("sources.json contains no sources")
    if dry_run:
        for s in sources:
            if not valid_domain(s["url"], s["official_domain"]): raise RuntimeError(f"invalid official_domain for {s['id']}")
            if s["kind"] not in {"rss", "html"}: raise RuntimeError(f"unsupported kind for {s['id']}")
        print(f"Config valid: {len(sources)} sources. No network request made."); return 0
    data_dir.mkdir(parents=True, exist_ok=True)
    history_file = data_dir / "history.json"; audit_json = data_dir / "audit.json"; audit_csv = data_dir / "audit.csv"
    history = load_json(history_file, {"items": {}}); history_items = history.setdefault("items", {})
    audit, new_items = [], []
    for source in sources:
        record = {"run_at": discovered_at, "source_id": source["id"], "vendor": source["vendor"], "source_url": source["url"], "kind": source["kind"], "status": "failed", "http_status": None, "final_url": None, "content_type": None, "items_parsed": 0, "new_items": 0, "error": None}
        try:
            final_url, status, content_type, body = fetch(source["url"])
            record.update(http_status=status, final_url=final_url, content_type=content_type)
            parsed = parse_feed(source, body) if source["kind"] == "rss" else parse_html(source, body, final_url)
            record["items_parsed"] = len(parsed)
            # A generic HTML link scan only yields candidates.  It is deliberately
            # not reported as a successful dated release-note extraction.
            if source["kind"] == "html":
                qualities = {item.get("_quality") for item in parsed}
                if "dated_update" in qualities:
                    record["status"] = "ok"
                elif "page_metadata" in qualities:
                    record["status"] = "accessible_metadata"
                else:
                    record["status"] = "accessible_no_items"
            else:
                record["status"] = "ok" if parsed else "ok_empty"
            for item in parsed:
                key = item_id(source["id"], item["url"], item["title"])
                if key not in history_items:
                    entry = {"item_id": key, "source_id": source["id"], "vendor": source["vendor"], "title": item["title"], "url": item["url"], "published_at": item["published_at"], "updated_at": item["updated_at"], "date_raw": item["date_raw"], "first_discovered_at": discovered_at}
                    history_items[key] = entry; new_items.append(entry); record["new_items"] += 1
        except (HTTPError, URLError, TimeoutError, ET.ParseError, ValueError) as exc:
            record["error"] = f"{type(exc).__name__}: {exc}"
        except Exception as exc:  # preserve unexpected failures in audit rather than hiding them
            record["error"] = f"unexpected {type(exc).__name__}: {exc}"
        audit.append(record)
    history["last_run_at"] = discovered_at; write_json(history_file, history)
    write_json(audit_json, {"run_at": discovered_at, "sources": audit, "new_items": new_items})
    append_csv(audit_csv, audit, ["run_at", "source_id", "vendor", "source_url", "kind", "status", "http_status", "final_url", "content_type", "items_parsed", "new_items", "error"])
    print(json.dumps({"run_at": discovered_at, "sources": len(audit), "verified_sources": sum(x["status"] == "ok" for x in audit), "metadata_only": sum(x["status"] == "accessible_metadata" for x in audit), "new_items": len(new_items)}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("--config", type=Path, default=ROOT / "sources.json"); p.add_argument("--data-dir", type=Path, default=ROOT / "data"); p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(); sys.exit(run(args.config, args.data_dir, args.dry_run))
