#!/usr/bin/env python3
"""
KI Job Scraper - Main entry point

Scrapes PhD and research positions at Karolinska Institutet,
matches against keywords, sends notifications, and generates dashboard.
"""

import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Set, Tuple
import re

from scraper.sites import ki_doktorand, ki_varbi, academic_positions
from scraper import notifier

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_FILE = PROJECT_ROOT / "data" / "seen_jobs.json"
DASHBOARD_FILE = PROJECT_ROOT / "docs" / "index.html"

# Keywords configuration
HIGH_PRIORITY_KEYWORDS = [
    'organoid', 'ipsc', 'induced pluripotent', 'stem cell',
    'neuroscience', 'neurodevelopmental', 'neural stem',
    'brain organoid', 'single-cell', 'scrna-seq', 'spatial transcriptomics'
]

MEDIUM_PRIORITY_KEYWORDS = [
    'crispr', 'genome editing', 'developmental biology', 'developmental',
    'cell culture', 'bioinformatics', 'computational biology',
    'molecular biology', 'immunology', 'genetics', 'immunotherapies', 'genetic engineering'
]

ALL_KEYWORDS = HIGH_PRIORITY_KEYWORDS + MEDIUM_PRIORITY_KEYWORDS

# Exclude positions requiring a PhD (postdoc, etc.)
EXCLUDED_TITLE_PATTERNS = ['postdoc', 'post-doc', 'postdoctoral']


