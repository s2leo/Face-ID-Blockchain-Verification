"""
Social Profile Finder — Option B
=================================

Instagram, Facebook, and X/Twitter actively block reverse image crawlers.
Their images are served from CDN domains (cdninstagram.com, fbcdn.net) that
search engines cannot map back to a profile page.

This module works around that by:
  1. Extracting the most likely person name from existing search match titles
     (e.g. "Shruti Haasan" appears repeatedly in Pinterest/news match titles)
  2. Running targeted Google searches via SerpAPI:
       "Shruti Haasan" site:instagram.com
       "Shruti Haasan" site:facebook.com
       "Shruti Haasan" site:x.com OR site:twitter.com
       "Shruti Haasan" site:linkedin.com
  3. Returning those profile URLs as additional SearchMatch objects tagged
     with category="social" so they flow into the biometric verification step

This works for anyone whose name appears in public web content — celebrities,
professionals, academics, anyone with a news mention or Pinterest pin about them.

For truly private individuals (no name in any result), the function returns
an empty list gracefully.

Usage:
    from reverse_search.social_profile_finder import find_social_profiles
    extra = find_social_profiles(existing_search_response, api_key="...")
    # extra is a list of SearchMatch objects ready to append to the pipeline
"""

from __future__ import annotations

import os
import re
from collections import Counter
from typing import Optional

import requests
from dotenv import load_dotenv

from reverse_search.base import SearchMatch

load_dotenv()

SERPAPI_ENDPOINT = "https://serpapi.com/search.json"

# Social platforms to search for, in priority order
# Each entry: (site_query, platform_label)
SOCIAL_SITE_QUERIES: list[tuple[str, str]] = [
    ("site:instagram.com",          "Instagram"),
    ("site:facebook.com",           "Facebook"),
    ("site:x.com OR site:twitter.com", "Twitter/X"),
    ("site:linkedin.com",           "LinkedIn"),
    ("site:youtube.com",            "YouTube"),
    ("site:tiktok.com",             "TikTok"),
    ("site:reddit.com",             "Reddit"),
]

# Minimum times a name token cluster must appear across titles to be trusted
NAME_MIN_FREQUENCY = 2

# Maximum results to fetch per platform query
RESULTS_PER_PLATFORM = 5


def extract_candidate_name(titles: list[str]) -> Optional[str]:
    """
    Extract the most likely person name from a list of match titles.

    Strategy:
    - Tokenise each title into 2- and 3-word capitalised phrases
    - Count how often each phrase appears across all titles
    - Return the most frequent phrase that appears >= NAME_MIN_FREQUENCY times
    - Prefer 2-word names (First Last) over 3-word names

    Examples:
        "Shruti Haasan Goes Back To Her London Vacation" → "Shruti Haasan"
        "Beautiful adorable Shruti Hassan actress"       → "Shruti Hassan"
        "Pin on Shruti"                                  → (too short, skip)
    """
    phrase_counts: Counter = Counter()

    for title in titles:
        if not title:
            continue
        # Extract 2-word capitalised phrases (First Last style)
        two_word = re.findall(r'\b([A-Z][a-z]{1,})\s+([A-Z][a-z]{1,})\b', title)
        for first, last in two_word:
            # Skip common non-name words
            if first in ("The", "Pin", "How", "Here", "This", "That", "When",
                         "What", "Who", "From", "With", "For", "And", "Beautiful",
                         "Hot", "New", "Top", "Best", "All", "More"):
                continue
            phrase_counts[f"{first} {last}"] += 1

        # Extract 3-word capitalised phrases
        three_word = re.findall(
            r'\b([A-Z][a-z]{1,})\s+([A-Z][a-z]{1,})\s+([A-Z][a-z]{1,})\b', title
        )
        for a, b, c in three_word:
            phrase_counts[f"{a} {b} {c}"] += 1

    if not phrase_counts:
        return None

    # Prefer 2-word names that appear frequently
    two_word_candidates = [
        (name, count) for name, count in phrase_counts.items()
        if len(name.split()) == 2 and count >= NAME_MIN_FREQUENCY
    ]
    if two_word_candidates:
        return max(two_word_candidates, key=lambda x: x[1])[0]

    # Fall back to any phrase above threshold
    best = phrase_counts.most_common(1)[0]
    if best[1] >= NAME_MIN_FREQUENCY:
        return best[0]

    return None


def _google_search(query: str, api_key: str, num: int = 5) -> list[dict]:
    """Run a Google search via SerpAPI and return organic results."""
    try:
        resp = requests.get(
            SERPAPI_ENDPOINT,
            params={
                "engine": "google",
                "q": query,
                "api_key": api_key,
                "num": num,
                "hl": "en",
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("organic_results", [])
    except Exception:
        return []


def find_social_profiles(
    match_titles: list[str],
    api_key: Optional[str] = None,
    person_name: Optional[str] = None,
    platforms: Optional[list[str]] = None,
) -> tuple[Optional[str], list[SearchMatch]]:
    """
    Find social media profiles for the person identified in search results.

    Args:
        match_titles:  List of title strings from existing search matches.
        api_key:       SerpAPI key (falls back to SERPAPI_API_KEY env var).
        person_name:   Override name detection — use this name directly.
        platforms:     Limit to specific platforms e.g. ["Instagram", "Facebook"].
                       None = search all platforms in SOCIAL_SITE_QUERIES.

    Returns:
        (detected_name, list_of_SearchMatch)
        detected_name is None if no name could be extracted and none was provided.
    """
    key = api_key or os.getenv("SERPAPI_API_KEY", "")
    if not key:
        return None, []

    # Step 1: determine the person's name
    name = person_name or extract_candidate_name(match_titles)
    if not name:
        return None, []

    # Step 2: query each platform
    extra_matches: list[SearchMatch] = []
    seen_urls: set[str] = set()

    queries_to_run = [
        (site_q, label) for site_q, label in SOCIAL_SITE_QUERIES
        if platforms is None or label in platforms
    ]

    for site_query, platform_label in queries_to_run:
        full_query = f'"{name}" {site_query}'
        results = _google_search(full_query, key, num=RESULTS_PER_PLATFORM)

        for item in results:
            url = item.get("link", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            extra_matches.append(
                SearchMatch(
                    url=url,
                    title=item.get("title", ""),
                    snippet=item.get("snippet", ""),
                    domain=item.get("displayed_link", ""),
                    thumbnail=item.get("thumbnail", ""),
                    match_type="profile_search",
                    # Mark as high-confidence social — we searched specifically
                    # for this person's name on this platform
                )
            )

    return name, extra_matches
