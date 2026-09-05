"""
Bing Visual Search API provider (fallback / stub).

Docs: https://learn.microsoft.com/en-us/bing/search-apis/bing-visual-search/overview
Requires: Azure subscription + Bing Search resource.
"""

from __future__ import annotations

import os
import json
from pathlib import Path

import requests
from dotenv import load_dotenv

from reverse_search.base import BaseProvider, SearchMatch, SearchResponse

load_dotenv()

BING_ENDPOINT = "https://api.bing.microsoft.com/v7.0/images/visualsearch"


class BingVisualProvider(BaseProvider):
    """Bing Visual Search API."""

    name = "bing_visual_search"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("BING_SEARCH_API_KEY", "")

    def _execute_search(self, image_path: str, **kwargs) -> SearchResponse:
        if not self.api_key:
            return SearchResponse(
                provider=self.name,
                query_image=image_path,
                error=(
                    "BING_SEARCH_API_KEY is not set. "
                    "Create a Bing Search resource at "
                    "https://portal.azure.com/#create/Microsoft.BingSearch "
                    "and add the key to .env"
                ),
            )

        headers = {
            "Ocp-Apim-Subscription-Key": self.api_key,
        }

        if image_path.startswith(("http://", "https://")):
            # URL-based search
            knowledge_request = {
                "imageInfo": {"url": image_path},
            }
            data = {"knowledgeRequest": json.dumps(knowledge_request)}
            resp = requests.post(
                BING_ENDPOINT, headers=headers, data=data, timeout=60
            )
        else:
            file_path = Path(image_path).expanduser().resolve()
            if not file_path.exists():
                return SearchResponse(
                    provider=self.name,
                    query_image=image_path,
                    error=f"Image file not found: {file_path}",
                )
            with open(file_path, "rb") as f:
                resp = requests.post(
                    BING_ENDPOINT,
                    headers=headers,
                    files={"image": (file_path.name, f)},
                    timeout=60,
                )

        resp.raise_for_status()
        result = resp.json()
        return self._parse_response(image_path, result)

    def _parse_response(self, query_image: str, data: dict) -> SearchResponse:
        matches: list[SearchMatch] = []

        for tag in data.get("tags", []):
            for action in tag.get("actions", []):
                action_type = action.get("actionType", "")
                if action_type in (
                    "PagesIncluding",
                    "VisualSearch",
                    "ImageById",
                ):
                    for item in action.get("data", {}).get("value", []):
                        url = item.get("hostPageUrl") or item.get("contentUrl", "")
                        if url:
                            matches.append(
                                SearchMatch(
                                    url=url,
                                    title=item.get("name", ""),
                                    snippet=item.get("snippet", ""),
                                    thumbnail=item.get("thumbnailUrl", ""),
                                    match_type="visual",
                                )
                            )

        # Deduplicate
        seen = set()
        unique = []
        for m in matches:
            if m.url not in seen:
                seen.add(m.url)
                unique.append(m)

        return SearchResponse(
            provider=self.name,
            query_image=query_image,
            matches=unique,
            raw_response=data,
        )