def load_seen_jobs() -> Dict:
    """Load the seen jobs database"""
    try:
        if DATA_FILE.exists():
            with open(DATA_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading seen jobs: {e}")

    return {"jobs": {}, "last_updated": None}


def save_seen_jobs(data: Dict) -> None:
    """Save the seen jobs database"""
    try:
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        logger.info(f"Saved {len(data['jobs'])} jobs to database")
    except Exception as e:
        logger.error(f"Error saving seen jobs: {e}")


def match_keywords(job: Dict) -> List[str]:
    """
    Check if a job matches any of our keywords.
    Returns list of matched keywords.
    """
    # Combine title and description for matching
    text = f"{job.get('title', '')} {job.get('description', '')}".lower()

    matched = []
    for keyword in ALL_KEYWORDS:
        # Use word boundary matching for better accuracy
        pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
        if re.search(pattern, text):
            matched.append(keyword)

    return matched


def is_closing_soon(job: Dict) -> bool:
    """Check if job deadline is within 7 days"""
    deadline = job.get('deadline_date')
    if deadline:
        if isinstance(deadline, str):
            try:
                deadline = datetime.fromisoformat(deadline)
            except ValueError:
                return False
        days_left = (deadline - datetime.now()).days
        return 0 <= days_left <= 7
    return False


def scrape_all_sources() -> List[Dict]:
    """Scrape all job sources and return combined list"""
    all_jobs = []

    # Scrape each source
    scrapers = [
        ('KI Doctoral', ki_doktorand.scrape),
        ('KI Staff', ki_varbi.scrape),
        ('Academic Positions', academic_positions.scrape),
    ]

    for name, scraper in scrapers:
        try:
            logger.info(f"Scraping {name}...")
            jobs = scraper()
            all_jobs.extend(jobs)
            logger.info(f"  Found {len(jobs)} positions")
        except Exception as e:
            logger.error(f"Error scraping {name}: {e}")

    return all_jobs


def process_jobs(all_jobs: List[Dict], seen_data: Dict) -> Tuple[List[Dict], List[Dict]]:
    """
    Process scraped jobs, identify new and matching ones.

    Returns:
        (new_matching_jobs, all_matching_jobs)
    """
    new_matching = []
    all_matching = []

    for job in all_jobs:
        job_id = job['id']

        # Skip postdoc positions (requires PhD)
        title_lower = job['title'].lower()
        if any(pattern in title_lower for pattern in EXCLUDED_TITLE_PATTERNS):
            continue

        matched_keywords = match_keywords(job)

        if not matched_keywords:
            continue

        # Add keyword info to job
        job['matched_keywords'] = matched_keywords
        job['is_high_priority'] = any(k in HIGH_PRIORITY_KEYWORDS for k in matched_keywords)
        job['closing_soon'] = is_closing_soon(job)

        all_matching.append(job)

        # Check if this is a new job
        if job_id not in seen_data['jobs']:
            new_matching.append(job)
            # Mark as seen
            seen_data['jobs'][job_id] = {
                'first_seen': datetime.now().isoformat(),
                'title': job['title'],
                'url': job['url'],
                'source': job['source'],
                'deadline': job.get('deadline'),
                'matched_keywords': matched_keywords
            }

    return new_matching, all_matching


def generate_dashboard(matching_jobs: List[Dict], last_updated: str) -> None:
    """Generate the static HTML dashboard"""
    # Sort jobs: closing soon first, then by priority, then alphabetically
    sorted_jobs = sorted(
        matching_jobs,
        key=lambda j: (
            not j.get('closing_soon', False),
            not j.get('is_high_priority', False),
            j.get('title', '').lower()
        )
    )

    # Group by source
    by_source = {}
    for job in sorted_jobs:
        source = job.get('source', 'unknown')
        if source not in by_source:
            by_source[source] = []
        by_source[source].append(job)

    source_names = {
        'ki_doktorand': 'KI Doctoral Positions',
        'ki_varbi': 'KI Staff Positions',
        'academic_positions': 'Academic Positions'
    }

    # Generate job data as JSON for JavaScript
    import json
    jobs_json = json.dumps([{
        'id': job['id'],
        'title': job['title'],
        'url': job['url'],
        'deadline': job.get('deadline'),
        'deadline_date': job.get('deadline_date').isoformat() if job.get('deadline_date') and hasattr(job.get('deadline_date'), 'isoformat') else job.get('deadline_date'),
        'source': job['source'],
        'matched_keywords': job.get('matched_keywords', []),
        'is_high_priority': job.get('is_high_priority', False),
        'closing_soon': job.get('closing_soon', False)
    } for job in matching_jobs])

    # Generate HTML
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Andrada - KI</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🧬</text></svg>">
    <style>
        :root {{
            --primary: #1a365d;
            --accent: #2c5282;
            --success: #276749;
            --warning: #c05621;
            --light: #f7fafc;
            --border: #e2e8f0;
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--light);
            color: #2d3748;
            line-height: 1.6;
            padding: 1rem;
        }}
        .top-container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        .main-layout {{
            display: grid;
            grid-template-columns: 1fr 350px;
            gap: 1.5rem;
            max-width: 1400px;
            margin: 0 auto;
        }}
        .left-column {{
            min-width: 0;
        }}
        .right-column {{
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }}
        header {{
            background: var(--primary);
            color: white;
            padding: 1.5rem;
            border-radius: 8px;
            margin-bottom: 1.5rem;
        }}
        header h1 {{
            font-size: 1.5rem;
            margin-bottom: 0.5rem;
        }}
        .subtitle {{
            opacity: 0.9;
            font-size: 0.9rem;
        }}
        .stats {{
            display: flex;
            gap: 1rem;
            margin-top: 1rem;
            flex-wrap: wrap;
        }}
        .stat {{
            background: rgba(255,255,255,0.15);
            padding: 0.5rem 1rem;
            border-radius: 4px;
            font-size: 0.85rem;
        }}
        .stat strong {{
            font-size: 1.2rem;
        }}
        .section {{
            background: white;
            border-radius: 8px;
            padding: 1rem;
            margin-bottom: 1rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        .section h2 {{
            color: var(--primary);
            font-size: 1.1rem;
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 2px solid var(--border);
        }}
        .section.applied {{
            border-left: 4px solid var(--success);
        }}
        .section.applied h2 {{
            color: var(--success);
        }}
        .section.irrelevant {{
            border-left: 4px solid #a0aec0;
        }}
        .section.irrelevant h2 {{
            color: #718096;
        }}
        .job-list {{
            list-style: none;
        }}
        .job {{
            padding: 1rem;
            border-bottom: 1px solid var(--border);
        }}
        .job:last-child {{
            border-bottom: none;
        }}
        .job-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 0.5rem;
        }}
        .job-title {{
            font-weight: 600;
            color: var(--accent);
            text-decoration: none;
            flex: 1;
        }}
        .job-title:hover {{
            text-decoration: underline;
        }}
        .job-actions {{
            display: flex;
            gap: 0.25rem;
            flex-shrink: 0;
        }}
        .btn {{
            padding: 0.25rem 0.5rem;
            border: none;
            border-radius: 4px;
            font-size: 0.7rem;
            cursor: pointer;
            transition: opacity 0.2s;
        }}
        .btn:hover {{
            opacity: 0.8;
        }}
        .btn-applied {{
            background: #c6f6d5;
            color: var(--success);
        }}
        .btn-irrelevant {{
            background: #e2e8f0;
            color: #718096;
        }}
        .btn-undo {{
            background: #fed7d7;
            color: #c53030;
        }}
        .job-meta {{
            display: flex;
            gap: 1rem;
            flex-wrap: wrap;
            font-size: 0.85rem;
            color: #718096;
            margin-top: 0.5rem;
        }}
        .badge {{
            display: inline-block;
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 500;
        }}
        .badge-high {{
            background: #fed7d7;
            color: #c53030;
        }}
        .badge-closing {{
            background: #feebc8;
            color: var(--warning);
        }}
        .badge-keyword {{
            background: #e2e8f0;
            color: #4a5568;
        }}
        .keywords {{
            margin-top: 0.5rem;
            display: flex;
            gap: 0.25rem;
            flex-wrap: wrap;
        }}
        .empty {{
            color: #a0aec0;
            text-align: center;
            padding: 1rem;
            font-size: 0.9rem;
        }}
        footer {{
            text-align: center;
            color: #a0aec0;
            font-size: 0.8rem;
            margin-top: 2rem;
        }}
        footer a {{
            color: var(--accent);
        }}
        .easter-egg {{
            text-align: center;
            padding: 1.5rem;
            margin-bottom: 1rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 8px;
            color: white;
        }}
        .easter-egg img {{
            width: 100px;
            height: 100px;
            border-radius: 50%;
            border: 3px solid white;
            margin-bottom: 0.75rem;
            object-fit: cover;
        }}
        .easter-egg p {{
            margin: 0;
            font-size: 1.1rem;
            font-weight: 500;
        }}
        .right-job {{
            padding: 0.75rem;
            border-bottom: 1px solid var(--border);
            font-size: 0.85rem;
        }}
        .right-job:last-child {{
            border-bottom: none;
        }}
        .right-job-title {{
            font-weight: 500;
            color: var(--accent);
            text-decoration: none;
            display: block;
            margin-bottom: 0.25rem;
        }}
        .right-job-title:hover {{
            text-decoration: underline;
        }}
        .right-job-meta {{
            font-size: 0.75rem;
            color: #718096;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        @media (max-width: 900px) {{
            .main-layout {{
                grid-template-columns: 1fr;
            }}
            .right-column {{
                order: -1;
            }}
        }}
        @media (max-width: 600px) {{
            body {{
                padding: 0.5rem;
            }}
            header {{
                padding: 1rem;
            }}
            .job-meta {{
                flex-direction: column;
                gap: 0.5rem;
            }}
            .job-header {{
                flex-direction: column;
            }}
            .job-actions {{
                align-self: flex-start;
            }}
        }}
    </style>
