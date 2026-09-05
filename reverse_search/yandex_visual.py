"""
Yandex Reverse Image Search provider via SerpApi.

Why Yandex for non-famous people:
  - Has its own face-recognition index separate from Google's.
  - Crawls VK, Odnoklassniki, and many Eastern-European/Asian platforms
    that Google under-indexes.
  - For everyday people, Yandex often surfaces matches Google Lens misses.

Uses the same SERPAPI_API_KEY already configured — no extra key needed.
Docs: https://serpapi.com/yandex-reverse-image-api  (engine=yandex_images)
"""

from __future__ import annotations

import os
from pathlib import Path

import requests
from dotenv import load_dotenv

from reverse_search.base import BaseProvider, SearchMatch, SearchResponse
from reverse_search.serpapi_lens import upload_local_image

load_dotenv()

SERPAPI_ENDPOINT = "https://serpapi.com/search.json"


class YandexVisualProvider(BaseProvider):
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
                    "Yandex search runs through SerpApi — "
                    "get a free key at https://serpapi.com/users/sign_up"
                ),
            )

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

        params = {
            "engine": "yandex_images",
            "api_key": self.api_key,
            "url": image_url,
        }
        resp = requests.get(SERPAPI_ENDPOINT, params=params, timeout=90)
        resp.raise_for_status()
        return self._parse_response(image_path, resp.json(), image_url=image_url)

    def _parse_response(self, query_image: str, data: dict, image_url: str = "") -> SearchResponse:
        matches: list[SearchMatch] = []

        for item in data.get("image_results", []):
            url = item.get("link", "")
            thumb = item.get("thumbnail", {})
            if url:
                matches.append(SearchMatch(
                    url=url,
                    title=item.get("title", ""),
                    domain=item.get("source", ""),
                    snippet=item.get("snippet", ""),
                    thumbnail=thumb.get("link", "") if isinstance(thumb, dict) else str(thumb),
                    match_type="visual",
                ))

        for item in data.get("similar_images", []):
            url = item.get("link", "") or item.get("source", "")
            thumb = item.get("thumbnail", {})
            if url:
                matches.append(SearchMatch(
                    url=url,
                    title=item.get("title", ""),
                    thumbnail=thumb.get("link", "") if isinstance(thumb, dict) else str(thumb),
                    match_type="similar",
                ))

        kg = data.get("knowledge_graph", {})
        if isinstance(kg, dict) and kg:
            link = kg.get("link", "") or kg.get("website", "")
            if link:
                matches.append(SearchMatch(
                    url=link,
                    title=kg.get("title", ""),
                    snippet=kg.get("subtitle", ""),
                    match_type="exact",
                ))

        for item in data.get("inline_images", []):
            url = item.get("link", "") or item.get("source", "")
            if url:
                matches.append(SearchMatch(
                    url=url,
                    title=item.get("title", ""),
                    thumbnail=item.get("thumbnail", ""),
                    match_type="visual",
                ))

        # Deduplicate
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
