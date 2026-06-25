import os
import json
import logging
import requests
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ModelDiscovery")

REGISTRY_PATH = os.path.join(os.path.dirname(__file__), "model_registry.json")

def load_live_registry():
    gist_url = os.environ.get("MODEL_REGISTRY_URL")
    if gist_url:
        try:
            res = requests.get(gist_url, timeout=5)
            if res.status_code == 200:
                logger.info("Loaded registry from Gist.")
                return res.json()
        except Exception as e:
            logger.warning(f"Failed to load from Gist URL: {e}")
            
    if os.path.exists(REGISTRY_PATH):
        with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"MODEL_CAPABILITIES": {}, "MODEL_SCORES": {}, "TAG_WEIGHTS": {}, "MISSING_MODELS": {}, "MODEL_METADATA": {}}

def save_registry(registry):
    # Always save locally as a backup
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2)
        
    # Push to Gist if credentials exist
    gist_id = os.environ.get("GIST_ID")
    github_token = os.environ.get("GITHUB_TOKEN")
    if gist_id and github_token:
        try:
            url = f"https://api.github.com/gists/{gist_id}"
            headers = {
                "Authorization": f"token {github_token}",
                "Accept": "application/vnd.github.v3+json"
            }
            payload = {
                "files": {
                    "model_registry.json": {
                        "content": json.dumps(registry, indent=2)
                    }
                }
            }
            res = requests.patch(url, headers=headers, json=payload, timeout=5)
            if res.status_code == 200:
                logger.info("Successfully pushed updated registry to GitHub Gist.")
            else:
                logger.error(f"Failed to push to Gist. Status {res.status_code}: {res.text}")
        except Exception as e:
            logger.error(f"Network error pushing to Gist: {e}")

def fetch_openai():
    try:
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key: return []
        res = requests.get("https://api.openai.com/v1/models", headers={"Authorization": f"Bearer {api_key}"}, timeout=10)
        return [m["id"] for m in res.json().get("data", []) if "gpt" in m["id"] or "o1" in m["id"] or "o3" in m["id"]]
    except Exception as e:
        logger.error(f"OpenAI fetch failed: {e}")
        return []

def fetch_google():
    try:
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key: return []
        res = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}", timeout=10)
        return [m["name"].split('/')[-1] for m in res.json().get("models", []) if "gemini" in m.get("name", "")]
    except Exception as e:
        logger.error(f"Google fetch failed: {e}")
        return []

def fetch_deepseek():
    try:
        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        if not api_key: return []
        res = requests.get("https://api.deepseek.com/models", headers={"Authorization": f"Bearer {api_key}"}, timeout=10)
        return [m["id"] for m in res.json().get("data", [])] if res.status_code == 200 else []
    except Exception as e:
        logger.error(f"DeepSeek fetch failed: {e}")
        return []