</head>
<body>
    <div class="top-container">
        <div class="easter-egg">
            <img src="andrada.jpeg" alt="Andrada Balmez">
            <p>Future PhD Student: Andrada Balmez</p>
        </div>
        <header>
            <h1>KI Research Position Tracker</h1>
            <p class="subtitle">PhD &amp; Research positions at Karolinska Institutet</p>
            <p class="subtitle">Focus: iPSC/Organoids, Single-cell, Neuroscience</p>
            <div class="stats">
                <div class="stat"><strong id="stat-total">{len(matching_jobs)}</strong> matching positions</div>
                <div class="stat"><strong id="stat-closing">{sum(1 for j in matching_jobs if j.get('closing_soon'))}</strong> closing soon</div>
                <div class="stat"><strong id="stat-high">{sum(1 for j in matching_jobs if j.get('is_high_priority'))}</strong> high priority</div>
            </div>
        </header>
    </div>

    <div class="main-layout">
        <div class="left-column" id="main-jobs">
            <div class="section"><p class="empty">Loading...</p></div>
        </div>
        <div class="right-column">
            <div class="section applied">
                <h2>Applied (<span id="applied-count">0</span>)</h2>
                <ul class="job-list" id="applied-list">
                    <li class="empty" id="applied-empty">No applications yet</li>
                </ul>
            </div>
            <div class="section irrelevant">
                <h2>Irrelevant (<span id="irrelevant-count">0</span>)</h2>
                <ul class="job-list" id="irrelevant-list">
                    <li class="empty" id="irrelevant-empty">None marked</li>
                </ul>
            </div>
        </div>
    </div>

    <footer>
        <p>Last updated: {last_updated}</p>
        <p>Subscribe to notifications: <a href="https://ntfy.sh/andrada-ki-jobs">ntfy.sh/andrada-ki-jobs</a></p>
        <p style="margin-top: 0.5rem;">
            <button onclick="exportState()" style="padding: 0.3rem 0.8rem; margin-right: 0.5rem; cursor: pointer;">Export</button>
            <button onclick="importState()" style="padding: 0.3rem 0.8rem; cursor: pointer;">Import</button>
            <span style="font-size: 0.7rem; margin-left: 0.5rem;">(sync between devices)</span>
        </p>
    </footer>

    <script>
        const allJobs = {jobs_json};
        const sourceNames = {{
            'ki_doktorand': 'KI Doctoral Positions',
            'ki_varbi': 'KI Staff Positions',
            'academic_positions': 'Academic Positions'
        }};

        let applied = [];
        let irrelevant = [];

        // Load state from localStorage
        function loadState() {{
            applied = JSON.parse(localStorage.getItem('ki-jobs-applied') || '[]');
            irrelevant = JSON.parse(localStorage.getItem('ki-jobs-irrelevant') || '[]');
            render();
        }}

        // Save state to localStorage
        function saveState() {{
            localStorage.setItem('ki-jobs-applied', JSON.stringify(applied));
            localStorage.setItem('ki-jobs-irrelevant', JSON.stringify(irrelevant));
        }}

        // Export state as JSON string (for manual sync)
        function exportState() {{
            const data = JSON.stringify({{ applied, irrelevant }}, null, 2);
            navigator.clipboard.writeText(data).then(() => {{
                alert('State copied to clipboard! Paste it on another device using Import.');
            }}).catch(() => {{
                prompt('Copy this data:', data);
            }});
        }}

        // Import state from JSON string (for manual sync)
        function importState() {{
            const data = prompt('Paste the exported state here:');
            if (data) {{
                try {{
                    const parsed = JSON.parse(data);
                    // Merge with existing
                    applied = [...new Set([...applied, ...(parsed.applied || [])])];
                    irrelevant = [...new Set([...irrelevant, ...(parsed.irrelevant || [])])];
                    saveState();
                    render();
                    alert('State imported successfully!');
                }} catch (e) {{
                    alert('Invalid data format');
                }}
            }}
        }}

        function formatDate(dateStr) {{
            if (!dateStr) return 'Not specified';
            try {{
                const date = new Date(dateStr);
                return date.toLocaleDateString('en-GB', {{ day: '2-digit', month: 'short', year: 'numeric' }});
            }} catch {{
                return dateStr;
            }}
        }}

        function createJobCard(job, showUndo = false, undoAction = null) {{
            const badges = [];
            if (job.is_high_priority) badges.push('<span class="badge badge-high">High Priority</span>');
            if (job.closing_soon) badges.push('<span class="badge badge-closing">Closing Soon</span>');

            const keywords = job.matched_keywords.map(k => `<span class="badge badge-keyword">${{k}}</span>`).join('');
            const deadline = formatDate(job.deadline_date || job.deadline);

            let actions = '';
            if (showUndo) {{
                actions = `<button class="btn btn-undo" onclick="undoJob('${{job.id}}', '${{undoAction}}')">Undo</button>`;
            }} else {{
                actions = `
                    <button class="btn btn-applied" onclick="markApplied('${{job.id}}')">Applied</button>
                    <button class="btn btn-irrelevant" onclick="markIrrelevant('${{job.id}}')">Irrelevant</button>
                `;
            }}

            return `
                <li class="job" data-job-id="${{job.id}}">
                    <div class="job-header">
                        <a href="${{job.url}}" class="job-title" target="_blank">${{job.title}}</a>
                        <div class="job-actions">${{actions}}</div>
                    </div>
                    <div class="job-meta">
                        <span>Deadline: ${{deadline}}</span>
                        ${{badges.join(' ')}}
                    </div>
                    <div class="keywords">${{keywords}}</div>
                </li>
            `;
        }}

        function createRightJobCard(job, listType) {{
            const deadline = formatDate(job.deadline_date || job.deadline);
            return `
                <li class="right-job" data-job-id="${{job.id}}">
                    <a href="${{job.url}}" class="right-job-title" target="_blank">${{job.title}}</a>
                    <div class="right-job-meta">
                        <span>${{deadline}}</span>
                        <button class="btn btn-undo" onclick="undoJob('${{job.id}}', '${{listType}}')">Undo</button>
                    </div>
                </li>
            `;
        }}

        function markApplied(jobId) {{
            if (!applied.includes(jobId)) {{
                applied.push(jobId);
                irrelevant = irrelevant.filter(id => id !== jobId);
                saveState();
                render();
            }}
        }}

        function markIrrelevant(jobId) {{
            if (!irrelevant.includes(jobId)) {{
                irrelevant.push(jobId);
                applied = applied.filter(id => id !== jobId);
                saveState();
                render();
            }}
        }}

        function undoJob(jobId, listType) {{
            if (listType === 'applied') {{
                applied = applied.filter(id => id !== jobId);
            }} else {{
                irrelevant = irrelevant.filter(id => id !== jobId);
            }}
            saveState();
            render();
        }}

        function render() {{
            const mainJobs = allJobs.filter(j => !applied.includes(j.id) && !irrelevant.includes(j.id));
            const appliedJobs = allJobs.filter(j => applied.includes(j.id));
            const irrelevantJobs = allJobs.filter(j => irrelevant.includes(j.id));

            // Group main jobs by source
            const bySource = {{}};
            mainJobs.forEach(job => {{
                if (!bySource[job.source]) bySource[job.source] = [];
                bySource[job.source].push(job);
            }});

            // Render main jobs
            const mainContainer = document.getElementById('main-jobs');
            if (mainJobs.length === 0) {{
                mainContainer.innerHTML = '<div class="section"><p class="empty">No matching positions found. Check back later!</p></div>';
            }} else {{
                let html = '';
                for (const [source, jobs] of Object.entries(bySource)) {{
                    const sourceName = sourceNames[source] || source;
                    html += `<div class="section"><h2>${{sourceName}} (${{jobs.length}})</h2><ul class="job-list">`;
                    jobs.forEach(job => {{
                        html += createJobCard(job);
                    }});
                    html += '</ul></div>';
                }}
                mainContainer.innerHTML = html;
            }}

            // Render applied
            const appliedList = document.getElementById('applied-list');
            const appliedEmpty = document.getElementById('applied-empty');
            document.getElementById('applied-count').textContent = appliedJobs.length;
            if (appliedJobs.length === 0) {{
                appliedList.innerHTML = '<li class="empty">No applications yet</li>';
            }} else {{
                appliedList.innerHTML = appliedJobs.map(j => createRightJobCard(j, 'applied')).join('');
            }}

            // Render irrelevant
            const irrelevantList = document.getElementById('irrelevant-list');
            document.getElementById('irrelevant-count').textContent = irrelevantJobs.length;
            if (irrelevantJobs.length === 0) {{
                irrelevantList.innerHTML = '<li class="empty">None marked</li>';
            }} else {{
                irrelevantList.innerHTML = irrelevantJobs.map(j => createRightJobCard(j, 'irrelevant')).join('');
            }}

            // Update stats
            document.getElementById('stat-total').textContent = mainJobs.length;
            document.getElementById('stat-closing').textContent = mainJobs.filter(j => j.closing_soon).length;
            document.getElementById('stat-high').textContent = mainJobs.filter(j => j.is_high_priority).length;
        }}

        // Initial load from cloud
        loadState();
    </script>
