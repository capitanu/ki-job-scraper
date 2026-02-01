"""Scraper for Academic Positions - KI PhD listings"""

import logging
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from datetime import datetime
import re

logger = logging.getLogger(__name__)

BASE_URL = "https://academicpositions.com/jobs/employer/karolinska-institutet/position/phd"


def scrape() -> List[Dict]:
    """
    Scrape PhD positions from academicpositions.com for KI

    Returns list of job dicts with keys:
    - id: unique identifier
    - title: job title
    - url: direct link to job posting
    - deadline: deadline date string
    - deadline_date: parsed datetime or None
    - posted_date: when job was posted (if available)
    - source: 'academic_positions'
    - description: brief description if available
    """
    jobs = []

    try:
        logger.info(f"Fetching {BASE_URL}")
        response = requests.get(BASE_URL, timeout=30, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'lxml')

        # Academic Positions uses job cards/listings
        # Look for job listing containers
        job_cards = soup.select('article, .job-card, .job-listing, .job-item, [class*="JobCard"], [class*="job-card"]')

        if not job_cards:
            # Try finding links to job pages
            job_links = soup.find_all('a', href=re.compile(r'/jobs/\d+'))

            seen_ids = set()
            for link in job_links:
                href = link.get('href', '')
                job_id = extract_job_id(href)

                if not job_id or job_id in seen_ids:
                    continue

                seen_ids.add(job_id)

                title = link.get_text(strip=True)
                if not title or len(title) < 5:
                    continue

                # Build full URL
                if href.startswith('/'):
                    url = f"https://academicpositions.com{href}"
                else:
                    url = href

                deadline, deadline_date = find_deadline(link)

                jobs.append({
                    'id': f"academic_positions_{job_id}",
                    'title': title,
                    'url': url,
                    'deadline': deadline,
                    'deadline_date': deadline_date,
                    'posted_date': None,
                    'source': 'academic_positions',
                    'description': ''
                })
        else:
            for card in job_cards:
                job_data = parse_job_card(card)
                if job_data:
                    jobs.append(job_data)

        # Deduplicate
        seen_ids = set()
        unique_jobs = []
        for job in jobs:
            if job['id'] not in seen_ids:
                seen_ids.add(job['id'])
                unique_jobs.append(job)

        logger.info(f"Found {len(unique_jobs)} positions on Academic Positions")
        return unique_jobs

    except requests.RequestException as e:
        logger.error(f"Error fetching Academic Positions: {e}")
        return []
    except Exception as e:
        logger.error(f"Error parsing Academic Positions: {e}")
        return []


def extract_job_id(href: str) -> Optional[str]:
    """Extract job ID from URL"""
    # Pattern: /jobs/123456 or /job/123456
    match = re.search(r'/jobs?/(\d+)', href)
    if match:
        return match.group(1)

    # Try slug-based ID
    match = re.search(r'/jobs?/([a-z0-9-]+)', href)
    if match:
        return match.group(1)

    return None


def find_deadline(element) -> tuple:
    """Try to find deadline date near an element"""
    deadline = None
    deadline_date = None

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
    """Parse deadline from text"""
    patterns = [
        r'[Dd]eadline[:\s]+(\d{4}-\d{2}-\d{2})',
        r'[Dd]eadline[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
        r'[Aa]pply by[:\s]+([A-Z][a-z]+ \d{1,2},? \d{4})',
        r'[Aa]pplication deadline[:\s]+([A-Z][a-z]+ \d{1,2},? \d{4})',
        r'[Cc]losing[:\s]+(\d{4}-\d{2}-\d{2})',
        r'[Ee]xpires?[:\s]+([A-Z][a-z]+ \d{1,2},? \d{4})',
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            date_str = match.group(1)
            try:
                for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%B %d, %Y', '%B %d %Y', '%b %d, %Y']:
                    try:
                        deadline_date = datetime.strptime(date_str, fmt)
                        return date_str, deadline_date
                    except ValueError:
                        continue
            except Exception:
                pass
            return date_str, None

    return None, None


def parse_job_card(card) -> Optional[Dict]:
    """Parse a job card element"""
    # Find the main link
    link = card.find('a', href=re.compile(r'/jobs?/'))
    if not link:
        link = card.find('a', href=True)

    if not link:
        return None

    href = link.get('href', '')
    job_id = extract_job_id(href)

    if not job_id:
        # Generate ID from href hash
        import hashlib
        job_id = hashlib.md5(href.encode()).hexdigest()[:10]

    # Get title
    title_elem = card.find(['h2', 'h3', 'h4', '.title', '[class*="title"]'])
    if title_elem:
        title = title_elem.get_text(strip=True)
    else:
        title = link.get_text(strip=True)

    if not title or len(title) < 5:
        return None

    # Build URL
    if href.startswith('/'):
        url = f"https://academicpositions.com{href}"
    elif not href.startswith('http'):
        url = f"https://academicpositions.com/{href}"
    else:
        url = href

    # Find deadline
    deadline, deadline_date = parse_deadline_text(card.get_text())

    # Try to find description
    desc_elem = card.find(['p', '.description', '[class*="description"]'])
    description = desc_elem.get_text(strip=True)[:200] if desc_elem else ''

    return {
        'id': f"academic_positions_{job_id}",
        'title': title,
        'url': url,
        'deadline': deadline,
        'deadline_date': deadline_date,
        'posted_date': None,
        'source': 'academic_positions',
        'description': description
    }
