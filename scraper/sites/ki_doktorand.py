"""Scraper for KI Doctoral positions (kidoktorand.varbi.com)"""

import logging
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from datetime import datetime
import re

logger = logging.getLogger(__name__)

BASE_URL = "https://kidoktorand.varbi.com/en/"


def scrape() -> List[Dict]:
    """
    Scrape doctoral positions from kidoktorand.varbi.com

    Returns list of job dicts with keys:
    - id: unique identifier
    - title: job title
    - url: direct link to job posting
    - deadline: deadline date string
    - deadline_date: parsed datetime or None
    - posted_date: when job was posted (if available)
    - source: 'ki_doktorand'
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

        # Varbi sites typically list jobs in a container with job cards
        # Look for common patterns in Varbi job listings
        job_listings = soup.select('.job-listing, .vacancy, article.job, .list-item, tr.job-row, .job-item, a[href*="/what:job/"]')

        # If no structured elements found, try to find links to job postings
        if not job_listings:
            # Varbi URLs typically have format /what:job/jobID:XXXXX/
            job_links = soup.find_all('a', href=re.compile(r'/what:job/jobID:\d+'))
            if not job_links:
                # Try alternative patterns
                job_links = soup.find_all('a', href=re.compile(r'jobID[=:]\d+'))

            for link in job_links:
                job_id = extract_job_id(link.get('href', ''))
                if not job_id:
                    continue

                title = link.get_text(strip=True)
                if not title:
                    continue

                # Build full URL
                href = link.get('href', '')
                if href.startswith('/'):
                    url = f"https://kidoktorand.varbi.com{href}"
                elif not href.startswith('http'):
                    url = f"https://kidoktorand.varbi.com/{href}"
                else:
                    url = href

                jobs.append({
                    'id': f"ki_doktorand_{job_id}",
                    'title': title,
                    'url': url,
                    'deadline': None,
                    'deadline_date': None,
                    'posted_date': None,
                    'source': 'ki_doktorand',
                    'description': ''
                })
        else:
            for listing in job_listings:
                job_data = parse_listing(listing)
                if job_data:
                    jobs.append(job_data)

        # Deduplicate by ID
        seen_ids = set()
        unique_jobs = []
        for job in jobs:
            if job['id'] not in seen_ids:
                seen_ids.add(job['id'])
                unique_jobs.append(job)

        # Fetch deadlines from detail pages
        logger.info(f"Found {len(unique_jobs)} doctoral positions, fetching deadlines...")
        for job in unique_jobs:
            deadline, deadline_date = fetch_job_deadline(job['url'])
            if deadline:
                job['deadline'] = deadline
                job['deadline_date'] = deadline_date

        return unique_jobs

    except requests.RequestException as e:
        logger.error(f"Error fetching KI Doktorand: {e}")
        return []
    except Exception as e:
        logger.error(f"Error parsing KI Doktorand: {e}")
        return []


def extract_job_id(href: str) -> Optional[str]:
    """Extract job ID from Varbi URL"""
    # Pattern: jobID:12345 or jobID=12345
    match = re.search(r'jobID[=:](\d+)', href)
    if match:
        return match.group(1)
    return None


def fetch_job_deadline(url: str) -> tuple:
    """Fetch job detail page to get the deadline"""
    try:
        response = requests.get(url, timeout=15, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; KI-Job-Scraper/1.0)'
        })
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')
        text = soup.get_text()

        # Search for date after "Last application date" (with possible whitespace/newlines)
        match = re.search(
            r'Last application date[\s:]*(\d{1,2}[\./-][A-Za-z]{3}[\./-]\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2}[\./-]\d{1,2}[\./-]\d{4})',
            text,
            re.IGNORECASE
        )
        if match:
            date_str = match.group(1)
            # Try parsing various formats
            for fmt in ['%d.%b.%Y', '%d-%b-%Y', '%Y-%m-%d', '%d/%m/%Y', '%d.%m.%Y']:
                try:
                    deadline_date = datetime.strptime(date_str, fmt)
                    return date_str, deadline_date
                except ValueError:
                    continue
            return date_str, None
        return None, None
    except Exception as e:
        logger.debug(f"Could not fetch deadline from {url}: {e}")
        return None, None


def find_deadline(element) -> tuple:
    """Try to find deadline date near an element"""
    deadline = None
    deadline_date = None

    # Search in parent elements
    parent = element.parent
    for _ in range(5):  # Look up to 5 levels
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
    # Common patterns: "Deadline: 2024-03-15", "Apply by March 15, 2024"
    patterns = [
        r'[Dd]eadline[:\s]+(\d{4}-\d{2}-\d{2})',
        r'[Dd]eadline[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
        r'[Aa]pply by[:\s]+([A-Z][a-z]+ \d{1,2},? \d{4})',
        r'[Ll]ast application date[:\s]+(\d{4}-\d{2}-\d{2})',
        r'(\d{4}-\d{2}-\d{2})'
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            date_str = match.group(1)
            try:
                # Try different date formats
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


def parse_listing(listing) -> Optional[Dict]:
    """Parse a job listing element into a job dict"""
    # Try to find job link
    link = listing.find('a', href=True)
    if not link:
        link = listing if listing.name == 'a' else None

    if not link:
        return None

    href = link.get('href', '')
    job_id = extract_job_id(href)

    if not job_id:
        return None

    title = link.get_text(strip=True)

    # Build URL
    if href.startswith('/'):
        url = f"https://kidoktorand.varbi.com{href}"
    elif not href.startswith('http'):
        url = f"https://kidoktorand.varbi.com/{href}"
    else:
        url = href

    # Find deadline
    deadline, deadline_date = parse_deadline_text(listing.get_text())

    return {
        'id': f"ki_doktorand_{job_id}",
        'title': title,
        'url': url,
        'deadline': deadline,
        'deadline_date': deadline_date,
        'posted_date': None,
        'source': 'ki_doktorand',
        'description': ''
    }
