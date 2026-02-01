# KI Job Scraper

Automated scraper for PhD and research positions at Karolinska Institutet (KI), with push notifications and a live dashboard.

## Features

- Monitors 3 job sources:
  - [KI Doctoral positions](https://kidoktorand.varbi.com/en/)
  - [KI Staff positions](https://ki.varbi.com/en/)
  - [Academic Positions - KI PhDs](https://academicpositions.com/jobs/employer/karolinska-institutet/position/phd)

- Keyword matching for relevant positions:
  - **High priority**: organoid, iPSC, induced pluripotent, stem cell, neuroscience, neurodevelopmental, neural stem, brain organoid, single-cell, scRNA-seq, spatial transcriptomics
  - **Medium priority**: CRISPR, genome editing, developmental biology, cell culture, bioinformatics, computational biology

- Push notifications via [ntfy.sh](https://ntfy.sh) when new matching positions appear
- Static HTML dashboard showing all current matching positions
- Runs daily via GitHub Actions

## Setup

### 1. Create GitHub Repository

```bash
# Clone or copy this folder to a new repo
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/ki-job-scraper.git
git push -u origin main
```

### 2. Enable GitHub Pages

1. Go to your repository **Settings**
2. Navigate to **Pages** (in the sidebar)
3. Under "Source", select **Deploy from a branch**
4. Select **main** branch and **/docs** folder
5. Click Save

Your dashboard will be available at: `https://YOUR_USERNAME.github.io/ki-job-scraper/`

### 3. Subscribe to Notifications

Install the ntfy app on your phone:
- [iOS App Store](https://apps.apple.com/app/ntfy/id1625396347)
- [Google Play Store](https://play.google.com/store/apps/details?id=io.heckel.ntfy)

Subscribe to the topic: `andrada-ki-jobs`

Or open in browser: https://ntfy.sh/andrada-ki-jobs

## Usage

### Automatic Runs

The scraper runs automatically every day at 9:00 AM CET via GitHub Actions.

### Manual Trigger

1. Go to **Actions** tab in your repository
2. Select **KI Job Scraper** workflow
3. Click **Run workflow**
4. Optionally check "Send test notification" to verify ntfy is working

### Test Notifications Locally

```bash
pip install -r requirements.txt
python -m scraper.main --test-notify
```

### Run Scraper Locally

```bash
pip install -r requirements.txt
python -m scraper.main
```

## File Structure

```
ki-job-scraper/
├── .github/
│   └── workflows/
│       └── scrape.yml          # GitHub Actions workflow
├── scraper/
│   ├── __init__.py
│   ├── main.py                 # Main entry point
│   ├── notifier.py             # ntfy.sh notifications
│   └── sites/
│       ├── __init__.py
│       ├── ki_doktorand.py     # KI doctoral positions scraper
│       ├── ki_varbi.py         # KI staff positions scraper
│       └── academic_positions.py  # Academic Positions scraper
├── data/
│   └── seen_jobs.json          # Tracks seen jobs (auto-updated)
├── docs/
│   └── index.html              # Dashboard (auto-generated)
├── requirements.txt
└── README.md
```

## Dashboard Features

- Lists all currently open matching positions
- Sorted by urgency (closing soon first) and priority
- Shows matched keywords for each position
- Mobile-friendly design
- Updates automatically after each scrape

## Customization

### Change Keywords

Edit the keyword lists in `scraper/main.py`:

```python
HIGH_PRIORITY_KEYWORDS = [
    'organoid', 'ipsc', ...
]

MEDIUM_PRIORITY_KEYWORDS = [
    'crispr', 'genome editing', ...
]
```

### Change Notification Topic

Edit `NTFY_TOPIC` in `scraper/notifier.py`:

```python
NTFY_TOPIC = "your-custom-topic"
```

### Change Schedule

Edit the cron expression in `.github/workflows/scrape.yml`:

```yaml
schedule:
  - cron: '0 8 * * *'  # 8:00 UTC = 9:00 CET
```

## Notes

- No API keys or authentication needed
- Job data is stored in the repository and updated via GitHub Actions
- Notifications are instant via ntfy.sh (no account required)
- Expired jobs are automatically removed from the dashboard
