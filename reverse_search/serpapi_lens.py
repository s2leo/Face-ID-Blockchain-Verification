"""
SerpApi reverse image search provider.

Uses two SerpApi engines:
  - google_lens          → richer results (visual matches, knowledge graph)
  - google_reverse_image → fallback (organic results, inline images)

IMPORTANT: SerpApi does NOT support direct file uploads.
For local files, this provider auto-uploads the image to a free
temporary hosting service (imgbb) to get a public URL first.

Docs:
  https://serpapi.com/google-lens-api
  https://serpapi.com/google-reverse-image
Free: 100 searches/month (no credit card required)
"""

from __future__ import annotations

import os
import base64
from pathlib import Path

import requests
from dotenv import load_dotenv

from reverse_search.base import BaseProvider, SearchMatch, SearchResponse

load_dotenv()

SERPAPI_ENDPOINT = "https://serpapi.com/search.json"


def _upload_image_to_freeimage(file_path: Path) -> str:
    """
    Upload a local image to freeimage.host (free, no API key required)
    and return the public URL.

    Falls back to base64 data-uri if upload fails.
    """
    # freeimage.host — free image hosting, no API key required
    with open(file_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode("utf-8")

    resp = requests.post(
        "https://freeimage.host/api/1/upload",
        data={
            "key": "6d207e02198a847aa98d0a2a901485a5",  # public API key for freeimage.host
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

    raise RuntimeError(f"Image upload failed: {data}")


def _upload_image_to_imgbb(file_path: Path) -> str:
    """
    Upload a local image to imgbb.com (free, public API).
    Returns the direct image URL.
    """
    with open(file_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode("utf-8")

    resp = requests.post(
        "https://api.imgbb.com/1/upload",
        data={
            "key": "3e45a9cde06f1f41e2e6c3b9f0b1e5d7",  # free tier public key
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
    Tries multiple free hosting services as fallbacks.
    """
    errors = []

    # Try freeimage.host first (no key needed)
    try:
        return _upload_image_to_freeimage(file_path)
    except Exception as e:
        errors.append(f"freeimage.host: {e}")

    # Fallback: 0x0.st (simple curl-like upload, no API key)
    try:
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
    except Exception as e:
        errors.append(f"0x0.st: {e}")

    raise RuntimeError(
        f"Failed to upload image to any hosting service. Errors:\n"
        + "\n".join(f"  - {e}" for e in errors)
        + "\n\nAlternative: pass a public image URL instead of a local file."
    )


class SerpApiLensProvider(BaseProvider):
    """Google Lens / Reverse Image via SerpApi."""

    name = "serpapi_google_lens"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("SERPAPI_API_KEY", "")

    # -----------------------------------------------------------------
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

        is_url = image_path.startswith(("http://", "https://"))

        if is_url:
            image_url = image_path
        else:
            # Local file — must upload to get a public URL first
            # (SerpApi does NOT support direct file upload)
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
                return SearchResponse(
                    provider=self.name,
                    query_image=image_path,
                    error=str(e),
                )

        # Use Google Lens engine (richer results than google_reverse_image)
        params = {
            "engine": "google_lens",
            "api_key": self.api_key,
            "url": image_url,
        }
        resp = requests.get(SERPAPI_ENDPOINT, params=params, timeout=90)
        resp.raise_for_status()
        data = resp.json()

        return self._parse_response(image_path, data, image_url=image_url)

    # -----------------------------------------------------------------
    def _parse_response(
        self, query_image: str, data: dict, image_url: str = ""
    ) -> SearchResponse:
        matches: list[SearchMatch] = []

        # --- Visual Matches (google_lens engine) ---
        for item in data.get("visual_matches", []):
            matches.append(
                SearchMatch(
                    url=item.get("link", ""),
                    title=item.get("title", ""),
                    domain=item.get("source", ""),
                    snippet=item.get("snippet", ""),
                    thumbnail=item.get("thumbnail", ""),
                    match_type="visual",
                )
            )

        # --- Image Results (google_reverse_image engine) ---
        for item in data.get("image_results", []):
            matches.append(
                SearchMatch(
                    url=item.get("link", ""),
                    title=item.get("title", ""),
                    domain=item.get("source", ""),
                    snippet=item.get("snippet", ""),
                    thumbnail=item.get("thumbnail", ""),
                    match_type="visual",
                )
            )

        # --- Inline Images ---
        for item in data.get("inline_images", []):
            link = item.get("link", "") or item.get("source", "")
            if link:
                matches.append(
                    SearchMatch(
                        url=link,
                        title=item.get("title", ""),
                        thumbnail=item.get("thumbnail", ""),
                        match_type="visual",
                    )
                )

        # --- Knowledge Graph (sometimes has social links) ---
        kg = data.get("knowledge_graph", [])
        if isinstance(kg, dict):
            kg = [kg]
        for item in kg:
            link = item.get("link", "") or item.get("website", "")
            if link:
                matches.append(
                    SearchMatch(
                        url=link,
                        title=item.get("title", ""),
                        snippet=item.get("subtitle", ""),
                        match_type="exact",
                    )
                )
            # Social profile links inside KG
            for profile in item.get("profiles", []):
                matches.append(
                    SearchMatch(
                        url=profile.get("link", ""),
                        title=profile.get("name", ""),
                        snippet=f"via Knowledge Graph / {profile.get('source', '')}",
                        match_type="exact",
                    )
                )

        # --- Organic Results ---
        for item in data.get("organic_results", []):
            link = item.get("link", "")
            if link:
                matches.append(
                    SearchMatch(
                        url=link,
                        title=item.get("title", ""),
                        snippet=item.get("snippet", ""),
                        match_type="exact",
                    )
                )

        # --- Reverse Image Search results ---
        for item in data.get("reverse_image_search", {}).get("results", []):
            matches.append(
                SearchMatch(
                    url=item.get("link", ""),
                    title=item.get("title", ""),
                    snippet=item.get("snippet", ""),
                    thumbnail=item.get("thumbnail", ""),
                    match_type="exact",
                )
            )

        # --- Text Results (sometimes appear in google_lens) ---
        for item in data.get("text_results", []):
            link = item.get("link", "")
            if link:
                matches.append(
                    SearchMatch(
                        url=link,
                        title=item.get("title", ""),
                        snippet=item.get("snippet", ""),
                        match_type="partial",
                    )
                )

        # Filter out empty URLs
        matches = [m for m in matches if m.url]

        # Deduplicate by URL
        seen_urls: set[str] = set()
        unique_matches: list[SearchMatch] = []
        for m in matches:
            if m.url not in seen_urls:
                seen_urls.add(m.url)
                unique_matches.append(m)

        # Try to get the search URL from metadata
        search_url = (
            data.get("search_metadata", {}).get("google_lens_url", "")
            or data.get("search_metadata", {}).get("google_url", "")
        )

        return SearchResponse(
            provider=self.name,
            query_image=query_image,
            matches=unique_matches,
            raw_response=data,
            search_url=search_url,
        )
