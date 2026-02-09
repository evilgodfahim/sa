# Scientific American RSS Feed Generator

Automated scraper that fetches articles from Scientific American's latest issue and generates an Inoreader-compatible RSS feed.

## Features

- 🔥 Uses FlareSolverr to bypass Cloudflare protection
- 📰 Extracts articles from JSON-LD structured data
- 🖼️ Includes article thumbnails/images
- 📅 Automatic daily updates via GitHub Actions
- 📱 Inoreader compatible RSS 2.0 feed
- 🐳 Docker support for easy deployment

## RSS Feed URL

Once deployed to GitHub Pages or with Actions enabled:

```
https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/feed.xml
```

Replace `YOUR_USERNAME` and `YOUR_REPO` with your actual GitHub username and repository name.

## Setup Instructions

### Option 1: GitHub Actions (Recommended)

This automatically updates the RSS feed daily.

1. **Fork or clone this repository**

2. **Enable GitHub Actions**
   - Go to your repository settings
   - Navigate to "Actions" → "General"
   - Enable "Read and write permissions" under "Workflow permissions"

3. **Enable GitHub Pages (Optional but recommended)**
   - Go to Settings → Pages
   - Set Source to "Deploy from a branch"
   - Select "main" branch and "/ (root)" folder
   - Your feed will be available at: `https://YOUR_USERNAME.github.io/YOUR_REPO/feed.xml`

4. **Run the workflow**
   - Go to "Actions" tab
   - Select "Update Scientific American RSS Feed"
   - Click "Run workflow"

The feed will automatically update daily at 6 AM UTC.

### Option 2: Local Docker Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
   cd YOUR_REPO
   ```

2. **Run with Docker Compose**
   ```bash
   docker-compose up
   ```

3. **The RSS feed will be generated at `feed.xml`**

### Option 3: Local Python Setup

1. **Install Python 3.11+**

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run FlareSolverr**
   ```bash
   docker run -d \
     --name flaresolverr \
     -p 8191:8191 \
     ghcr.io/flaresolverr/flaresolverr:latest
   ```

4. **Run the scraper**
   ```bash
   python scraper.py
   ```

## How It Works

1. **FlareSolverr** acts as a proxy that solves Cloudflare challenges
2. The scraper fetches `https://www.scientificamerican.com/latest-issue/`
3. Extracts article data from the JSON-LD structured data in the page
4. Generates an RSS 2.0 feed with:
   - Article titles
   - Authors
   - Publication dates
   - Descriptions
   - Thumbnails/images
   - Links to full articles

## RSS Feed Structure

The generated feed includes:

- **Channel metadata**: Title, description, language, last build date
- **Articles** with:
  - `<title>`: Article headline
  - `<link>`: URL to the full article
  - `<description>`: Article summary
  - `<pubDate>`: Publication date in RFC 822 format
  - `<author>` and `<dc:creator>`: Article author
  - `<media:thumbnail>`: Article image
  - `<media:content>`: Article image content
  - `<enclosure>`: Image enclosure for compatibility
  - `<guid>`: Unique identifier

## Adding to Inoreader

1. Copy your feed URL:
   ```
   https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/feed.xml
   ```

2. In Inoreader:
   - Click "Add subscription"
   - Paste the feed URL
   - Click "Subscribe"

## Customization

### Change Update Frequency

Edit `.github/workflows/update-feed.yml`:

```yaml
on:
  schedule:
    # Change this cron expression
    - cron: '0 6 * * *'  # Daily at 6 AM UTC
```

Cron examples:
- Every 6 hours: `0 */6 * * *`
- Twice daily: `0 6,18 * * *`
- Weekly: `0 6 * * 0`

### Modify Scraper Behavior

Edit `scraper.py` to:
- Change the output filename (default: `feed.xml`)
- Adjust FlareSolverr timeout settings
- Customize RSS feed metadata
- Filter specific article types

## Troubleshooting

### GitHub Actions failing

- Check that "Read and write permissions" are enabled in repository settings
- Verify the workflow has permission to push changes

### FlareSolverr timeout

If you get timeout errors, increase the timeout in `scraper.py`:

```python
payload = {
    "cmd": "request.get",
    "url": url,
    "maxTimeout": 120000  # Increase from 60000
}
```

### No articles found

- Check that Scientific American hasn't changed their page structure
- Verify the JSON-LD script tag is still present
- Enable debug logging by setting `LOG_LEVEL=debug` in docker-compose.yml

## Project Structure

```
.
├── .github/
│   └── workflows/
│       └── update-feed.yml    # GitHub Actions workflow
├── scraper.py                 # Main scraper script
├── requirements.txt           # Python dependencies
├── docker-compose.yml         # Docker Compose configuration
├── Dockerfile                 # Docker image definition
├── README.md                  # This file
└── feed.xml                   # Generated RSS feed (after running)
```

## Dependencies

- **Python 3.11+**
- **requests**: HTTP library for Python
- **FlareSolverr**: Cloudflare bypass proxy

## License

MIT License - feel free to use and modify as needed.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Disclaimer

This tool is for personal use and educational purposes. Please respect Scientific American's terms of service and robots.txt. Consider subscribing to their official feeds or magazine if available.
