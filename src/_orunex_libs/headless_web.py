import os
import warnings as _warnings

# Suppress legacy rename warning by trying the new name first
try:
    from ddgs import DDGS
except ImportError:
    try:
        with _warnings.catch_warnings():
            _warnings.simplefilter("ignore")
            from duckduckgo_search import DDGS  # Legacy alias
    except ImportError:
        DDGS = None
try:
    from bs4 import BeautifulSoup  # type: ignore
    import requests
except ImportError:
    BeautifulSoup = None
    import requests

def extract_text_from_url(url, truncate_len=2000):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/100.0'}
        r = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Remove noisy elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.extract()
            
        text = " ".join(soup.stripped_strings)
        if len(text) > truncate_len:
            text = text[:truncate_len] + "..."
        return text
    except:
        return ""

def search_and_summarize(query, max_results=3):
    """
    Motor Headless Orunex V30.2 — Busqueda web robusta con corpus garantizado.
    Extrae texto de DDG + scrapeo de URLs para maximo contenido.
    """
    if DDGS is None:
        return f"[HEADLESS] Motor no disponible. Instala: pip install ddgs"
    print(f"[HEADLESS] Buscando en DDG: '{query}'")
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            ddgs_inst = DDGS()
            results = list(ddgs_inst.text(query, max_results=max(max_results, 5)))

        if not results:
            return f"No se encontraron resultados para: {query}"

        corpus = f"### Investigacion Web: '{query}'\n\n"

        # Always add body snippets first (guaranteed content)
        for i, r in enumerate(results):
            title = r.get('title', 'Sin titulo')
            body  = r.get('body', '')
            href  = r.get('href', '')
            corpus += f"[{i+1}] {title}\n"
            if body:
                corpus += f"{body}\n"
            corpus += f"Fuente: {href}\n{'-'*40}\n"

        # Deep-scrape up to 2 URLs for richer content
        scraped = 0
        for r in results:
            if scraped >= 2:
                break
            href = r.get('href', '')
            if not href:
                continue
            try:
                extracted = extract_text_from_url(href, truncate_len=1500)
                if extracted and len(extracted) > 200:
                    corpus += f"\n--- Contenido extraido de {href} ---\n{extracted}\n"
                    scraped += 1
            except Exception:
                continue

        return corpus
    except Exception as e:
        return f"[HEADLESS] Error en motor web: {e}"
def search_youtube(query, max_results=5):
    """
    YouTube Expert V36.9.2 (ddgs fix): Universal Search with requests-fallback.
    Resistant to DDG 403 Ratelimits.
    """
    print(f"[YOUTUBE] Buscando videos (Universal Engine): '{query}'")
    try:
        if DDGS is None:
            raise ImportError("DDGS no disponible")
        results = []
        ddgs_inst = DDGS()
        search_query = f"{query} site:youtube.com"
        vids = list(ddgs_inst.text(search_query, max_results=max_results + 3))
        
        for v in vids:
            href = v.get("href", "")
            if "youtube.com/watch" in href or "youtu.be" in href:
                results.append({
                    "title": v.get("title", "Video Sin Titulo"),
                    "url": href,
                    "uploader": "YouTube",
                    "description": v.get("body", "")
                })
            if len(results) >= max_results: break
    
        if not results:
            # Fallback 1: Direct requests scrape (Silencioso)
            print("[YOUTUBE] DDG bloqueado. Activando Fallback 1: Scrape directo...")
            fallback_res = get_youtube_via_requests(query, max_results)
            if fallback_res: return fallback_res
            
        return results
    except Exception as e:
        if "403" in str(e):
            print("[YOUTUBE] Ratelimit detectado. Usando Fallback 1...")
            return get_youtube_via_requests(query, max_results)
        print(f"[ERR] Search Youtube Universal Engine: {e}")
        return get_youtube_via_requests(query, max_results)

def get_youtube_via_requests(query, max_results=5):
    """Crawl silencioso de YouTube results."""
    try:
        import requests
        import re
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'}
        url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
        response = requests.get(url, headers=headers, timeout=10)
        
        # Regex to find video IDs and titles in the raw HTML (ytInitialData)
        video_ids = re.findall(r"\"videoRenderer\":\{\"videoId\":\"(.*?)\"", response.text)
        titles = re.findall(r"\"title\":\{\"runs\":\[\{\"text\":\"(.*?)\"\}\]", response.text)
        
        results = []
        for i in range(min(len(video_ids), max_results)):
            results.append({
                "title": titles[i] if i < len(titles) else "Video",
                "url": f"https://www.youtube.com/watch?v={video_ids[i]}",
                "uploader": "YouTube (Direct)",
                "description": "Extraido via Fallback 1"
            })
        return results
    except:
        return []
