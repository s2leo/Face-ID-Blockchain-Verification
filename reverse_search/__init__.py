"""
reverse_search — Unified Reverse Image Search Module
=====================================================

Provides a multi-provider reverse image search abstraction for Phase 1
derisking of the HH Goa 2026 pipeline.

Supported providers:
  - SerpApi Google Lens  (recommended, free tier)
  - Google Cloud Vision  (backup)
  - Bing Visual Search   (stub / fallback)

Quick start:
    from reverse_search import search_image
    results = search_image("photo.jpg", provider="serpapi")
"""

from reverse_search.base import SearchMatch, SearchResponse, BaseProvider
from reverse_search.serpapi_lens import SerpApiLensProvider
from reverse_search.google_vision import GoogleVisionProvider
from reverse_search.bing_visual import BingVisualProvider
from reverse_search.biometric_verifier import BiometricVerifier

# Registry of available providers
PROVIDERS = {
    "serpapi": SerpApiLensProvider,
    "google_vision": GoogleVisionProvider,
    "bing": BingVisualProvider,
}


def search_image(image_path: str, provider: str = "serpapi", **kwargs) -> SearchResponse:
    """
    Run a reverse image search using the specified provider.

    Args:
        image_path: Path to local image file or a public image URL.
        provider: One of 'serpapi', 'google_vision', 'bing'.
        **kwargs: Additional provider-specific options.

    Returns:
        SearchResponse with normalized matches.
    """
    provider_key = provider.lower().replace("-", "_").replace(" ", "_")
    if provider_key not in PROVIDERS:
        raise ValueError(
            f"Unknown provider '{provider}'. "
            f"Available: {', '.join(PROVIDERS.keys())}"
        )
    instance = PROVIDERS[provider_key]()
    return instance.search(image_path, **kwargs)

