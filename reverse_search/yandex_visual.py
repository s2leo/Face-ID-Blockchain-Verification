"""
Yandex Reverse Image Search provider via SerpApi.

Why Yandex for non-famous people?
  - Yandex has its own face-recognition index separate from Google's.
  - It crawls VK (Russia's largest social network), Odnoklassniki, and many
    Eastern-European/Asian platforms that Google under-indexes.
  - For everyday people who aren't celebrities, Yandex often surfaces matches
    that Google Lens completely misses — especially profile photos on VK,
    university pages, and local news sites.

Reuses the SERPAPI_API_KEY already configured for the SerpApi Google Lens provider.

Docs: https://serpapi.com/yandex-reverse-image-api
Engine name: yandex_images
"""

from __future__ import annotations

import os
from pathlib import Path

import requests
from dotenv import load_dotenv

from reverse_search.base import BaseProvider, SearchMatch, SearchResponse
from reverse_search.serpapi_lens import upload_local_image  # reuse shared uploader

load_dotenv()

SERPAPI_ENDPOINT = "https://serpapi.com/search.json"


class YandexVisualProvider(BaseProvider):
    """
    Yandex reverse image search via SerpApi.

    Uses the same SERPAPI_API_KEY as the Google Lens provider — no extra key needed.
    Best complementary provider for non-famous / private individuals.
    """

    name = "yandex_reverse_image"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("SERPAPI_API_KEY", "")

    def _execute_search(self, image_path: str, **kwargs) -> SearchResponse:
        if not self.api_key:
            return SearchResponse(
                provider=self.name,
                query_image=image_path,
                error=(
                    "SERPAPI_API_KEY is not set. "
                    "Yandex reverse image search runs through SerpApi — "
                    "get a free key at https://serpapi.com/users/sign_up"
                ),
            )

        # Resolve image URL (SerpApi requires a public URL, not a local path)
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
                return SearchResponse(
                    provider=self.name,
                    query_image=image_path,
                    error=str(e),
                )

        params = {
            "engine": "yandex_images",
            "api_key": self.api_key,
            "url": image_url,
        }

        resp = requests.get(SERPAPI_ENDPOINT, params=params, timeout=90)
        resp.raise_for_status()
        data = resp.json()

        return self._parse_response(image_path, data, image_url=image_url)

    def _parse_response(
        self, query_image: str, data: dict, image_url: str = ""
    ) -> SearchResponse:
        matches: list[SearchMatch] = []

        # --- Primary image results ---
        for item in data.get("image_results", []):
            url = item.get("link", "")
            thumbnail_obj = item.get("thumbnail", {})
            thumbnail_url = (
                thumbnail_obj.get("link", "")
                if isinstance(thumbnail_obj, dict)
                else str(thumbnail_obj)
            )
            if url:
                matches.append(
                    SearchMatch(
                        url=url,
                        title=item.get("title", ""),
                        domain=item.get("source", ""),
                        snippet=item.get("snippet", ""),
                        thumbnail=thumbnail_url,
                        match_type="visual",
                    )
                )

        # --- Similar images (also useful — often same person on different pages) ---
        for item in data.get("similar_images", []):
            url = item.get("link", "") or item.get("source", "")
            thumbnail_obj = item.get("thumbnail", {})
            thumbnail_url = (
                thumbnail_obj.get("link", "")
                if isinstance(thumbnail_obj, dict)
                else str(thumbnail_obj)
            )
            if url:
                matches.append(
                    SearchMatch(
                        url=url,
                        title=item.get("title", ""),
                        thumbnail=thumbnail_url,
                        match_type="similar",
                    )
                )

        # --- Knowledge graph (Yandex sometimes identifies the person directly) ---
        kg = data.get("knowledge_graph", {})
        if isinstance(kg, dict) and kg:
            link = kg.get("link", "") or kg.get("website", "")
            if link:
                matches.append(
                    SearchMatch(
                        url=link,
                        title=kg.get("title", ""),
                        snippet=kg.get("subtitle", ""),
                        match_type="exact",
                    )
                )

        # --- Inline images ---
        for item in data.get("inline_images", []):
            url = item.get("link", "") or item.get("source", "")
            if url:
                matches.append(
                    SearchMatch(
                        url=url,
                        title=item.get("title", ""),
                        thumbnail=item.get("thumbnail", ""),
                        match_type="visual",
                    )
                )

        # Filter empty URLs and deduplicate
        matches = [m for m in matches if m.url]
        seen: set[str] = set()
        unique: list[SearchMatch] = []
        for m in matches:
            if m.url not in seen:
                seen.add(m.url)
                unique.append(m)

        search_url = (
            data.get("search_metadata", {}).get("yandex_images_url", "")
            or data.get("search_metadata", {}).get("yandex_url", "")
        )

        return SearchResponse(
            provider=self.name,
            query_image=query_image,
            matches=unique,
            raw_response=data,
            search_url=search_url,
        )
