import os
import sys
import base64
import re
import mss
import pyautogui
import time
from PIL import Image
from io import BytesIO

# Path setup
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.append(PROJECT_ROOT)

_VISION_MODEL = None
_VISION_TOKENIZER = None

def get_vision_model():
    """Lazy-loads local Moondream2 using transformers on CUDA/CPU directly."""
    global _VISION_MODEL, _VISION_TOKENIZER
    if _VISION_MODEL is None:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        
        model_id = "vikhyatk/moondream2"
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[VISION ENGINE] Loading Moondream2 model on {device} (100% local, no Ollama)...")
        
        _VISION_MODEL = AutoModelForCausalLM.from_pretrained(
            model_id, 
            trust_remote_code=True,
            revision="2024-08-26" # Locked revision for consistency
        ).to(device)
        _VISION_MODEL.eval()
        _VISION_TOKENIZER = AutoTokenizer.from_pretrained(model_id, revision="2024-08-26")
        print("[VISION ENGINE] Local Moondream2 model loaded successfully.")
        
    return _VISION_MODEL, _VISION_TOKENIZER

def take_fast_screenshot(monitor=1):
    """Captures the screen and returns a base64 encoded PNG."""
    with mss.mss() as sct:
        monitor_list = sct.monitors
        if monitor >= len(monitor_list):
            monitor = 1 # Fallback to primary
            
        screenshot = sct.grab(monitor_list[monitor])
        img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
        
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode("utf-8")

def skip_ads_intelligent(monitor=1):
    """
    SOVEREIGN UI CLEANER V40.4
    Scans for ads, banners, and skip buttons to clean the executive workspace.
    """
    targets = ["Skip Ad button", "Close button", "X icon in corner", "Accept cookies button", "No thanks button"]
    results = []
    
    for target in targets:
        coords = get_ui_coordinates(target, monitor)
        if coords:
            pyautogui.moveTo(coords[0], coords[1], duration=0.2)
            pyautogui.click()
            results.append(f"Elemento limpiado: {target}")
            time.sleep(0.5)
            
    return results or ["Pantalla ya despejada."]

def get_ui_coordinates(target_name, monitor=1):
    """
    Uses local Moondream2 via transformers to find the coordinates of a UI element.
    Returns (x, y) relative to the screen resolution.
    """
    try:
        b64_img = take_fast_screenshot(monitor)
        img_data = base64.b64decode(b64_img)
        img = Image.open(BytesIO(img_data))
        
        model, tokenizer = get_vision_model()
        
        prompt = f"Provide the center coordinates [x, y] of the '{target_name}' in a 0 to 1000 scale. If it's a small icon or button, be extremely precise. Format: [x, y]"
        
        # Run local inference
        enc_image = model.encode_image(img)
        output = model.answer_question(enc_image, prompt, tokenizer)
        
        print(f"[VISION ENGINE] Output for '{target_name}': {output}")
        
        match = re.search(r"\[(\d+),\s*(\d+)\]", output)
        if not match:
            match = re.search(r"(\d+),\s*(\d+)", output)
            
        if match:
            x_norm = int(match.group(1))
            y_norm = int(match.group(2))
            
            screen_w, screen_h = pyautogui.size()
            final_x = int((x_norm / 1000.0) * screen_w)
            final_y = int((y_norm / 1000.0) * screen_h)
            
            return final_x, final_y
    except Exception as e:
        print(f"[VISION ENGINE ERROR] Local UI coordinate detection failed: {e}")
        
    return None

if __name__ == "__main__":
    print("[TEST] Looking for Chrome Icon...")
    coords = get_ui_coordinates("Chrome icon")
    print(f"[TEST] Result: {coords}")
