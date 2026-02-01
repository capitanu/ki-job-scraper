"""Notification system using ntfy.sh"""

import logging
import requests
import unicodedata
from typing import Dict, List

logger = logging.getLogger(__name__)

NTFY_TOPIC = "andrada-ki-jobs"
NTFY_URL = f"https://ntfy.sh/{NTFY_TOPIC}"


def sanitize_header(text: str) -> str:
    """Sanitize text for HTTP headers (ASCII-safe)"""
    # Normalize unicode (e.g., en-dash to hyphen)
    text = unicodedata.normalize('NFKD', text)
    # Replace common problematic characters
    replacements = {
        '\u2013': '-',  # en-dash
        '\u2014': '-',  # em-dash
        '\u2018': "'",  # left single quote
        '\u2019': "'",  # right single quote
        '\u201c': '"',  # left double quote
        '\u201d': '"',  # right double quote
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    # Remove any remaining non-ASCII characters
    return text.encode('ascii', 'ignore').decode('ascii')


def send_notification(job: Dict, matched_keywords: List[str]) -> bool:
    """
    Send a push notification for a new job via ntfy.sh

    Args:
        job: Job dict with title, url, deadline, source
        matched_keywords: List of keywords that matched

    Returns:
        True if notification sent successfully
    """
    try:
        # Format the message
        job_title = sanitize_header(job['title'][:60])
        title = f"New KI Position: {job_title}"
        if len(job['title']) > 60:
            title += "..."

        # Build message body
        lines = []

        if job.get('deadline'):
            lines.append(f"Deadline: {job['deadline']}")

        # Source info
        source_names = {
            'ki_doktorand': 'KI Doctoral',
            'ki_varbi': 'KI Staff',
            'academic_positions': 'Academic Positions'
        }
        source = source_names.get(job.get('source'), job.get('source', 'Unknown'))
        lines.append(f"Source: {source}")

        # Keywords matched
        if matched_keywords:
            high_priority = ['organoid', 'ipsc', 'induced pluripotent', 'stem cell',
                           'neuroscience', 'neurodevelopmental', 'neural stem',
                           'brain organoid', 'single-cell', 'scrna-seq', 'spatial transcriptomics']
            high = [k for k in matched_keywords if k.lower() in high_priority]
            medium = [k for k in matched_keywords if k.lower() not in high_priority]

            if high:
                lines.append(f"High priority: {', '.join(high)}")
            if medium:
                lines.append(f"Medium priority: {', '.join(medium)}")

        message = "\n".join(lines)

        # Send via ntfy.sh
        response = requests.post(
            NTFY_URL,
            data=message.encode('utf-8'),
            headers={
                "Title": title,
                "Click": job['url'],
                "Tags": "briefcase,sweden",
                "Priority": "high" if any(k.lower() in ['organoid', 'ipsc', 'neuroscience'] for k in matched_keywords) else "default"
            },
            timeout=10
        )
        response.raise_for_status()

        logger.info(f"Notification sent for job: {job['id']}")
        return True

    except requests.RequestException as e:
        logger.error(f"Failed to send notification: {e}")
        return False
    except Exception as e:
        logger.error(f"Error sending notification: {e}")
        return False


def send_test_notification() -> bool:
    """Send a test notification to verify ntfy.sh is working"""
    try:
        response = requests.post(
            NTFY_URL,
            data="This is a test notification from your KI Job Scraper.\n\nIf you see this, notifications are working!",
            headers={
                "Title": "KI Job Scraper - Test",
                "Tags": "white_check_mark,test_tube",
                "Priority": "low"
            },
            timeout=10
        )
        response.raise_for_status()
        logger.info("Test notification sent successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to send test notification: {e}")
        return False


def send_summary_notification(new_count: int, total_matching: int) -> bool:
    """Send a daily summary notification"""
    try:
        if new_count == 0:
            message = f"No new matching positions today.\n\nTotal open matching positions: {total_matching}"
            title = "KI Jobs - Daily Check"
            priority = "low"
        else:
            message = f"Found {new_count} new matching position(s)!\n\nTotal open matching positions: {total_matching}"
            title = f"KI Jobs - {new_count} New Position(s)!"
            priority = "default"

        response = requests.post(
            NTFY_URL,
            data=message.encode('utf-8'),
            headers={
                "Title": title,
                "Tags": "clipboard",
                "Priority": priority
            },
            timeout=10
        )
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Failed to send summary notification: {e}")
        return False
