"""Scraper for KI Staff positions (ki.varbi.com)"""

import logging
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from datetime import datetime
import re

logger = logging.getLogger(__name__)

BASE_URL = "https://ki.varbi.com/en/"


def scrape() -> List[Dict]:
    """
    Scrape staff positions from ki.varbi.com

    Returns list of job dicts with keys:
    - id: unique identifier
    - title: job title
    - url: direct link to job posting
    - deadline: deadline date string
    - deadline_date: parsed datetime or None
    - posted_date: when job was posted (if available)
    - source: 'ki_varbi'
    - description: brief description if available
    """
    jobs = []

    try:
        logger.info(f"Fetching {BASE_URL}")
        response = requests.get(BASE_URL, timeout=30, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; KI-Job-Scraper/1.0)'
        })
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'lxml')

        # Find all job links - Varbi uses /what:job/jobID:XXXXX/ format
        job_links = soup.find_all('a', href=re.compile(r'jobID[=:]\d+'))

        seen_ids = set()

        for link in job_links:
            href = link.get('href', '')
            job_id = extract_job_id(href)

            if not job_id or job_id in seen_ids:
                continue

            seen_ids.add(job_id)

            title = link.get_text(strip=True)
            if not title or len(title) < 5:
                # Try to get title from parent
                parent = link.parent
                if parent:
                    title = parent.get_text(strip=True)
                if not title or len(title) < 5:
                    continue

            # Build full URL
            if href.startswith('/'):
                url = f"https://ki.varbi.com{href}"
            elif not href.startswith('http'):
                url = f"https://ki.varbi.com/{href}"
            else:
                url = href

            # Try to find deadline in surrounding elements
            deadline, deadline_date = find_deadline(link)

            jobs.append({
                'id': f"ki_varbi_{job_id}",
                'title': title[:200],  # Truncate overly long titles
                'url': url,
                'deadline': deadline,
                'deadline_date': deadline_date,
                'posted_date': None,
                'source': 'ki_varbi',
                'description': ''
            })

        logger.info(f"Found {len(jobs)} staff positions")
        return jobs

    except requests.RequestException as e:
        logger.error(f"Error fetching KI Varbi: {e}")
        return []
    except Exception as e:
        logger.error(f"Error parsing KI Varbi: {e}")
        return []


def extract_job_id(href: str) -> Optional[str]:
    """Extract job ID from Varbi URL"""
    match = re.search(r'jobID[=:](\d+)', href)
    if match:
        return match.group(1)
    return None


def find_deadline(element) -> tuple:
    """Try to find deadline date near an element"""
    deadline = None
    deadline_date = None

    # Check siblings and parent
    parent = element.parent
    for _ in range(5):
        if parent is None:
            break
        text = parent.get_text()
        deadline, deadline_date = parse_deadline_text(text)
        if deadline:
            break
        parent = parent.parent

    return deadline, deadline_date


def parse_deadline_text(text: str) -> tuple:
    """Parse deadline from text, return (string, datetime)"""
    patterns = [
        r'[Dd]eadline[:\s]+(\d{4}-\d{2}-\d{2})',
        r'[Dd]eadline[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
        r'[Aa]pply by[:\s]+([A-Z][a-z]+ \d{1,2},? \d{4})',
        r'[Ll]ast application date[:\s]+(\d{4}-\d{2}-\d{2})',
        r'[Ss]ista ansökningsdag[:\s]+(\d{4}-\d{2}-\d{2})',
        r'(\d{4}-\d{2}-\d{2})'
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            date_str = match.group(1)
            try:
                for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%B %d, %Y', '%B %d %Y']:
                    try:
                        deadline_date = datetime.strptime(date_str, fmt)
                        return date_str, deadline_date
                    except ValueError:
                        continue
            except Exception:
                pass
            return date_str, None

    return None, None
