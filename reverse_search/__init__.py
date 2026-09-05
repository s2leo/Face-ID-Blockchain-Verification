"""
reverse_search — Unified Reverse Image Search Module
=====================================================

Provides a multi-provider reverse image search abstraction for the
HH Goa 2026 pipeline.

Provider comparison for non-famous individuals:
  ┌─────────────────┬──────────────────────────────────────────────────────┐
  │ Provider        │ Best For                                             │
  ├─────────────────┼──────────────────────────────────────────────────────┤
  │ serpapi         │ General web search via Google Lens (default)         │
  │ yandex          │ Non-famous people — indexes VK, Eastern-EU socials   │
  │ facecheck       │ Purpose-built face search across social/news/dating  │
  │ google_vision   │ Exact image matching via Google Cloud Vision API     │
  │ bing            │ Microsoft Azure Bing Visual Search fallback          │
  └─────────────────┴──────────────────────────────────────────────────────┘

Quick start:
    from reverse_search import search_image
    results = search_image("photo.jpg", provider="serpapi")   # Google Lens
    results = search_image("photo.jpg", provider="yandex")    # Yandex
    results = search_image("photo.jpg", provider="facecheck") # FaceCheck.id
"""

from reverse_search.base import SearchMatch, SearchResponse, BaseProvider
from reverse_search.serpapi_lens import SerpApiLensProvider
from reverse_search.yandex_visual import YandexVisualProvider
from reverse_search.facecheck_id import FaceCheckProvider
from reverse_search.google_vision import GoogleVisionProvider
from reverse_search.bing_visual import BingVisualProvider
from reverse_search.biometric_verifier import BiometricVerifier

# Registry of available providers — order matters for --all-providers runs
PROVIDERS: dict[str, type] = {
    "serpapi": SerpApiLensProvider,     # Google Lens — best general coverage
    "yandex": YandexVisualProvider,     # Yandex — best for non-famous individuals
    "facecheck": FaceCheckProvider,     # FaceCheck.id — face-specific search
    "google_vision": GoogleVisionProvider,
    "bing": BingVisualProvider,
}

# Human-readable descriptions for each provider
PROVIDER_DESCRIPTIONS: dict[str, str] = {
    "serpapi": "Google Lens via SerpApi (general, ~100 free searches/month)",
    "yandex": "Yandex Reverse Image via SerpApi (best for non-celebrities, same API key)",
    "facecheck": "FaceCheck.id (face-specific search, paid credits; testing mode free)",
    "google_vision": "Google Cloud Vision WEB_DETECTION (requires GCP service account)",
    "bing": "Bing Visual Search (requires Azure subscription key)",
}


def search_image(image_path: str, provider: str = "serpapi", **kwargs) -> SearchResponse:
    """
    Run a reverse image search using the specified provider.

    Args:
        image_path: Path to a local image file or a public image URL.
        provider:   One of 'serpapi', 'yandex', 'facecheck', 'google_vision', 'bing'.
        **kwargs:   Additional provider-specific options passed to the provider constructor.

    Returns:
        SearchResponse with normalized matches across all providers.
    """
    provider_key = provider.lower().strip().replace("-", "_").replace(" ", "_")
    if provider_key not in PROVIDERS:
        raise ValueError(
            f"Unknown provider '{provider}'. "
            f"Available: {', '.join(PROVIDERS.keys())}"
        )
    instance = PROVIDERS[provider_key]()
    return instance.search(image_path, **kwargs)


__all__ = [
    "search_image",
    "PROVIDERS",
    "PROVIDER_DESCRIPTIONS",
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
