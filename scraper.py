#!/usr/bin/env python3
"""
Scientific American Latest Issue Scraper
Fetches articles from the latest issue and generates an RSS feed
"""

import json
import requests
from datetime import datetime
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
FLARESOLVERR_URL = os.getenv('FLARESOLVERR_URL', 'http://localhost:8191/v1')
SCIENTIFIC_AMERICAN_URL = "https://www.scientificamerican.com/latest-issue/"
RSS_OUTPUT_FILE = "feed.xml"


def fetch_with_flaresolverr(url):
    """
    Fetch a URL using FlareSolverr to bypass Cloudflare protection
    """
    logger.info(f"Fetching URL via FlareSolverr: {url}")
    
    payload = {
        "cmd": "request.get",
        "url": url,
        "maxTimeout": 60000
    }
    
    try:
        response = requests.post(FLARESOLVERR_URL, json=payload, timeout=70)
        response.raise_for_status()
        data = response.json()
        
        if data.get('status') == 'ok':
            logger.info("Successfully fetched page via FlareSolverr")
            return data['solution']['response']
        else:
            logger.error(f"FlareSolverr error: {data.get('message', 'Unknown error')}")
            return None
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        return None


def extract_articles_from_html(html_content):
    """
    Extract articles from the JSON-LD script tag in the HTML
    """
    logger.info("Extracting articles from HTML content")
    
    try:
        # Find the JSON-LD script tag
        start_marker = '<script type="application/ld+json">{"@context":"https://schema.org","@graph":'
        end_marker = '</script>'
        
        start_idx = html_content.find(start_marker)
        if start_idx == -1:
            logger.error("Could not find JSON-LD script tag")
            return []
        
        start_idx += len('<script type="application/ld+json">')
        end_idx = html_content.find(end_marker, start_idx)
        
        if end_idx == -1:
            logger.error("Could not find end of JSON-LD script tag")
            return []
        
        json_text = html_content[start_idx:end_idx].strip()
        data = json.loads(json_text)
        
        # Extract the PublicationIssue from the @graph
        for item in data.get('@graph', []):
            if item.get('@type') == 'PublicationIssue':
                articles = item.get('hasPart', [])
                logger.info(f"Found {len(articles)} articles")
                return articles
        
        logger.warning("No PublicationIssue found in JSON-LD")
        return []
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON-LD: {e}")
        return []
    except Exception as e:
        logger.error(f"Error extracting articles: {e}")
        return []


def escape_xml(text):
    """Escape special XML characters"""
    if not text:
        return ''
    text = str(text)
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('"', '&quot;')
    text = text.replace("'", '&apos;')
    return text


def create_rss_feed(articles):
    """
    Create an RSS 2.0 feed from the articles using string building
    """
    logger.info("Creating RSS feed")
    
    # Build RSS feed as a string to avoid XML library issues
    rss_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:media="http://search.yahoo.com/mrss/">',
        '  <channel>',
        f'    <title>{escape_xml("Scientific American - Latest Issue")}</title>',
        f'    <link>{escape_xml(SCIENTIFIC_AMERICAN_URL)}</link>',
        f'    <description>{escape_xml("Latest articles from Scientific American magazine")}</description>',
        '    <language>en-us</language>',
        f'    <lastBuildDate>{datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")}</lastBuildDate>',
        '    <atom:link href="https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/feed.xml" rel="self" type="application/rss+xml"/>',
        ''
    ]
    
    # Add each article as an item
    item_count = 0
    for article in articles:
        if article.get('@type') != 'Article':
            continue
        
        item_count += 1
        
        # Extract article data
        title = article.get('headline', 'Untitled Article')
        article_url = article.get('url', article.get('@id', ''))
        description = article.get('about', article.get('description', ''))
        pub_date = article.get('datePublished', '')
        image_url = article.get('image', '')
        
        # Parse publication date
        rfc822_date = ''
        if pub_date:
            try:
                dt = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                rfc822_date = dt.strftime('%a, %d %b %Y %H:%M:%S %z')
            except Exception as e:
                logger.warning(f"Could not parse date '{pub_date}': {e}")
        
        # Get author
        authors = article.get('author', [])
        author_name = ''
        if authors and isinstance(authors, list) and len(authors) > 0:
            author_name = authors[0].get('name', '')
        
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
        
        # GUID
        guid_value = article_url if article_url else title
        is_permalink = 'true' if article_url and article_url.startswith('http') else 'false'
        rss_lines.append(f'      <guid isPermaLink="{is_permalink}">{escape_xml(guid_value)}</guid>')
        
        # Images/Media
        if image_url:
            rss_lines.append(f'      <media:thumbnail url="{escape_xml(image_url)}"/>')
            rss_lines.append(f'      <media:content url="{escape_xml(image_url)}" medium="image"/>')
            rss_lines.append(f'      <enclosure url="{escape_xml(image_url)}" type="image/jpeg"/>')
        
        rss_lines.append('    </item>')
        rss_lines.append('')
    
    # Close channel and RSS
    rss_lines.append('  </channel>')
    rss_lines.append('</rss>')
    
    logger.info(f"Created RSS feed with {item_count} items")
    return '\n'.join(rss_lines)


def main():
    """
    Main function to scrape and generate RSS feed
    """
    logger.info("Starting Scientific American scraper")
    
    # Fetch the page
    html_content = fetch_with_flaresolverr(SCIENTIFIC_AMERICAN_URL)
    
    if not html_content:
        logger.error("Failed to fetch page content")
        return False
    
    # Extract articles
    articles = extract_articles_from_html(html_content)
    
    if not articles:
        logger.error("No articles found")
        return False
    
    # Create RSS feed
    rss_content = create_rss_feed(articles)
    
    # Write to file
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
