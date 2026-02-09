# Quick Start Guide

## 🚀 Get Your RSS Feed Running in 5 Minutes

### Step 1: Create GitHub Repository

1. Go to [GitHub](https://github.com) and create a new repository
2. Name it something like `sciam-rss-feed`
3. Make it **Public** (required for GitHub Pages)
4. Initialize with README: **No** (we have our own)

### Step 2: Upload Files

Upload all these files to your repository:
- `scraper.py`
- `requirements.txt`
- `docker-compose.yml`
- `Dockerfile`
- `README.md`
- `.gitignore`
- `index.html`
- `LICENSE`
- `feed.xml`
- `.github/workflows/update-feed.yml` (maintain the folder structure)

### Step 3: Configure GitHub Actions

1. Go to your repository **Settings**
2. Click **Actions** → **General**
3. Scroll to **Workflow permissions**
4. Select **Read and write permissions**
5. Click **Save**

### Step 4: Enable GitHub Pages

1. In **Settings**, click **Pages**
2. Under **Source**, select **Deploy from a branch**
3. Select **main** branch
4. Select **/ (root)** folder
5. Click **Save**

### Step 5: Run the Workflow

1. Go to the **Actions** tab
2. Click **Update Scientific American RSS Feed**
3. Click **Run workflow**
4. Select **main** branch
5. Click **Run workflow**

Wait 2-3 minutes for it to complete.

### Step 6: Get Your Feed URL

Your RSS feed will be available at:

```
https://YOUR_USERNAME.github.io/YOUR_REPO/feed.xml
```

Replace:
- `YOUR_USERNAME` with your GitHub username
- `YOUR_REPO` with your repository name

Example:
```
https://johnsmith.github.io/sciam-rss-feed/feed.xml
```

### Step 7: Add to RSS Reader

**Inoreader:**
1. Click the **+** button
2. Select **Feed**
3. Paste your feed URL
4. Click **Subscribe**

**Feedly:**
1. Click **Add Content**
2. Paste your feed URL
3. Click **Follow**

**Any other RSS reader:**
1. Look for "Add Feed" or "Subscribe"
2. Paste your feed URL
3. Subscribe!

## 🎉 Done!

Your feed will automatically update daily at 6 AM UTC.

## Troubleshooting

### GitHub Actions not running?
- Check that you enabled "Read and write permissions"
- Make sure the `.github/workflows/` folder structure is correct

### Feed URL not working?
- Wait a few minutes after enabling GitHub Pages
- Check the Actions tab to see if the workflow succeeded
- Make sure your repository is public

### Want to test locally first?

```bash
# Install Python dependencies
pip install -r requirements.txt

# Run FlareSolverr
docker run -d -p 8191:8191 ghcr.io/flaresolverr/flaresolverr:latest

# Run scraper
python scraper.py

# Check feed.xml file
```

## Need Help?

Open an issue on GitHub or check the full README.md for detailed documentation.
