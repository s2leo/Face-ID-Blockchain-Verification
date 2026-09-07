"""
reverse_search — Unified Reverse Image Search Module
=====================================================

Provider guide:
  serpapi       — Google Lens via SerpApi (best general coverage)
  yandex        — Yandex reverse image via SerpApi (best for non-famous people,
                  same SERPAPI_API_KEY, no extra cost)
  facecheck     — FaceCheck.id face-specific search (purpose-built for faces,
                  free testing mode, paid for full index)
  google_vision — Google Cloud Vision WEB_DETECTION (requires GCP service account)
  bing          — Bing Visual Search (requires Azure key)

Quick start:
    from reverse_search import search_image
    results = search_image("photo.jpg", provider="serpapi")
    results = search_image("photo.jpg", provider="yandex")
    results = search_image("photo.jpg", provider="facecheck")
"""

from reverse_search.base import SearchMatch, SearchResponse, BaseProvider, merge_responses
from reverse_search.serpapi_lens import SerpApiLensProvider
from reverse_search.yandex_visual import YandexVisualProvider
from reverse_search.facecheck_id import FaceCheckProvider
from reverse_search.google_vision import GoogleVisionProvider
from reverse_search.bing_visual import BingVisualProvider
from reverse_search.biometric_verifier import BiometricVerifier
from reverse_search.social_profile_finder import find_social_profiles, extract_candidate_name
from reverse_search.gemini_vision import GeminiVisionAnalyzer, GeminiAnalysis

PROVIDERS: dict[str, type] = {
    "serpapi":       SerpApiLensProvider,
    "yandex":        YandexVisualProvider,
    "facecheck":     FaceCheckProvider,
    "google_vision": GoogleVisionProvider,
    "bing":          BingVisualProvider,
}

PROVIDER_DESCRIPTIONS: dict[str, str] = {
    "serpapi":       "Google Lens via SerpApi (~100 free searches/month)",
    "yandex":        "Yandex reverse image via SerpApi (best for non-celebrities, same key)",
    "facecheck":     "FaceCheck.id face-specific search (testing mode free)",
    "google_vision": "Google Cloud Vision WEB_DETECTION (requires GCP service account)",
    "bing":          "Bing Visual Search (requires Azure key)",
}


def search_image(image_path: str, provider: str = "serpapi", **kwargs) -> SearchResponse:
    """
    Run a reverse image search using the specified provider.

    Args:
        image_path: Local file path or public image URL.
        provider:   One of 'serpapi', 'yandex', 'facecheck', 'google_vision', 'bing'.
        **kwargs:   Passed through to the provider constructor.

    Returns:
        SearchResponse with normalised, categorised matches.
    """
    key = provider.lower().strip().replace("-", "_").replace(" ", "_")
    if key not in PROVIDERS:
        raise ValueError(
            f"Unknown provider '{provider}'. "
            f"Available: {', '.join(PROVIDERS.keys())}"
        )
    return PROVIDERS[key]().search(image_path, **kwargs)


__all__ = [
    "search_image",
    "PROVIDERS",
    "PROVIDER_DESCRIPTIONS",
    "merge_responses",
    "find_social_profiles",
    "extract_candidate_name",
    "GeminiVisionAnalyzer",
    "GeminiAnalysis",
    "SearchMatch",
    "SearchResponse",
    "BaseProvider",
    "BiometricVerifier",
    "SerpApiLensProvider",
    "YandexVisualProvider",
    "FaceCheckProvider",
    "GoogleVisionProvider",
    "BingVisualProvider",
]
