#!/usr/bin/env python3
"""
Scientific American Latest Issue Scraper
- Primary article data source: window.__DATA__ JSON (has correct URLs + rich metadata)
- Fallback: JSON-LD hasPart for any articles not found in __DATA__
"""

import os
import re
import json
import logging
from datetime import datetime
from urllib.parse import urljoin

import requests

# Configuration
FLARESOLVERR_URL = os.getenv('FLARESOLVERR_URL', 'http://localhost:8191/v1')
PAGE_URL = "https://www.scientificamerican.com/latest-issue/"
BASE_URL = "https://www.scientificamerican.com"
RSS_OUTPUT_FILE = "feed.xml"

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def fetch_with_flaresolverr(url):
    """Fetch a URL using FlareSolverr to bypass Cloudflare protection."""
    logger.info(f"Fetching URL via FlareSolverr: {url}")
    payload = {"cmd": "request.get", "url": url, "maxTimeout": 60000}

    try:
        resp = requests.post(FLARESOLVERR_URL, json=payload, timeout=70)
        resp.raise_for_status()
        data = resp.json()
        if data.get('status') == 'ok':
            logger.info("Successfully fetched page via FlareSolverr")
            return data['solution']['response']
        logger.error(f"FlareSolverr returned status != ok: {data.get('message')}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        return None
    except ValueError as e:
        logger.error(f"Invalid JSON from FlareSolverr: {e}")
        return None


def extract_window_data(html_content):
    """
    Extract and parse window.__DATA__ from the page HTML.
    This contains full article info including correct URLs, authors, images, etc.
    Returns the parsed dict or None.
    """
    match = re.search(
        r'window\.__DATA__\s*=\s*JSON\.parse\(`(.*?)`\)\s*;',
        html_content,
        flags=re.S
    )
    if not match:
        # also try without JSON.parse wrapper (plain assignment)
        match = re.search(
            r'window\.__DATA__\s*=\s*(\{.*?\})\s*;',
            html_content,
            flags=re.S
        )
    if not match:
        logger.warning("window.__DATA__ not found in HTML")
        return None

    raw = match.group(1)
    # The value is a JSON-encoded string inside backticks (already escaped for JS)
    # We need to unescape JS escape sequences (\n, \t, \\, \", etc.)
    try:
        # ast.literal_eval won't help here; use json.loads with proper quoting
        # The backtick-delimited string uses \` for literal backticks; handle that
        raw = raw.replace('\\`', '`')
        data = json.loads(raw)
        logger.info("Successfully parsed window.__DATA__")
        return data
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse window.__DATA__: {e}")
        return None


def normalize_articles_from_window_data(window_data):
    """
    Flatten articles from window.__DATA__ issueData.article_previews
    (advances + departments + features) into a unified list of dicts
    with a consistent schema matching what create_rss_feed expects.
    """
    try:
        previews = window_data['initialData']['issueData']['article_previews']
    except (KeyError, TypeError) as e:
        logger.error(f"Could not find article_previews in window.__DATA__: {e}")
        return []

    articles = []
    for section in ('advances', 'departments', 'features'):
        for a in previews.get(section, []):
            # Build a normalized dict
            authors = a.get('authors', [])
            author_names = [au.get('name', '') for au in authors if au.get('name')]

            raw_url = a.get('url', '')
            full_url = urljoin(BASE_URL, raw_url) if raw_url else ''

            articles.append({
                'headline': a.get('title') or a.get('display_title') or '',
                'about': _strip_html(a.get('summary', '')),
                'datePublished': a.get('date_published') or a.get('release_date') or '',
                'url': full_url,
                'image': a.get('image_url', ''),
                'author': [{'name': n} for n in author_names],
                '_column': a.get('column', ''),
                '_category': a.get('category', ''),
            })

    logger.info(f"Extracted {len(articles)} articles from window.__DATA__")
    return articles


def _strip_html(text):
    """Remove HTML tags from a string."""
    if not text:
        return ''
    return re.sub(r'<[^>]+>', '', text).strip()


def extract_articles_from_jsonld(html_content):
    """
    Fallback: extract articles from JSON-LD hasPart.
    Only used when window.__DATA__ is unavailable.
    Note: JSON-LD hasPart items do NOT have article URLs — only image URLs —
    so URLs will be empty when this fallback is used.
    """
    logger.info("Falling back to JSON-LD extraction")
    scripts = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html_content,
        flags=re.S | re.I
    )
    for json_text in scripts:
        json_text = json_text.strip()
        if not json_text:
            continue
        try:
            data = json.loads(json_text)
        except json.JSONDecodeError:
            cleaned = re.sub(r',\s*}', '}', json_text)
            cleaned = re.sub(r',\s*]', ']', cleaned)
            try:
                data = json.loads(cleaned)
            except Exception:
                continue

        # Search for PublicationIssue in various structures
        candidates = []
        if isinstance(data, dict):
            for item in data.get('@graph', [data]):
                if isinstance(item, dict) and item.get('@type') == 'PublicationIssue':
                    candidates = item.get('hasPart', [])
                    break
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get('@type') == 'PublicationIssue':
                    candidates = item.get('hasPart', [])
                    break

        if candidates:
            logger.info(f"Found {len(candidates)} articles in JSON-LD (URLs will be empty)")
            return candidates

    return []


def extract_articles_from_html(html_content):
    """
    Primary extraction pipeline:
    1. Try window.__DATA__ (has correct URLs + rich metadata)
    2. Fall back to JSON-LD hasPart
    """
    window_data = extract_window_data(html_content)
    if window_data:
        articles = normalize_articles_from_window_data(window_data)
        if articles:
            return articles

    logger.warning("window.__DATA__ extraction failed or empty; trying JSON-LD fallback")
    return extract_articles_from_jsonld(html_content)


