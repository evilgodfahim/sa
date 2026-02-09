#!/usr/bin/env python3
"""
Scientific American Latest Issue Scraper — updated
- robust JSON-LD extraction
- convert relative article/image URLs to absolute
- tolerant handling of image, author, and description formats
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
    """
    Fetch a URL using FlareSolverr to bypass Cloudflare protection.
    Returns HTML string or None.
    """
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


def extract_articles_from_html(html_content):
    """
    Robust extraction of articles from JSON-LD blocks in the HTML.
    Returns list of article dicts (as found in JSON-LD 'hasPart' items).
    """
    logger.info("Extracting articles from HTML content (searching JSON-LD)")

    try:
        scripts = re.findall(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            html_content,
            flags=re.S | re.I
        )
        if not scripts:
            logger.error("No application/ld+json script tags found")
            return []

        for json_text in scripts:
            json_text = json_text.strip()
            if not json_text:
                continue

            # Try direct parse, then naive cleaning if it fails
            try:
                data = json.loads(json_text)
            except json.JSONDecodeError:
                cleaned = re.sub(r',\s*}', '}', json_text)
                cleaned = re.sub(r',\s*]', ']', cleaned)
                try:
                    data = json.loads(cleaned)
                except Exception as e:
                    logger.debug(f"Skipping JSON-LD block (parse failed): {e}")
                    continue

            # If dict with @graph
            if isinstance(data, dict):
                graph = data.get('@graph')
                if isinstance(graph, list):
                    for item in graph:
                        if item.get('@type') == 'PublicationIssue':
                            articles = item.get('hasPart', [])
                            logger.info(f"Found {len(articles)} articles inside PublicationIssue (@graph)")
                            return articles

                if data.get('@type') == 'PublicationIssue':
                    articles = data.get('hasPart', [])
                    logger.info(f"Found {len(articles)} articles (top-level PublicationIssue)")
                    return articles

            # If top-level list
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get('@type') == 'PublicationIssue':
                        articles = item.get('hasPart', [])
                        logger.info(f"Found {len(articles)} articles inside PublicationIssue (list)")
                        return articles

        logger.warning("No PublicationIssue found in any JSON-LD blocks")
        return []

    except Exception as e:
        logger.error(f"Error extracting articles: {e}")
        return []


def escape_xml(text):
    """Escape special XML characters; returns empty string for falsy input."""
    if not text:
        return ''
    text = str(text)
    return (text.replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&apos;'))


def parse_pubdate_iso_to_rfc822(pub_date_iso):
    """
    Convert ISO 8601 (e.g. 2026-02-01T12:34:56Z) to RFC-822 style with timezone.
    Returns string or empty on failure.
    """
    if not pub_date_iso:
        return ''
    try:
        # handle 'Z' and timezone-less strings
        if pub_date_iso.endswith('Z'):
            dt = datetime.fromisoformat(pub_date_iso.replace('Z', '+00:00'))
        else:
            # if no timezone, treat as UTC
            if re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$', pub_date_iso):
                dt = datetime.fromisoformat(pub_date_iso + '+00:00')
            else:
                dt = datetime.fromisoformat(pub_date_iso)
        return dt.strftime('%a, %d %b %Y %H:%M:%S %z')
    except Exception as e:
        logger.debug(f"Could not parse date '{pub_date_iso}': {e}")
        return ''


def normalize_author_field(author_field):
    """
    author_field may be:
    - string: 'Jane Doe'
    - dict: {'@type': 'Person', 'name': 'Jane Doe'}
    - list: [ {...}, {...} ]
    Returns first author name or empty string.
    """
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
                return a.get('name')
    return ''


def extract_description(article):
    """
    description may be in 'about', 'description', or nested fields.
    Return a short string or ''.
    """
    about = article.get('about')
    if isinstance(about, str):
        return about
    if isinstance(about, dict):
        # try common keys
        return about.get('description') or about.get('name') or ''
    desc = article.get('description') or article.get('dek') or ''
    if isinstance(desc, dict):
        return desc.get('description') or desc.get('name') or ''
    if isinstance(desc, list):
        # join short strings if it's a list
        return ' '.join([str(x) for x in desc if isinstance(x, str)])[:500]
    return desc if isinstance(desc, str) else ''


def extract_image_url(image_field):
    """
    image_field may be:
    - string URL
    - dict {'@type':'ImageObject','url':'...'}
    - list [ ... ]
    Returns first usable URL or ''.
    """
    if not image_field:
        return ''
    if isinstance(image_field, str):
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
    """
    Build an RSS 2.0 feed string from article dicts.
    """
    logger.info("Creating RSS feed")
    build_date = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")

    rss_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:media="http://search.yahoo.com/mrss/">',
        '  <channel>',
        f'    <title>{escape_xml("Scientific American - Latest Issue")}</title>',
        f'    <link>{escape_xml(PAGE_URL)}</link>',
        f'    <description>{escape_xml("Latest articles from Scientific American magazine")}</description>',
        '    <language>en-us</language>',
        f'    <lastBuildDate>{build_date}</lastBuildDate>',
        '    <atom:link href="https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/feed.xml" rel="self" type="application/rss+xml"/>',
        ''
    ]

    item_count = 0
    for article in articles:
        if not isinstance(article, dict):
            continue
        # Skip non-Article types
        if article.get('@type') and article.get('@type') != 'Article':
            # some feeds omit @type; allow those
            pass

        item_count += 1

        # title
        title = article.get('headline') or article.get('name') or 'Untitled Article'

        # url: prefer 'url', then '@id'
        raw_url = article.get('url') or article.get('@id') or ''
        article_url = urljoin(BASE_URL, raw_url) if raw_url else ''

        # description
        description = extract_description(article)

        # pub date
        pub_date_iso = article.get('datePublished') or article.get('dateCreated') or ''
        rfc822_date = parse_pubdate_iso_to_rfc822(pub_date_iso)

        # image
        image_url = extract_image_url(article.get('image', ''))
        if image_url:
            image_url = urljoin(BASE_URL, image_url)

        # author
        author_name = normalize_author_field(article.get('author'))

        # GUID
        guid_value = article_url or title
        is_permalink = 'true' if article_url and article_url.startswith('http') else 'false'

        # Build item
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
            # try to guess MIME type from filename; default to image/jpeg
            rss_lines.append(f'      <enclosure url="{escape_xml(image_url)}" type="image/jpeg"/>')

        rss_lines.append('    </item>')
        rss_lines.append('')

    rss_lines.append('  </channel>')
    rss_lines.append('</rss>')

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
        logger.error("No articles found via JSON-LD extraction")
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