"""
Yandex Reverse Image Search provider via SerpApi.

Why Yandex for non-famous people:
  - Has its own face-recognition index separate from Google's.
  - Crawls VK, Odnoklassniki, and many Eastern-European/Asian platforms
    that Google under-indexes.
  - For everyday people, Yandex often surfaces matches Google Lens misses.

Improvements applied:
  #6 — After the initial search, Yandex returns a cbir_id (internal image ID).
       A second call using that cbir_id fetches a fresh batch of similar-image
       results from a different part of Yandex's index. Both result sets are
       merged and deduplicated before returning.

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

        # Resolve to a public URL (upload_local_image uses the MD5 cache from #9)
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

        # --- First call: reverse image search by URL ---
        params = {
            "engine":   "yandex_images",
            "api_key":  self.api_key,
            "url":      image_url,
        }
        try:
            resp = requests.get(SERPAPI_ENDPOINT, params=params, timeout=90)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            return SearchResponse(provider=self.name, query_image=image_path,
                                  error=f"Yandex first call failed: {e}")

        # --- #6: Second call using cbir_id for more results ---
        # Yandex assigns an internal image ID (cbir_id) after processing.
        # A second request with this ID queries a different slice of the index.
        cbir_data: dict = {}
        cbir_id = self._extract_cbir_id(data)
        if cbir_id:
            try:
                cbir_params = {
                    "engine":   "yandex_images",
                    "api_key":  self.api_key,
                    "cbir_id":  cbir_id,
                }
                cbir_resp = requests.get(SERPAPI_ENDPOINT, params=cbir_params, timeout=90)
                cbir_resp.raise_for_status()
                cbir_data = cbir_resp.json()
            except Exception:
                cbir_data = {}   # non-fatal — first call results are still used

        return self._parse_response(image_path, data, cbir_data, image_url=image_url)

    def _extract_cbir_id(self, data: dict) -> str | None:
        """
        #6: Extract Yandex's internal cbir_id from the response.
        It appears in image_preview.crops[].serpapi_link as cbir_id=<value>,
        or sometimes directly in search_parameters.
        """
        # Check search_parameters first
        cbir = data.get("search_parameters", {}).get("cbir_id")
        if cbir:
            return str(cbir)

        # Check image_preview crops
        preview = data.get("image_preview", {})
        for crop in preview.get("crops", []):
            crop_id = crop.get("crop_id")
            if crop_id is not None:
                return str(crop_id)
            # Try parsing from serpapi_link query string
            link = crop.get("serpapi_link", "")
            if "cbir_id=" in link:
                try:
                    from urllib.parse import urlparse, parse_qs
                    qs = parse_qs(urlparse(link).query)
                    if "cbir_id" in qs:
                        return qs["cbir_id"][0]
                except Exception:
                    pass

        # Check image_preview.image.serpapi_link
        img_link = preview.get("image", {}).get("serpapi_link", "")
        if "cbir_id=" in img_link:
            try:
                from urllib.parse import urlparse, parse_qs
                qs = parse_qs(urlparse(img_link).query)
                if "cbir_id" in qs:
                    return qs["cbir_id"][0]
            except Exception:
                pass

        return None

    def _collect_matches(self, data: dict) -> list[SearchMatch]:
        """Parse all match types from a single Yandex API response dict."""
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

        return [m for m in matches if m.url]

    def _parse_response(
        self,
        query_image: str,
        data: dict,
        cbir_data: dict,
        image_url: str = "",
    ) -> SearchResponse:
        # Collect matches from both calls
        matches = self._collect_matches(data)

        # #6: merge cbir_id second-call results
        if cbir_data:
            matches.extend(self._collect_matches(cbir_data))

        # Deduplicate by URL
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
            raw_response={"first": data, "cbir": cbir_data},
            search_url=search_url,
        )
