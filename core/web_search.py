"""Optional web-search fallback for "Auto" model selection.

core/model_detect.py's find_best_hf_model() is the primary, keyless
mechanism and covers every stage type. This module is a secondary,
opt-in enrichment for when the user wants broader options than what's
hosted on Hugging Face - it requires the user to configure a search
provider + API key in Settings first (nothing here works without that).

Results are always surfaced as candidate links for the user to review and
pick from, never auto-installed - a raw web search ranking isn't a trust
signal strong enough to download and run a model from unattended.

Built with one provider (Google Programmable Search Engine / Custom
Search JSON API) since that's the most commonly available "Google search"
API; SEARCH_PROVIDERS is a dict specifically so more can be added the same
way core/providers/*/cloud_rest.py's presets are - without touching
callers.
"""

import requests


def _google_cse_search(query, api_key, engine_id, num):
    from core.network_policy import require_network_allowed
    require_network_allowed('https://www.googleapis.com')
    resp = requests.get(
        "https://www.googleapis.com/customsearch/v1",
        params={"key": api_key, "cx": engine_id, "q": query, "num": num},
        timeout=10,
    )
    resp.raise_for_status()
    items = resp.json().get("items", [])
    return [{"title": i.get("title", ""), "link": i.get("link", ""), "snippet": i.get("snippet", "")} for i in items]


SEARCH_PROVIDERS = {
    "google_cse": _google_cse_search,
}


def is_configured(provider, api_key, engine_id=None):
    if provider not in SEARCH_PROVIDERS:
        return False
    if not api_key:
        return False
    if provider == "google_cse" and not engine_id:
        return False
    return True


def search(query, provider, api_key, engine_id=None, num=5):
    """Returns [{"title", "link", "snippet"}, ...], or raises RuntimeError
    with a clear message on misconfiguration/failure - callers decide how
    to surface that (this module doesn't know about the UI)."""
    fn = SEARCH_PROVIDERS.get(provider)
    if fn is None:
        raise RuntimeError(f"Unknown search provider: {provider}")
    if not is_configured(provider, api_key, engine_id):
        raise RuntimeError("Web search isn't configured yet - add a search API key in Settings.")
    try:
        return fn(query, api_key, engine_id, num)
    except requests.RequestException as e:
        raise RuntimeError(f"Web search failed: {e}") from e