# ── RSS helpers ────────────────────────────────────────────────────────────────

def escape_xml(text):
    if not text:
        return ''
    text = str(text)
    return (text.replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&apos;'))


def parse_pubdate_iso_to_rfc822(pub_date_iso):
    if not pub_date_iso:
        return ''
    try:
        if pub_date_iso.endswith('Z'):
            dt = datetime.fromisoformat(pub_date_iso.replace('Z', '+00:00'))
        elif re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$', pub_date_iso):
            dt = datetime.fromisoformat(pub_date_iso + '+00:00')
        else:
            dt = datetime.fromisoformat(pub_date_iso)
        return dt.strftime('%a, %d %b %Y %H:%M:%S %z')
    except Exception as e:
        logger.debug(f"Could not parse date '{pub_date_iso}': {e}")
        return ''


def normalize_author_field(author_field):
    if not author_field:
        return ''
    if isinstance(author_field, str):
        return author_field
    if isinstance(author_field, dict):
        return author_field.get('name', '')
    if isinstance(author_field, list):
        for a in author_field:
            if isinstance(a, str):
                return a
            if isinstance(a, dict) and a.get('name'):
                return a['name']
    return ''


def extract_description(article):
    about = article.get('about')
    if isinstance(about, str):
        return about
    if isinstance(about, dict):
        return about.get('description') or about.get('name') or ''
    desc = article.get('description') or article.get('dek') or ''
    if isinstance(desc, str):
        return desc
    if isinstance(desc, dict):
        return desc.get('description') or desc.get('name') or ''
    if isinstance(desc, list):
        return ' '.join(str(x) for x in desc if isinstance(x, str))[:500]
    return ''


def extract_image_url(image_field):
    if not image_field:
        return ''
    if isinstance(image_field, str):
        # Reject strings that are clearly not image URLs
        # (JSON-LD hasPart 'image' is just a plain URL string — that's fine)
        return image_field
    if isinstance(image_field, dict):
        return image_field.get('url') or image_field.get('@id') or ''
    if isinstance(image_field, list) and image_field:
        first = image_field[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            return first.get('url') or first.get('@id') or ''
    return ''


def create_rss_feed(articles):
    logger.info("Creating RSS feed")
    build_date = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")

    rss_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0"'
        ' xmlns:atom="http://www.w3.org/2005/Atom"'
        ' xmlns:dc="http://purl.org/dc/elements/1.1/"'
        ' xmlns:media="http://search.yahoo.com/mrss/">',
        '  <channel>',
        f'    <title>{escape_xml("Scientific American - Latest Issue")}</title>',
        f'    <link>{escape_xml(PAGE_URL)}</link>',
        f'    <description>{escape_xml("Latest articles from Scientific American magazine")}</description>',
        '    <language>en-us</language>',
        f'    <lastBuildDate>{build_date}</lastBuildDate>',
        '    <atom:link href="https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/feed.xml"'
        ' rel="self" type="application/rss+xml"/>',
        '',
    ]

    item_count = 0
    for article in articles:
        if not isinstance(article, dict):
            continue

        item_count += 1

        title = article.get('headline') or article.get('name') or 'Untitled Article'
        title = _strip_html(title)

        article_url = article.get('url') or ''
        if article_url and not article_url.startswith('http'):
            article_url = urljoin(BASE_URL, article_url)

        description = extract_description(article)
        pub_date_iso = article.get('datePublished') or article.get('dateCreated') or ''
        rfc822_date = parse_pubdate_iso_to_rfc822(pub_date_iso)

        image_raw = extract_image_url(article.get('image', ''))
        image_url = urljoin(BASE_URL, image_raw) if image_raw else ''

        author_name = normalize_author_field(article.get('author'))

        guid_value = article_url or title
        is_permalink = 'true' if article_url.startswith('http') else 'false'

        rss_lines.append('    <item>')
        rss_lines.append(f'      <title>{escape_xml(title)}</title>')
        if article_url:
            rss_lines.append(f'      <link>{escape_xml(article_url)}</link>')
        if description:
            rss_lines.append(f'      <description>{escape_xml(description)}</description>')
        if rfc822_date:
            rss_lines.append(f'      <pubDate>{escape_xml(rfc822_date)}</pubDate>')
        if author_name:
            rss_lines.append(f'      <dc:creator>{escape_xml(author_name)}</dc:creator>')
            rss_lines.append(f'      <author>{escape_xml(author_name)}</author>')
        rss_lines.append(f'      <guid isPermaLink="{is_permalink}">{escape_xml(guid_value)}</guid>')

        if image_url:
            rss_lines.append(f'      <media:thumbnail url="{escape_xml(image_url)}"/>')
            rss_lines.append(f'      <media:content url="{escape_xml(image_url)}" medium="image"/>')
            rss_lines.append(f'      <enclosure url="{escape_xml(image_url)}" type="image/jpeg"/>')

        rss_lines.append('    </item>')
        rss_lines.append('')

    rss_lines += ['  </channel>', '</rss>']

    logger.info(f"Created RSS feed with {item_count} items")
    return '\n'.join(rss_lines)


def main():
    logger.info("Starting Scientific American scraper")

    html_content = fetch_with_flaresolverr(PAGE_URL)
    if not html_content:
        logger.error("Failed to fetch page content")
        return False

    articles = extract_articles_from_html(html_content)
    if not articles:
        logger.error("No articles found")
        return False

    rss_content = create_rss_feed(articles)

    try:
        with open(RSS_OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write(rss_content)
        logger.info(f"RSS feed written to {RSS_OUTPUT_FILE}")
        return True
    except Exception as e:
        logger.error(f"Failed to write RSS feed: {e}")
        return False


if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)
