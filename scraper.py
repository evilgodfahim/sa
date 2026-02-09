#!/usr/bin/env python3
"""
Scientific American Latest Issue Scraper
Fetches articles from the latest issue and generates an RSS feed
"""

import json
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from xml.dom import minidom
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


def create_rss_feed(articles):
    """
    Create an RSS 2.0 feed from the articles
    """
    logger.info("Creating RSS feed")
    
    # Create RSS root element
    rss = ET.Element('rss', version='2.0')
    rss.set('xmlns:atom', 'http://www.w3.org/2005/Atom')
    rss.set('xmlns:dc', 'http://purl.org/dc/elements/1.1/')
    rss.set('xmlns:media', 'http://search.yahoo.com/mrss/')
    
    channel = ET.SubElement(rss, 'channel')
    
    # Channel metadata
    ET.SubElement(channel, 'title').text = 'Scientific American - Latest Issue'
    ET.SubElement(channel, 'link').text = SCIENTIFIC_AMERICAN_URL
    ET.SubElement(channel, 'description').text = 'Latest articles from Scientific American magazine'
    ET.SubElement(channel, 'language').text = 'en-us'
    ET.SubElement(channel, 'lastBuildDate').text = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S +0000')
    
    # Add atom:link for self-reference
    atom_link = ET.SubElement(channel, '{http://www.w3.org/2005/Atom}link')
    atom_link.set('href', 'https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/feed.xml')
    atom_link.set('rel', 'self')
    atom_link.set('type', 'application/rss+xml')
    
    # Add each article as an item
    for article in articles:
        if article.get('@type') != 'Article':
            continue
        
        item = ET.SubElement(channel, 'item')
        
        # Title
        title = article.get('headline', 'Untitled Article')
        ET.SubElement(item, 'title').text = title
        
        # Link - construct from headline if URL not provided
        article_url = article.get('url', '')
        if not article_url and article.get('@id'):
            article_url = article.get('@id')
        ET.SubElement(item, 'link').text = article_url
        
        # Description
        description = article.get('about', article.get('description', ''))
        ET.SubElement(item, 'description').text = description
        
        # Publication date
        pub_date = article.get('datePublished', '')
        if pub_date:
            try:
                # Parse ISO 8601 date and convert to RFC 822
                dt = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                rfc822_date = dt.strftime('%a, %d %b %Y %H:%M:%S %z')
                ET.SubElement(item, 'pubDate').text = rfc822_date
            except Exception as e:
                logger.warning(f"Could not parse date '{pub_date}': {e}")
        
        # Author
        authors = article.get('author', [])
        if authors:
            if isinstance(authors, list) and len(authors) > 0:
                author_name = authors[0].get('name', '')
                if author_name:
                    ET.SubElement(item, '{http://purl.org/dc/elements/1.1/}creator').text = author_name
                    ET.SubElement(item, 'author').text = author_name
        
        # GUID
        guid = ET.SubElement(item, 'guid')
        guid.set('isPermaLink', 'true' if article_url.startswith('http') else 'false')
        guid.text = article_url if article_url else title
        
        # Image/Thumbnail
        image_url = article.get('image', '')
        if image_url:
            # Add media:thumbnail for Inoreader
            media_thumbnail = ET.SubElement(item, '{http://search.yahoo.com/mrss/}thumbnail')
            media_thumbnail.set('url', image_url)
            
            # Add media:content for better compatibility
            media_content = ET.SubElement(item, '{http://search.yahoo.com/mrss/}content')
            media_content.set('url', image_url)
            media_content.set('medium', 'image')
            
            # Add enclosure for RSS readers that prefer it
            enclosure = ET.SubElement(item, 'enclosure')
            enclosure.set('url', image_url)
            enclosure.set('type', 'image/jpeg')
    
    logger.info(f"Created RSS feed with {len(channel.findall('item'))} items")
    return rss


def prettify_xml(elem):
    """
    Return a pretty-printed XML string for the Element
    """
    rough_string = ET.tostring(elem, encoding='unicode')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ", encoding='UTF-8').decode('utf-8')


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
    rss_feed = create_rss_feed(articles)
    
    # Write to file
    try:
        xml_string = prettify_xml(rss_feed)
        with open(RSS_OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write(xml_string)
        logger.info(f"RSS feed written to {RSS_OUTPUT_FILE}")
        return True
    except Exception as e:
        logger.error(f"Failed to write RSS feed: {e}")
        return False


if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)
