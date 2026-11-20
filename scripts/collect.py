#!/usr/bin/env python3
"""Small source-monitoring pilot. HTML checks are explicitly NOT article extraction."""
import csv
import hashlib
import json
import os
import pathlib
import sys
from datetime import datetime, timezone
from urllib.parse import urljoin
import requests
import feedparser
from bs4 import BeautifulSoup

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
DATA.mkdir(exist_ok=True)
NOW = datetime.now(timezone.utc).isoformat(timespec='seconds')
HEADERS = {'User-Agent': 'OfficialUpdatesMonitor/0.1 (public news monitoring; GitHub Actions)'}
TIMEOUT = 20


def write_csv(path, rows, columns):
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        w.writerows(rows)


def run():
    sources = json.loads((ROOT / 'config' / 'sources.json').read_text(encoding='utf-8'))
    seen_path = DATA / 'seen.json'
    try:
        seen = json.loads(seen_path.read_text(encoding='utf-8')) if seen_path.exists() else {}
    except (json.JSONDecodeError, OSError):
        seen = {}
    audit, new_items = [], []
    for source in sources:
        record = {'checked_at_utc': NOW, 'source_id': source['id'], 'source': source['name'], 'source_url': source['url'], 'method': source['kind'], 'status': '', 'http_status': '', 'items_found': 0, 'new_items': 0, 'error': ''}
        try:
            resp = requests.get(source['url'], headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
            record['http_status'] = resp.status_code
            resp.raise_for_status()
            if source['kind'] == 'rss':
                parsed = feedparser.parse(resp.content)
                if not parsed.entries:
                    raise ValueError('RSS has no entries; verify feed URL or access restrictions')
                record['items_found'] = len(parsed.entries)
                for entry in parsed.entries:
                    link = entry.get('link')
                    title = entry.get('title', '').strip()
                    published = entry.get('published', '')
                    updated = entry.get('updated', '')
                    if not link or not title:
                        continue
                    key = hashlib.sha256((source['id'] + '|' + link).encode()).hexdigest()
                    if key not in seen:
                        seen[key] = NOW
                        new_items.append({'source_id': source['id'], 'title': title, 'url': link, 'published_raw': published, 'updated_raw': updated, 'first_seen_utc': NOW, 'date_verified': bool(published or updated)})
                        record['new_items'] += 1
                record['status'] = 'feed_parsed'
            else:
                soup = BeautifulSoup(resp.text, 'html.parser')
                title = soup.title.get_text(' ', strip=True) if soup.title else ''
                if len(title) < 4:
                    raise ValueError('No readable HTML title; possibly JS-only or blocked')
                # HTML mode checks availability ONLY. It does not claim to have inspected releases.
                record['status'] = 'html_reachable_not_verified'
                record['error'] = 'HTML reachable; release entries and publication dates NOT verified'
        except Exception as e:
            record['status'] = 'failed'
            record['error'] = f'{type(e).__name__}: {str(e)[:350]}'
        audit.append(record)
        print(f"{source['id']}: {record['status']} ({record['http_status']}) {record['error']}")
    write_csv(DATA / 'latest_audit.csv', audit, ['checked_at_utc','source_id','source','source_url','method','status','http_status','items_found','new_items','error'])
    write_csv(DATA / 'latest_new_items.csv', new_items, ['source_id','title','url','published_raw','updated_raw','first_seen_utc','date_verified'])
    seen_path.write_text(json.dumps(seen, ensure_ascii=False, indent=2), encoding='utf-8')
    summary = {'checked_at_utc': NOW, 'planned_sources': len(audit), 'rss_parsed': sum(a['status']=='feed_parsed' for a in audit), 'html_reachable_not_verified': sum(a['status']=='html_reachable_not_verified' for a in audit), 'failed': sum(a['status']=='failed' for a in audit), 'new_items': len(new_items), 'note': 'HTML reachable is NOT successful release-date verification; this is a pilot, not 27-platform coverage.'}
    (DATA / 'latest_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False))
    return 0

if __name__ == '__main__':
    sys.exit(run())
