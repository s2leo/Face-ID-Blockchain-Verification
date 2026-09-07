"""
SerpApi reverse image search provider.

Improvements applied:
  #1 — Two-engine strategy: google_lens (visual matches) + google_reverse_image
       (organic/news results). Both results are merged before returning.
  #4 — google_lens call includes no_cache=true, hl=en, gl=us for freshest
       English/US results (better social media coverage for Indian profiles).
  #7 — imgbb added as third upload fallback (freeimage.host → 0x0.st → imgbb).
  #9 — Uploaded image URL is cached by the crop file's MD5 hash so multi-
       provider runs (serpapi + yandex) only upload once.

Docs:
  https://serpapi.com/google-lens-api
  https://serpapi.com/google-reverse-image
Free: 100 searches/month (no credit card required)
"""

from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

from reverse_search.base import BaseProvider, SearchMatch, SearchResponse

load_dotenv()

SERPAPI_ENDPOINT = "https://serpapi.com/search.json"

# --- #9: in-process URL cache keyed by file MD5 ---
_upload_cache: dict[str, str] = {}


def _file_md5(file_path: Path) -> str:
    h = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Upload helpers
# ---------------------------------------------------------------------------

def _upload_image_to_freeimage(file_path: Path) -> str:
    with open(file_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode("utf-8")
    resp = requests.post(
        "https://freeimage.host/api/1/upload",
        data={
            "key": "6d207e02198a847aa98d0a2a901485a5",
            "action": "upload",
            "source": image_b64,
            "format": "json",
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("status_code") == 200:
        return data["image"]["url"]
    raise RuntimeError(f"freeimage.host upload failed: {data}")


def _upload_image_to_0x0(file_path: Path) -> str:
    with open(file_path, "rb") as f:
        resp = requests.post(
            "https://0x0.st",
            files={"file": (file_path.name, f)},
            timeout=30,
        )
    if resp.status_code == 200:
        url = resp.text.strip()
        if url.startswith("http"):
            return url
    raise RuntimeError(f"0x0.st upload failed (status {resp.status_code})")


def _upload_image_to_imgbb(file_path: Path) -> str:
    """#7: imgbb as third fallback — free tier, no API key needed for public uploads."""
    with open(file_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode("utf-8")
    resp = requests.post(
        "https://api.imgbb.com/1/upload",
        data={
            "key": "3e45a9cde06f1f41e2e6c3b9f0b1e5d7",
            "image": image_b64,
        },
        timeout=30,
    )
    if resp.status_code == 200:
        data = resp.json()
        if data.get("success"):
            return data["data"]["url"]
    raise RuntimeError(f"imgbb upload failed (status {resp.status_code})")


def upload_local_image(file_path: Path) -> str:
    """
    Upload a local image and return a public URL.
    #9: result is cached by file MD5 — safe to call multiple times per session.
    #7: fallback chain: freeimage.host → 0x0.st → imgbb
    """
    md5 = _file_md5(file_path)
    if md5 in _upload_cache:
        return _upload_cache[md5]

    errors: list[str] = []

    for fn, name in [
        (_upload_image_to_freeimage, "freeimage.host"),
        (_upload_image_to_0x0,       "0x0.st"),
        (_upload_image_to_imgbb,     "imgbb"),        # #7
    ]:
        try:
            url = fn(file_path)
            _upload_cache[md5] = url               # #9: cache for reuse
            return url
        except Exception as e:
            errors.append(f"{name}: {e}")

    raise RuntimeError(
        "Failed to upload image to any hosting service:\n"
        + "\n".join(f"  - {e}" for e in errors)
        + "\n\nAlternative: pass a public image URL instead of a local file."
    )


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------

class SerpApiLensProvider(BaseProvider):
    """
    Google Lens + Google Reverse Image via SerpApi.
    #1: Runs both engines and merges results for maximum coverage.
    """

    name = "serpapi_google_lens"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("SERPAPI_API_KEY", "")

    def _execute_search(self, image_path: str, **kwargs) -> SearchResponse:
        if not self.api_key:
            return SearchResponse(
                provider=self.name,
                query_image=image_path,
                error=(
                    "SERPAPI_API_KEY is not set. "
                    "Get one free at https://serpapi.com/users/sign_up "
                    "and add it to your .env file."
                ),
            )

        # Resolve to a public URL
        if image_path.startswith(("http://", "https://")):
            image_url = image_path
        else:
            file_path = Path(image_path).expanduser().resolve()
            if not file_path.exists():
                return SearchResponse(
                    provider=self.name,
                    query_image=image_path,
                    error=f"Image file not found: {file_path}",
                )
            try:
                image_url = upload_local_image(file_path)
            except RuntimeError as e:
                return SearchResponse(provider=self.name, query_image=image_path, error=str(e))

        # --- #1 + #4: Engine 1 — google_lens (visual matches, KG, text results) ---
        lens_params = {
            "engine":    "google_lens",
            "api_key":   self.api_key,
            "url":       image_url,
            "no_cache":  "true",   # #4: always fresh
            "hl":        "en",     # #4: English results
            "gl":        "us",     # #4: US locale — better social media coverage
        }
        try:
            lens_resp = requests.get(SERPAPI_ENDPOINT, params=lens_params, timeout=90)
            lens_resp.raise_for_status()
            lens_data = lens_resp.json()
        except Exception as e:
            lens_data = {}

        # --- #1: Engine 2 — google_reverse_image (organic results, news, inline images) ---
        rev_params = {
            "engine":            "google_reverse_image",
            "api_key":           self.api_key,
            "image_url":         image_url,
            "no_cache":          "true",   # #4
            "hl":                "en",     # #4
            "gl":                "us",     # #4
        }
        try:
            rev_resp = requests.get(SERPAPI_ENDPOINT, params=rev_params, timeout=90)
            rev_resp.raise_for_status()
            rev_data = rev_resp.json()
        except Exception as e:
            rev_data = {}

        return self._parse_response(image_path, lens_data, rev_data, image_url=image_url)

    def _parse_response(
        self,
        query_image: str,
        lens_data: dict,
        rev_data: dict,
        image_url: str = "",
    ) -> SearchResponse:
        matches: list[SearchMatch] = []

        # ── Google Lens results ──────────────────────────────────────────────

        # Visual matches
        for item in lens_data.get("visual_matches", []):
            if item.get("link"):
                matches.append(SearchMatch(
                    url=item["link"],
                    title=item.get("title", ""),
                    domain=item.get("source", ""),
                    snippet=item.get("snippet", ""),
                    thumbnail=item.get("thumbnail", ""),
                    match_type="visual",
                ))

        # Inline images (lens)
        for item in lens_data.get("inline_images", []):
            link = item.get("link", "") or item.get("source", "")
            if link:
                matches.append(SearchMatch(
                    url=link,
                    title=item.get("title", ""),
                    thumbnail=item.get("thumbnail", ""),
                    match_type="visual",
                ))

        # Knowledge graph (lens) — may contain social profile links
        kg = lens_data.get("knowledge_graph", [])
        if isinstance(kg, dict):
            kg = [kg]
        for item in kg:
            link = item.get("link", "") or item.get("website", "")
            if link:
                matches.append(SearchMatch(
                    url=link,
                    title=item.get("title", ""),
                    snippet=item.get("subtitle", ""),
                    match_type="exact",
                ))
            for profile in item.get("profiles", []):
                if profile.get("link"):
                    matches.append(SearchMatch(
                        url=profile["link"],
                        title=profile.get("name", ""),
                        snippet=f"Knowledge Graph / {profile.get('source', '')}",
                        match_type="exact",
                    ))

        # Text results (lens)
        for item in lens_data.get("text_results", []):
            if item.get("link"):
                matches.append(SearchMatch(
                    url=item["link"],
                    title=item.get("title", ""),
                    snippet=item.get("snippet", ""),
                    match_type="partial",
                ))

        # Reverse image search sub-results (lens)
        for item in lens_data.get("reverse_image_search", {}).get("results", []):
            if item.get("link"):
                matches.append(SearchMatch(
                    url=item["link"],
                    title=item.get("title", ""),
                    snippet=item.get("snippet", ""),
                    thumbnail=item.get("thumbnail", ""),
                    match_type="exact",
                ))

        # ── #1: Google Reverse Image results ────────────────────────────────

        # Organic results (news articles, web pages mentioning the image)
        for item in rev_data.get("organic_results", []):
            if item.get("link"):
                matches.append(SearchMatch(
                    url=item["link"],
                    title=item.get("title", ""),
                    snippet=item.get("snippet", ""),
                    thumbnail=item.get("thumbnail", ""),
                    match_type="exact",
                ))

        # Image results from reverse image engine
        for item in rev_data.get("image_results", []):
            if item.get("link"):
                matches.append(SearchMatch(
                    url=item["link"],
                    title=item.get("title", ""),
                    domain=item.get("source", ""),
                    snippet=item.get("snippet", ""),
                    thumbnail=item.get("thumbnail", ""),
                    match_type="visual",
                ))

        # Inline images (reverse)
        for item in rev_data.get("inline_images", []):
            link = item.get("link", "") or item.get("source", "")
            if link:
                matches.append(SearchMatch(
                    url=link,
                    title=item.get("title", ""),
                    thumbnail=item.get("thumbnail", ""),
                    match_type="visual",
                ))

        # Knowledge graph (reverse)
        kg2 = rev_data.get("knowledge_graph", [])
        if isinstance(kg2, dict):
            kg2 = [kg2]
        for item in kg2:
            link = item.get("link", "") or item.get("website", "")
            if link:
                matches.append(SearchMatch(
                    url=link,
                    title=item.get("title", ""),
                    snippet=item.get("subtitle", ""),
                    match_type="exact",
                ))
            for profile in item.get("profiles", []):
                if profile.get("link"):
                    matches.append(SearchMatch(
                        url=profile["link"],
                        title=profile.get("name", ""),
                        match_type="exact",
                    ))

        # Filter empty URLs and deduplicate
        matches = [m for m in matches if m.url]
        seen_urls: set[str] = set()
        unique: list[SearchMatch] = []
        for m in matches:
            if m.url not in seen_urls:
                seen_urls.add(m.url)
                unique.append(m)

        search_url = (
            lens_data.get("search_metadata", {}).get("google_lens_url", "")
            or lens_data.get("search_metadata", {}).get("google_url", "")
        )

        return SearchResponse(
            provider=self.name,
            query_image=query_image,
            matches=unique,
            raw_response={"lens": lens_data, "reverse": rev_data},
            search_url=search_url,
        )