def run_search_classification(new_model_name, scout_model, provider, api_key):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{scout_model}:generateContent?key={api_key}"
    
    domain_map = {
        "openai": "site:openai.com OR site:platform.openai.com OR site:developers.openai.com",
        "google": "site:blog.google OR site:ai.google.dev",
        "deepseek": "site:deepseek.com OR site:api.deepseek.com"
    }
    domain_filter = domain_map.get(provider, "")
    
    prompt = f"""
    You are a strict technical scout agent. I have discovered a new AI model identifier named '{new_model_name}' released by '{provider}'.

    STEP 1: GROUNDING (MANDATORY)
    Use the Google Search tool to search for the official documentation for '{new_model_name}'.
    You MUST append this exact filter to your search query to prevent hallucination and rumors: {domain_filter}
    Do NOT use Wikipedia, Reddit, or tech blogs. Rely ONLY on the official provider domain.

    Look for:
    1. Context Window Size (in tokens).
    2. Is it a "reasoning", "chain of thought", or "system 2" model?
    3. Is it optimized for "speed", "low latency", "cost", or "lightweight" tasks?
    4. Is it a "flagship", "premium", "standard", or "lite" model?

    STEP 2: CLASSIFICATION
    Based EXCLUSIVELY on the official search results, classify the model into our exact JSON structure:
    {{
        "caps": ["tag1", "tag2"],
        "tier": "tier_name"
    }}

    Allowed Tags: ["reasoning", "coding", "large_context", "balanced", "fast", "cost_efficient"]
    Allowed Tiers: ["flagship", "premium", "standard", "lite"]

    Classification Rules:
    - If the official docs state it is a reasoning/thinking model (like o1 or DeepSeek R1), tag "reasoning".
    - If the official docs state it is optimized for coding, tag "coding".
    - If the official docs state it optimizes for speed, latency, or cost (like Flash or Mini), tag "fast".
    - If the official context window is 100,000 tokens or greater, tag "large_context".
    - If it is a flagship general-purpose model, tag "balanced".
    - ONLY include tags explicitly supported by the search results. DO NOT guess.

    Tier Rules:
    - "flagship": The provider's absolute most powerful logic/reasoning model.
    - "premium": The provider's general purpose powerful model (e.g., pro).
    - "standard": The provider's standard/fast model (e.g., flash, mini).
    - "lite": Specifically designated as ultra-lightweight.

    Return ONLY valid raw JSON.
    """
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"googleSearchRetrieval": {}}]
    }
    
    res = requests.post(url, json=payload, timeout=15)
    if res.status_code != 200:
        raise Exception(f"API Error {res.status_code}: {res.text}")
        
    data = res.json()
    candidates = data.get("candidates", [])
    if not candidates:
        raise Exception("No candidates returned.")
        
    parts = candidates[0].get("content", {}).get("parts", [])
    if not parts:
        raise Exception("No parts returned in candidate content.")
    text = parts[0].get("text", "")
    
    text_clean = text.strip().replace("```json", "").replace("```", "").strip()
    result = json.loads(text_clean)
    
    valid_tags = {"reasoning", "coding", "large_context", "balanced", "fast", "cost_efficient"}
    valid_tiers = {"flagship", "premium", "standard", "lite"}
    
    # Strict JSON validation
    caps = result.get("caps", [])
    if not isinstance(caps, list):
        caps = ["balanced"]
    caps = [t for t in caps if t in valid_tags]
    if not caps:
        caps = ["balanced"]
        
    tier = result.get("tier", "standard")
    if tier not in valid_tiers:
        tier = "standard"
        
    return {"caps": caps, "tier": tier}

def extract_new_model_specs(new_model_name, provider):
    scout_candidates = ["gemini-flash", "gemini-pro"]
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    
    if not gemini_key:
        logger.warning("No GEMINI_API_KEY, cannot perform search classification.")
        return {"caps": ["balanced"], "tier": "standard", "scout": "none"}
        
    for scout_model in scout_candidates:
        try:
            logger.info(f"Attempting classification of {new_model_name} using scout model: {scout_model}")
            result = run_search_classification(new_model_name, scout_model, provider, gemini_key)
            result["scout"] = scout_model
            logger.info(f"Classification successful with {scout_model}: {result}")
            return result
        except Exception as e:
            logger.debug(f"Scout model {scout_model} failed: {e}")
            continue
            
    logger.warning(f"All scout models failed for {new_model_name}. Defaulting to balanced.")
    return {"caps": ["balanced"], "tier": "standard", "scout": "failed"}

def get_tier_score(tier):
    tier_scores = {"flagship": 8, "premium": 6, "standard": 4, "lite": 2}
    return tier_scores.get(tier, 4)

def test_model_connection(model_name, provider):
    try:
        if provider == "openai":
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key: return None
            url = "https://api.openai.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}"}
            payload = {"model": model_name, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1}
            res = requests.post(url, headers=headers, json=payload, timeout=10)
        elif provider == "google":
            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key: return None
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            payload = {"contents": [{"parts": [{"text": "hi"}]}], "generationConfig": {"maxOutputTokens": 1}}
            res = requests.post(url, json=payload, timeout=10)
        elif provider == "deepseek":
            api_key = os.environ.get("DEEPSEEK_API_KEY")
            if not api_key: return None
            url = "https://api.deepseek.com/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}"}
            payload = {"model": model_name, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1}
            res = requests.post(url, headers=headers, json=payload, timeout=10)
        else:
            return None

        if res.status_code == 200:
            return True
        elif res.status_code in [400, 401, 403, 404]:
            # Deterministic failure (paywall, invalid params, unauthorized)
            return False
        elif res.status_code == 429 or res.status_code >= 500:
            # Transient failure (rate limit, server error)
            return None
    except requests.RequestException as e:
        logger.warning(f"Network error testing model {model_name} ({provider}): {e}")
        return None
    return None