</body>
</html>
'''

    # Write dashboard
    try:
        DASHBOARD_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(DASHBOARD_FILE, 'w') as f:
            f.write(html)
        logger.info(f"Dashboard generated: {DASHBOARD_FILE}")
    except Exception as e:
        logger.error(f"Error generating dashboard: {e}")


def cleanup_old_jobs(seen_data: Dict, current_job_ids: Set[str]) -> int:
    """Remove jobs that are no longer listed (expired)"""
    old_jobs = [jid for jid in seen_data['jobs'] if jid not in current_job_ids]
    for jid in old_jobs:
        del seen_data['jobs'][jid]
    return len(old_jobs)


def main():
    """Main entry point"""
    logger.info("=" * 60)
    logger.info("KI Job Scraper - Starting")
    logger.info("=" * 60)

    # Load existing data
    seen_data = load_seen_jobs()
    logger.info(f"Loaded {len(seen_data['jobs'])} previously seen jobs")

    # Scrape all sources
    all_jobs = scrape_all_sources()
    logger.info(f"Total jobs scraped: {len(all_jobs)}")

    # Get current job IDs for cleanup
    current_job_ids = {job['id'] for job in all_jobs}

    # Process jobs
    new_matching, all_matching = process_jobs(all_jobs, seen_data)

    logger.info(f"Matching jobs: {len(all_matching)}")
    logger.info(f"New matching jobs: {len(new_matching)}")

    # Send notifications for new matching jobs
    notification_count = 0
    for job in new_matching:
        logger.info(f"  NEW: {job['title']}")
        logger.info(f"       Keywords: {', '.join(job['matched_keywords'])}")
        if notifier.send_notification(job, job['matched_keywords']):
            notification_count += 1

    # Cleanup expired jobs
    removed = cleanup_old_jobs(seen_data, current_job_ids)
    if removed:
        logger.info(f"Removed {removed} expired jobs from database")

    # Update timestamp and save
    now = datetime.now()
    seen_data['last_updated'] = now.isoformat()
    save_seen_jobs(seen_data)

    # Generate dashboard
    last_updated = now.strftime("%Y-%m-%d %H:%M CET")
    generate_dashboard(all_matching, last_updated)

    # Summary
    logger.info("=" * 60)
    logger.info("Summary:")
    logger.info(f"  Total scraped: {len(all_jobs)}")
    logger.info(f"  Matching: {len(all_matching)}")
    logger.info(f"  New: {len(new_matching)}")
    logger.info(f"  Notifications sent: {notification_count}")
    logger.info("=" * 60)

    return 0


def test_notifications():
    """Test that notifications are working"""
    logger.info("Sending test notification...")
    if notifier.send_test_notification():
        logger.info("Test notification sent! Check your phone.")
        return 0
    else:
        logger.error("Failed to send test notification")
        return 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test-notify":
        sys.exit(test_notifications())
    else:
        sys.exit(main())
