"""
social_media.py — Social Media Browser Automation for Orunex
Uses pyautogui + subprocess to open browsers and interact with social networks.
Triggered by [SOCIAL: network="X" action="post" text="..."] tags.
"""
import subprocess
import pyautogui  # type: ignore
import time
import os
import webbrowser


NETWORKS = {
    "twitter":    "https://x.com",
    "x":          "https://x.com",
    "instagram":  "https://www.instagram.com",
    "linkedin":   "https://www.linkedin.com",
    "facebook":   "https://www.facebook.com",
    "tiktok":     "https://www.tiktok.com",
    "youtube":    "https://www.youtube.com",
    "reddit":     "https://www.reddit.com",
    "whatsapp":   "https://web.whatsapp.com",
    "telegram":   "https://web.telegram.org",
}


def _open_url(url: str):
    """Open URL in default browser."""
    webbrowser.open(url)
    time.sleep(3)  # Wait for browser to load


def open_network(name: str) -> str:
    """Open a social network in the browser."""
    key = name.strip().lower()
    url = NETWORKS.get(key)
    if not url:
        return f"Red social desconocida: '{name}'. Redes disponibles: {', '.join(NETWORKS.keys())}"
    _open_url(url)
    return f"Abriendo {name.title()} en el navegador..."


def post_twitter(text: str) -> str:
    """
    Attempt to compose a tweet on X.com.
    Requires the user to already be logged in to X in their browser.
    """
    _open_url("https://x.com/compose/tweet")
    time.sleep(4)
    try:
        pyautogui.click(pyautogui.size()[0] // 2, pyautogui.size()[1] // 2)
        time.sleep(0.5)
        pyautogui.typewrite(text[:280], interval=0.04)
        return (
            f"Tweet redactado: \"{text[:50]}...\"\n"
            "Revisa el navegador y confirma el post manualmente o dime 'publicar'."
        )
    except Exception as e:
        return f"Error redactando tweet: {e}"


def publish_tweet() -> str:
    """Press Ctrl+Enter to post the composed tweet."""
    try:
        pyautogui.hotkey('ctrl', 'enter')
        return "Tweet publicado."
    except Exception as e:
        return f"Error publicando tweet: {e}"


def search_on_network(network: str, query: str) -> str:
    """Search on a social network."""
    urls = {
        "twitter": f"https://x.com/search?q={query.replace(' ', '+')}",
        "x":       f"https://x.com/search?q={query.replace(' ', '+')}",
        "youtube": f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}",
        "reddit":  f"https://www.reddit.com/search/?q={query.replace(' ', '+')}",
        "linkedin":f"https://www.linkedin.com/search/results/all/?keywords={query.replace(' ', '+')}",
    }
    url = urls.get(network.lower(), NETWORKS.get(network.lower(), "https://google.com") + f"?q={query}")
    webbrowser.open(url)
    return f"Buscando '{query}' en {network.title()}..."


def send_whatsapp(contact: str, message: str) -> str:
    """Open WhatsApp Web with a pre-filled message."""
    encoded = message.replace(' ', '%20')
    url = f"https://web.whatsapp.com/send?phone={contact}&text={encoded}"
    webbrowser.open(url)
    return f"WhatsApp Web abierto para {contact}. Confirma el envío manualmente."


def execute(network: str, action: str, text: str = "", query: str = "", contact: str = "") -> str:
    """
    Unified entry point for social media commands.
    network: twitter|x|instagram|linkedin|facebook|tiktok|youtube|reddit|whatsapp|telegram
    action:  open | post | search | publish | send
    """
    net = network.strip().lower()
    act = action.strip().lower()

    if act in ("open", "abrir", "ir", "navegar"):
        return open_network(net)
    elif act in ("post", "publicar", "tweet", "twittear") and net in ("twitter", "x"):
        return post_twitter(text)
    elif act in ("confirm", "send_tweet", "publish", "enviar_tweet"):
        return publish_tweet()
    elif act in ("search", "buscar"):
        return search_on_network(net, query or text)
    elif act in ("send", "mensaje", "message") and net in ("whatsapp",):
        return send_whatsapp(contact, text)
    else:
        return open_network(net)