def sync_and_update_models():
    registry = load_live_registry()
    model_caps = registry.get("MODEL_CAPABILITIES", {})
    model_scores = registry.get("MODEL_SCORES", {})
    tag_weights = registry.get("TAG_WEIGHTS", {})
    missing_models = registry.get("MISSING_MODELS", {})
    model_metadata = registry.get("MODEL_METADATA", {})
    
    openai_models = fetch_openai()
    google_models = fetch_google()
    deepseek_models = fetch_deepseek()
    
    active_providers = set()
    if openai_models: active_providers.add("openai")
    if google_models: active_providers.add("google")
    if deepseek_models: active_providers.add("deepseek")
    
    if not active_providers:
        logger.warning("Could not contact any APIs. Keeping existing registry intact.")
        return
        
    live_models = {}
    for m in openai_models: live_models[m] = "openai"
    for m in google_models: live_models[m] = "google"
    for m in deepseek_models: live_models[m] = "deepseek"

    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. Grace Period for Missing Models
    current_known_models = list(model_metadata.keys())
    for model in current_known_models:
        provider = model_metadata[model].get("provider")
        if provider not in active_providers:
            continue
        if model not in live_models:
            missing_count = missing_models.get(model, 0) + 1
            missing_models[model] = missing_count
            logger.warning(f"Model {model} missing from API! Count: {missing_count}")
            
            if missing_count >= 3:
                logger.warning(f"Model {model} missing for 3 consecutive syncs. Deleting.")
                if model in model_caps: del model_caps[model]
                if model in model_scores: del model_scores[model]
                if model in model_metadata: del model_metadata[model]
                del missing_models[model]
        else:
            # Model is live, reset missing counter if it was missing
            if model in missing_models:
                logger.info(f"Model {model} reappeared. Resetting missing counter.")
                del missing_models[model]

    # 2. Discover and update models
    for live_model, provider in live_models.items():
        if live_model not in model_metadata:
            # Found a completely new model!
            logger.info(f"New model discovered: {live_model} from {provider}")
            specs = extract_new_model_specs(live_model, provider)
            
            model_metadata[live_model] = {
                "provider": provider,
                "tier": specs["tier"],
                "caps": specs["caps"],
                "verified": False,
                "connection_ok": "pending",
                "observations": 1,
                "first_seen": now_iso,
                "last_seen": now_iso,
                "source": "official_docs",
                "scout": specs["scout"]
            }
            logger.info(f"Added {live_model} to staging area (unverified).")
        else:
            # Model already exists in metadata
            meta = model_metadata[live_model]
            meta["last_seen"] = now_iso
            
            # 3. Live API Connection Ping
            if meta.get("connection_ok") is not True:
                logger.info(f"Pinging {live_model} to test API access...")
                ping_result = test_model_connection(live_model, provider)
                if ping_result is True:
                    meta["connection_ok"] = True
                    logger.info(f"Ping successful! Model {live_model} is accessible.")
                elif ping_result is False:
                    meta["connection_ok"] = False
                    logger.warning(f"Ping failed deterministically (403/404). {live_model} is inaccessible.")
                else:
                    logger.info(f"Ping hit a transient error (429/5xx). Will retry next sync.")
            
            # Stop tracking observations if connection is deterministically broken
            if meta.get("connection_ok") is False:
                model_metadata[live_model] = meta
                if live_model in model_caps:
                    del model_caps[live_model]
                if live_model in model_scores:
                    del model_scores[live_model]
                continue

            if not meta.get("verified", False):
                # Increment observations
                obs = meta.get("observations", 0) + 1
                meta["observations"] = obs
                logger.info(f"Unverified model {live_model} observed {obs} times.")
                
                if obs >= 3 and meta.get("connection_ok") is True:
                    # Promote to Verified!
                    meta["verified"] = True
                    logger.info(f"Model {live_model} reached 3 observations and passed connection ping! Promoting to Verified Production.")
                    
            # If it is verified, ensure it is in the active routing dictionaries
            if meta.get("verified", False) and meta.get("connection_ok") is True:
                caps = meta.get("caps", ["balanced"])
                if live_model not in model_caps:
                    model_caps[live_model] = caps
                
                # Deterministic scoring
                tier_base = get_tier_score(meta.get("tier", "standard"))
                tag_score = sum(tag_weights.get(tag, 0) for tag in caps)
                total_score = min(10, tier_base + tag_score)
                model_scores[live_model] = total_score
                
            model_metadata[live_model] = meta

    registry["MODEL_CAPABILITIES"] = model_caps
    registry["MODEL_SCORES"] = model_scores
    registry["MISSING_MODELS"] = missing_models
    registry["MODEL_METADATA"] = model_metadata
    
    save_registry(registry)
    logger.info("Registry synced successfully.")

if __name__ == "__main__":
    sync_and_update_models()
