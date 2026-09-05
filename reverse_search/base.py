"""
Base data structures and provider interface for reverse image search.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import List, Optional
from urllib.parse import urlparse, unquote


# ---------------------------------------------------------------------------
# Tier 1 — Social media platforms (exact domain lookup)
# These are actual social/professional platforms where a person HAS a profile
# or posted content.  is_social = True, category = "social"
# ---------------------------------------------------------------------------

SOCIAL_PLATFORMS: dict[str, str] = {
    # Core social networks
    "linkedin.com": "LinkedIn",
    "twitter.com": "Twitter/X",
    "x.com": "Twitter/X",
    "instagram.com": "Instagram",
    "facebook.com": "Facebook",
    "fb.com": "Facebook",
    "threads.com": "Threads",
    "threads.net": "Threads",
    "reddit.com": "Reddit",
    "tiktok.com": "TikTok",
    "snapchat.com": "Snapchat",
    "youtube.com": "YouTube",
    "youtu.be": "YouTube",
    "twitch.tv": "Twitch",
    "discord.com": "Discord",
    "t.me": "Telegram",
    "telegram.me": "Telegram",
    "telegram.org": "Telegram",
    "whatsapp.com": "WhatsApp",
    # Professional networks
    "researchgate.net": "ResearchGate",
    "academia.edu": "Academia.edu",
    "xing.com": "XING",
    "glassdoor.com": "Glassdoor",
    "angel.co": "AngelList",
    "wellfound.com": "Wellfound",
    "crunchbase.com": "Crunchbase",
    "orcid.org": "ORCID",
    "semanticscholar.org": "Semantic Scholar",
    # Developer / tech platforms
    "github.com": "GitHub",
    "gitlab.com": "GitLab",
    "bitbucket.org": "Bitbucket",
    "stackoverflow.com": "StackOverflow",
    "stackexchange.com": "StackExchange",
    "dev.to": "Dev.to",
    "devpost.com": "Devpost",
    "hackerrank.com": "HackerRank",
    "leetcode.com": "LeetCode",
    "codepen.io": "CodePen",
    "replit.com": "Replit",
    "kaggle.com": "Kaggle",
    "huggingface.co": "HuggingFace",
    # Creative / portfolio
    "behance.net": "Behance",
    "dribbble.com": "Dribbble",
    "artstation.com": "ArtStation",
    "deviantart.com": "DeviantArt",
    "500px.com": "500px",
    "flickr.com": "Flickr",
    "unsplash.com": "Unsplash",
    "pinterest.com": "Pinterest",
    "tumblr.com": "Tumblr",
    # Blogging / content
    "medium.com": "Medium",
    "substack.com": "Substack",
    "wordpress.com": "WordPress",
    "blogger.com": "Blogger",
    "quora.com": "Quora",
    # Eastern European / Russian social
    "vk.com": "VK",
    "vkontakte.ru": "VK",
    "ok.ru": "Odnoklassniki",
    "odnoklassniki.ru": "Odnoklassniki",
    "mamba.ru": "Mamba",
    "my.mail.ru": "Mail.ru",
    # Asian social
    "weibo.com": "Weibo",
    "bilibili.com": "Bilibili",
    "zhihu.com": "Zhihu",
    "line.me": "LINE",
    # People / profile pages
    "about.me": "About.me",
    "linktr.ee": "Linktree",
    "linktree.com": "Linktree",
    "gravatar.com": "Gravatar",
    "bebee.com": "BeBee",
    "meetup.com": "Meetup",
    "speakerdeck.com": "SpeakerDeck",
    "slideshare.net": "SlideShare",
    # Third-party Twitter/X mirrors and viewers
    "sotwe.com": "Twitter/X",        # Twitter profile/post archive
    "muskviewer.com": "Twitter/X",   # Twitter viewer
    "nitter.net": "Twitter/X",       # Nitter (Twitter front-end)
    "nitter.it": "Twitter/X",
    "twstalker.com": "Twitter/X",
    # Instagram mirrors/viewers/story archives
    "storiesdb.ch": "Instagram",     # Instagram Stories archive
    "imginn.com": "Instagram",       # Instagram viewer
    "picuki.com": "Instagram",       # Instagram viewer
    "greatfon.com": "Instagram",     # Instagram viewer
    "pixwox.com": "Instagram",       # Instagram viewer
    "inflact.com": "Instagram",      # Instagram viewer
    "inssist.com": "Instagram",      # Instagram viewer
    # Facebook mirrors
    "mbasic.facebook.com": "Facebook",
    # Dating / social profiles
    "yazawaj.com": "Dating Profile",
    "aguea.net": "Social Profile",   # social aggregator
}


# ---------------------------------------------------------------------------
# Tier 2 — Web profile patterns (heuristic, URL-structure based)
# These are NOT social platforms but show a person's web presence:
# news articles about them, celeb databases, portfolio sites, etc.
# is_social = False, category = "web_profile"
# ---------------------------------------------------------------------------

# Domains that aggregate/host individual web profiles but aren't social nets
WEB_PROFILE_DOMAINS: dict[str, str] = {
    "imdb.com": "IMDb",
    "rotten tomatoes.com": "Rotten Tomatoes",
    "wikipedia.org": "Wikipedia",
    "wikimedia.org": "Wikipedia",
    "wikidata.org": "Wikidata",
    "fandom.com": "Fandom Wiki",
    "crunchyroll.com": "Crunchyroll",
    "last.fm": "Last.fm",
    "genius.com": "Genius",
    "allmusic.com": "AllMusic",
    "discogs.com": "Discogs",
    "rocketreach.co": "RocketReach",
    "spokeo.com": "Spokeo",
    "zoominfo.com": "ZoomInfo",
    "pipl.com": "Pipl",
    "intelius.com": "Intelius",
    "manta.com": "Manta",
    "yellowpages.com": "YellowPages",
    "whitepages.com": "WhitePages",
    "superprof.com": "Superprof",
    "superprof.co.uk": "Superprof",
    "superprof.com.my": "Superprof",
    "pangea.app": "Pangea",
    "toptal.com": "Toptal",
    "upwork.com": "Upwork",
    "fiverr.com": "Fiverr",
}

# URL path patterns that signal a person's profile page on an arbitrary site.
# Checked against the full URL path (lowercased, URL-decoded).
# Each tuple: (regex_pattern, inferred_category_label)
_WEB_PROFILE_PATH_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"/@[a-z0-9_.]{2,}"),                   "Profile"),   # /@username
    (re.compile(r"/profile/[a-z0-9_.\-]{2,}"),          "Profile"),   # /profile/name
    (re.compile(r"/in/[a-z0-9_.\-]{2,}"),               "Profile"),   # LinkedIn-style /in/name
    (re.compile(r"/user/[a-z0-9_.\-]{2,}"),             "Profile"),   # /user/name
    (re.compile(r"/u/[a-z0-9_.\-]{2,}"),                "Profile"),   # /u/name
    (re.compile(r"/people/[a-z0-9_.\-]{2,}"),           "Profile"),   # /people/name
    (re.compile(r"/author/[a-z0-9_.\-]{2,}"),           "Profile"),   # /author/name
    (re.compile(r"/member/[a-z0-9_.\-]{2,}"),           "Profile"),   # /member/name
    (re.compile(r"/faculty/[a-z0-9_.\-]{2,}"),          "Faculty"),   # /faculty/name
    (re.compile(r"/staff/[a-z0-9_.\-]{2,}"),            "Staff"),     # /staff/name
    (re.compile(r"/team/[a-z0-9_.\-]{2,}"),             "Team Page"), # /team/name
    (re.compile(r"/alumni/[a-z0-9_.\-]{2,}"),           "Alumni"),    # /alumni/name
    (re.compile(r"/speaker/[a-z0-9_.\-]{2,}"),          "Speaker"),   # /speaker/name
    (re.compile(r"/freelancer[s]?/[a-z0-9_.\-/]{2,}"),  "Freelancer"),
]

# URL keywords that indicate the page is *about* or *mentions* a social platform
# (e.g. a news article reporting on someone's Instagram post).
# These get category="social_mention" — separate from true social profiles.
_SOCIAL_MENTION_KEYWORDS: dict[str, str] = {
    "instagram": "Instagram (mention)",
    "facebook": "Facebook (mention)",
    "twitter": "Twitter/X (mention)",
    "tiktok": "TikTok (mention)",
    "youtube": "YouTube (mention)",
    "linkedin": "LinkedIn (mention)",
    "snapchat": "Snapchat (mention)",
    "whatsapp": "WhatsApp (mention)",
}

# Domains to completely filter out — not useful results at all
JUNK_DOMAINS: set[str] = {
    "yandex.com",    # yandex internal image search links
    "yandex.ru",
    "yandex.net",
    "google.com",    # google internal links
    "googleapis.com",
    "gstatic.com",
    "googleusercontent.com",
}


def _normalise_host(url: str) -> str:
    """Extract lowercase bare hostname from URL, stripping www."""
    try:
        host = urlparse(url).hostname or ""
        return host.lower().removeprefix("www.")
    except Exception:
        return ""


def detect_platform(url: str) -> Optional[str]:
    """
    Tier 1: Return platform name if the URL is FROM a known social/professional
    platform (exact domain or subdomain match).  Returns None otherwise.
    """
    host = _normalise_host(url)
    if not host:
        return None
    if host in SOCIAL_PLATFORMS:
        return SOCIAL_PLATFORMS[host]
    # Subdomain match — e.g. in.linkedin.com, m.facebook.com, uk.pinterest.com
    for domain, name in SOCIAL_PLATFORMS.items():
        if host.endswith("." + domain):
            return name
    return None


def detect_web_profile(url: str) -> Optional[str]:
    """
    Tier 2a: Return a label if the URL points to a known web-profile aggregator
    domain (IMDb, Wikipedia, RocketReach, etc.) or matches a profile-style URL
    path pattern on any domain.  Returns None if neither applies.
    """
    host = _normalise_host(url)
    if not host:
        return None

    # Known web-profile domains
    if host in WEB_PROFILE_DOMAINS:
        return WEB_PROFILE_DOMAINS[host]
    for domain, name in WEB_PROFILE_DOMAINS.items():
        if host.endswith("." + domain):
            return name

    # Path-pattern heuristic on any domain
    try:
        path = unquote(urlparse(url).path).lower()
        for pattern, label in _WEB_PROFILE_PATH_PATTERNS:
            if pattern.search(path):
                return label
    except Exception:
        pass

    return None


def detect_social_mention(url: str, title: str = "") -> Optional[str]:
    """
    Tier 2b: Return a label if the URL or title *mentions* a social platform
    by name — i.e. a news article or blog post ABOUT someone's social activity.
    This is separate from actually being on that platform.
    """
    combined = (url + " " + title).lower()
    for keyword, label in _SOCIAL_MENTION_KEYWORDS.items():
        if keyword in combined:
            return label
    return None


def is_social_url(url: str) -> bool:
    """True if the URL is directly FROM a known social/professional platform."""
    return detect_platform(url) is not None


def is_junk_url(url: str) -> bool:
    """True if the URL is an internal search engine link with no value."""
    host = _normalise_host(url)
    return host in JUNK_DOMAINS


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class SearchMatch:
    """A single match returned by a reverse image search provider."""

    url: str
    title: str = ""
    domain: str = ""
    snippet: str = ""
    thumbnail: str = ""

    # --- Classification (set automatically in __post_init__) ---
    platform: Optional[str] = None   # e.g. "LinkedIn", "Instagram"
    category: str = "web"
    # category values:
    #   "social"          — URL is directly FROM a social/professional platform
    #   "social_mention"  — news/blog page that mentions a social platform
    #   "web_profile"     — profile page on any other site (IMDb, uni page, etc.)
    #   "web"             — general web page, no profile signal detected
    is_social: bool = False           # True only for category == "social"

    match_type: str = "visual"        # visual | exact | partial | similar
    confidence: Optional[float] = None

    # Biometric verification (filled by BiometricVerifier)
    biometric_similarity: Optional[float] = None
    biometrically_verified: bool = False
    verification_status: str = "unverified"

    def __post_init__(self):
        # 1. Auto-fill domain from URL
        if not self.domain:
            try:
                self.domain = urlparse(self.url).hostname or ""
                self.domain = self.domain.lower().removeprefix("www.")
            except Exception:
                pass

        # 2. Tier 1 — exact social platform match
        if not self.platform:
            self.platform = detect_platform(self.url)

        if self.platform:
            self.category = "social"
            self.is_social = True
            return

        # 3. Tier 2a — known web-profile domain / path pattern
        web_profile = detect_web_profile(self.url)
        if web_profile:
            self.platform = web_profile
            self.category = "web_profile"
            self.is_social = False
            return

        # 4. Tier 2b — social platform mention in URL/title
        mention = detect_social_mention(self.url, self.title)
        if mention:
            self.platform = mention
            self.category = "social_mention"
            self.is_social = False
            return

        # 5. Nothing matched
        self.category = "web"
        self.is_social = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SearchResponse:
    """Normalized response from any reverse image search provider."""

    provider: str
    query_image: str
    matches: List[SearchMatch] = field(default_factory=list)
    raw_response: Optional[dict] = None
    error: Optional[str] = None
    search_url: str = ""

    def __post_init__(self):
        # Filter out junk internal search-engine URLs (yandex.com/images/..., etc.)
        self.matches = [m for m in self.matches if not is_junk_url(m.url)]

    # --- Category-separated views ---

    @property
    def social_matches(self) -> List[SearchMatch]:
        """Matches directly FROM a social/professional platform."""
        return [m for m in self.matches if m.category == "social"]

    @property
    def social_mention_matches(self) -> List[SearchMatch]:
        """News/blog pages that mention a social platform."""
        return [m for m in self.matches if m.category == "social_mention"]

    @property
    def web_profile_matches(self) -> List[SearchMatch]:
        """Profile pages on non-social sites (IMDb, uni pages, etc.)."""
        return [m for m in self.matches if m.category == "web_profile"]

    @property
    def all_profile_matches(self) -> List[SearchMatch]:
        """Everything with a person-profile signal: social + web_profile."""
        return [m for m in self.matches if m.category in ("social", "web_profile")]

    # --- Biometric views ---

    @property
    def verified_matches(self) -> List[SearchMatch]:
        return [m for m in self.matches if m.biometrically_verified]

    @property
    def verified_social_matches(self) -> List[SearchMatch]:
        return [m for m in self.matches if m.category == "social" and m.biometrically_verified]

    # --- Flags ---

    @property
    def has_social_match(self) -> bool:
        return len(self.social_matches) > 0

    @property
    def has_verified_match(self) -> bool:
        return len(self.verified_matches) > 0

    @property
    def match_count(self) -> int:
        return len(self.matches)

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "query_image": self.query_image,
            "match_count": self.match_count,
            "social_match_count": len(self.social_matches),
            "social_mention_count": len(self.social_mention_matches),
            "web_profile_count": len(self.web_profile_matches),
            "has_social_match": self.has_social_match,
            "verified_match_count": len(self.verified_matches),
            "has_verified_match": self.has_verified_match,
            "search_url": self.search_url,
            "error": self.error,
            "matches": [m.to_dict() for m in self.matches],
        }


# ---------------------------------------------------------------------------
# Base provider
# ---------------------------------------------------------------------------

class BaseProvider:
    """
    Abstract base for reverse image search providers.
    Subclasses must implement _execute_search().
    """

    name: str = "base"

    def search(self, image_path: str, **kwargs) -> SearchResponse:
        """
        Public entry point. Handles common pre/post processing
        and delegates to _execute_search().
        """
        try:
            return self._execute_search(image_path, **kwargs)
        except Exception as exc:
            return SearchResponse(
                provider=self.name,
                query_image=image_path,
                error=f"{type(exc).__name__}: {exc}",
            )

    def _execute_search(self, image_path: str, **kwargs) -> SearchResponse:
        raise NotImplementedError("Subclasses must implement _execute_search()")



# ---------------------------------------------------------------------------
# Multi-provider merge utility
# ---------------------------------------------------------------------------

def merge_responses(responses: list["SearchResponse"], primary_provider: str = "merged") -> "SearchResponse":
    """
    Merge results from multiple providers into a single SearchResponse.
    Deduplicates by URL (first occurrence wins — preserves ordering of
    higher-confidence providers listed first in `responses`).
    Junk URLs are filtered automatically via SearchResponse.__post_init__.
    """
    seen_urls: set[str] = set()
    merged: list[SearchMatch] = []

    for resp in responses:
        if resp.error or not resp.matches:
            continue
        for match in resp.matches:
            if match.url not in seen_urls:
                seen_urls.add(match.url)
                merged.append(match)

    # Build a combined search_url string from all providers
    search_urls = " | ".join(
        r.search_url for r in responses if r.search_url and not r.error
    )

    query_image = responses[0].query_image if responses else ""

    # Use a temporary list so SearchResponse.__post_init__ runs junk filtering
    result = SearchResponse(
        provider=primary_provider,
        query_image=query_image,
        matches=merged,
        search_url=search_urls,
    )
    return result
