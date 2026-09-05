"""
Base data structures and provider interface for reverse image search.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import List, Optional
from urllib.parse import urlparse


# ---------------------------------------------------------------------------
# Social media platform detection
# ---------------------------------------------------------------------------

SOCIAL_PLATFORMS = {
    "linkedin.com": "LinkedIn",
    "twitter.com": "Twitter/X",
    "x.com": "Twitter/X",
    "instagram.com": "Instagram",
    "facebook.com": "Facebook",
    "fb.com": "Facebook",
    "github.com": "GitHub",
    "reddit.com": "Reddit",
    "medium.com": "Medium",
    "youtube.com": "YouTube",
    "tiktok.com": "TikTok",
    "pinterest.com": "Pinterest",
    "tumblr.com": "Tumblr",
    "quora.com": "Quora",
    "stackoverflow.com": "StackOverflow",
    "dev.to": "Dev.to",
    "vk.com": "VK",
    "t.me": "Telegram",
    "discord.com": "Discord",
    "twitch.tv": "Twitch",
    "behance.net": "Behance",
    "dribbble.com": "Dribbble",
    "flickr.com": "Flickr",
    "500px.com": "500px",
}


def detect_platform(url: str) -> Optional[str]:
    """
    Return human-readable platform name if the URL belongs to a known
    social / professional network, else None.
    """
    try:
        host = urlparse(url).hostname or ""
        host = host.lower().removeprefix("www.")
        # Direct match
        if host in SOCIAL_PLATFORMS:
            return SOCIAL_PLATFORMS[host]
        # Subdomain match (e.g. m.facebook.com)
        for domain, name in SOCIAL_PLATFORMS.items():
            if host.endswith("." + domain):
                return name
    except Exception:
        pass
    return None


def is_social_url(url: str) -> bool:
    """Return True if the URL is from a known social media platform."""
    return detect_platform(url) is not None


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
    platform: Optional[str] = None  # e.g. "LinkedIn", "GitHub"
    is_social: bool = False
    match_type: str = "visual"      # visual | exact | partial | similar
    confidence: Optional[float] = None  # 0.0 – 1.0 if provider gives one
    biometric_similarity: Optional[float] = None  # Cosine similarity score (0.0 – 1.0)
    biometrically_verified: bool = False  # True if similarity >= threshold
    verification_status: str = "unverified"  # verified | lookalike | no_face_found | fetch_error | unverified

    def __post_init__(self):
        # Auto-detect domain and social platform from URL
        if not self.domain:
            try:
                self.domain = urlparse(self.url).hostname or ""
                self.domain = self.domain.lower().removeprefix("www.")
            except Exception:
                pass
        if not self.platform:
            self.platform = detect_platform(self.url)
        self.is_social = self.platform is not None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SearchResponse:
    """
    Normalized response from any reverse image search provider.
    """

    provider: str
    query_image: str
    matches: List[SearchMatch] = field(default_factory=list)
    raw_response: Optional[dict] = None
    error: Optional[str] = None
    search_url: str = ""  # The URL the provider used (useful for debugging)

    @property
    def social_matches(self) -> List[SearchMatch]:
        """Return only matches from known social media platforms."""
        return [m for m in self.matches if m.is_social]

    @property
    def verified_matches(self) -> List[SearchMatch]:
        """Return matches that passed biometric verification."""
        return [m for m in self.matches if m.biometrically_verified]

    @property
    def verified_social_matches(self) -> List[SearchMatch]:
        """Return social media matches that passed biometric verification."""
        return [m for m in self.matches if m.is_social and m.biometrically_verified]

    @property
    def has_social_match(self) -> bool:
        """True if at least one social media match was found (Hackathon Req #2)."""
        return len(self.social_matches) > 0

    @property
    def has_verified_match(self) -> bool:
        """True if at least one match was biometrically verified."""
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

