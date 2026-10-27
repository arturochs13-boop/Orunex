"""
video_marketing_engine.py — Orunex Video & Social Marketing Master Engine V53.0
Motor SOTA de generación de video con IA, locución sintetizada (TTS) y marketing digital.

Capacidades:
  - Ensamblaje de imágenes IA fotorrealistas + Locución de voz real en español (gTTS)
  - Efecto Ken Burns (animación de cámara) + Tipografía ejecutiva animada
  - Formato vertical 9:16 (1080x1920) para Instagram Reels, TikTok y YouTube Shorts
  - Generación paralela de Notebook de Google Colab GPU para modelos SOTA (Wan2.1 / SVD)
"""
import os, sys, json, re, time, math, datetime
from PIL import Image, ImageDraw, ImageFont

def _progress(msg, cb=None):
    try:
        safe = str(msg).encode('ascii', errors='replace').decode('ascii')
        print(f"[VIDEO ENGINE V53] {safe}")
    except: pass
    if cb:
        try: cb(msg)
        except: pass

def _generate_marketing_script(topic: str) -> dict:
    """Genera el guión publicitario AIDA estructurado por escenas con locución."""
    try:
        from .ollama_client import call_ollama
        prompt = f"""Eres un director creativo de publicidad audiovisual para Instagram Reels y TikTok.
Crea un guión comercial AIDA para: '{topic}'.

Responde ÚNICAMENTE con un JSON con esta estructura:
{{
  "campaign_title": "Título de la campaña",
  "target_audience": "Público objetivo",
  "instagram_caption": "Texto para la publicación con emojis y llamado a la acción",
  "hashtags": ["#Hashtag1", "#Hashtag2", "#Hashtag3", "#Hashtag4", "#Hashtag5"],
  "scenes": [
    {{
      "scene_id": 1,
      "title": "¡ATENCIÓN! ¿BUSCAS AUTOMATIZAR?",
      "sub": "Tu empresa pierde tiempo en procesos manuales",
      "voiceover": "Si tu empresa sigue perdiendo tiempo en tareas manuales, necesitas una solución inteligente.",
      "image_prompt": "Futuristic cybernetic server room with glowing cyan data pulses, 9:16 vertical, photorealistic 8k",
      "duration_sec": 4
    }},
    {{
      "scene_id": 2,
      "title": "DESCUBRE CLOUDPULSE AI",
      "sub": "Monitoreo inteligente en tiempo real",
      "voiceover": "Descubre CloudPulse AI, la plataforma de monitoreo y análisis predictivo en tiempo real.",
      "image_prompt": "Futuristic AI data analytics dashboard hovering in dark space, glowing 3D charts, 9:16 vertical",
      "duration_sec": 4
    }},
    {{
      "scene_id": 3,
      "title": "¡PRUÉBALO GRATIS HOY!",
      "sub": "Link en la bio | Registra tu demo",
      "voiceover": "Escala tu negocio hoy mismo. Toca el enlace en nuestra bio y prueba la demo gratuita.",
      "image_prompt": "Confident tech leader looking at holographic metrics on smartphone, modern glass office, 9:16 vertical",
      "duration_sec": 4
    }}
  ]
}}"""
        res = call_ollama("orunex_v37", prompt, options={"temperature": 0.1})
        raw = res.get("response", "{}")
        if "</think>" in raw: raw = raw.split("</think>")[-1].strip()
        raw = re.sub(r'```json|```', '', raw).strip()
        start = raw.find("{")
        if start != -1: raw = raw[start:]
        return json.loads(raw)
    except Exception as e:
        _progress(f"⚠️ Usando guión publicitario experto ({e})")
        return {
            "campaign_title": f"Lanzamiento de Alto Impacto: {topic}",
            "target_audience": "Emprendedores, Directores de Tecnología y PYMEs",
            "instagram_caption": f"🚀 ¡Revoluciona tus procesos con {topic}! Automatiza, monitorea y escala al siguiente nivel con Inteligencia Artificial. 📲 Toca el enlace en la bio para obtener tu demo.",
            "hashtags": ["#AI", "#Tech", "#Productividad", "#SaaS", "#FuturoDigital"],
            "scenes": [
                {
                    "scene_id": 1,
                    "title": "¿SIGUES PERDIENDO TIEMPO?",
                    "sub": "Descubre la potencia de la Inteligencia Artificial",
                    "voiceover": f"Si buscas escalar {topic}, necesitas una plataforma inteligente y automatizada.",
                    "duration_sec": 4
                },
                {
                    "scene_id": 2,
                    "title": "RESULTADOS EN TIEMPO REAL",
                    "sub": "Análisis predictivo e integración instantánea",
                    "voiceover": "Monitorea tu infraestructura en tiempo real con alertas predictivas y máxima seguridad.",
                    "duration_sec": 4
                },
                {
                    "scene_id": 3,
                    "title": "¡COMIENZA HOY MISMO!",
                    "sub": "Link en la bio | Prueba gratuita 14 días",
                    "voiceover": "Toca el enlace en nuestra biografía y comienza tu prueba gratuita hoy mismo.",
                    "duration_sec": 4
                }
            ]
        }

def _create_audio_voiceover(text: str, out_path: str) -> bool:
    """Genera una locución de voz real en español usando gTTS."""
    try:
        from gtts import gTTS
        tts = gTTS(text=text, lang='es', slow=False)
        tts.save(out_path)
        return True
    except Exception as e:
        _progress(f"⚠️ Fallo TTS ({e})")
        return False

def _render_master_video(scenes: list, keyframe_images: list, out_dir: str, cb=None) -> str:
    """Compila las escenas con imágenes fotorrealistas + locución sintetizada en un video MP4 9:16."""
    # Soporte para MoviePy 2.x (API directa) y 1.x (moviepy.editor)
    try:
        from moviepy import ImageClip, AudioFileClip, concatenate_videoclips
    except ImportError:
        try:
            from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
        except ImportError:
            _progress("X MoviePy no disponible para renderizado local.", cb)
            return ""

    W, H = 1080, 1920
    fps = 30
    temp_dir = os.path.join(out_dir, "temp_video_assets")
    os.makedirs(temp_dir, exist_ok=True)

    clips = []
    _progress("Generando locuciones de voz e imagenes animadas por escena...", cb)

    for idx, scene in enumerate(scenes):
        title  = str(scene.get("title",     f"Escena {idx+1}"))
        sub    = str(scene.get("sub",        ""))
        vo_text = scene.get("voiceover", f"Descubre {title}")

        # --- 1. Voiceover TTS ---
        audio_path = os.path.join(temp_dir, f"vo_{idx}.mp3")
        has_audio  = _create_audio_voiceover(vo_text, audio_path)

        duration   = float(scene.get("duration_sec", 4))
        audio_clip = None
        if has_audio and os.path.exists(audio_path):
            try:
                audio_clip = AudioFileClip(audio_path)
                duration   = max(3.5, audio_clip.duration + 0.5)
            except Exception as ae:
                _progress(f"Audio load warning: {ae}", cb)

        # --- 2. Keyframe Image ---
        img_path = keyframe_images[idx % len(keyframe_images)] if keyframe_images else None

        if img_path and os.path.exists(img_path):
            img = Image.open(img_path).convert("RGB")
            img = img.resize((W, H), Image.Resampling.LANCZOS)
        else:
            # Dark Navy Gradient fallback
            img = Image.new("RGB", (W, H), color=(15, 23, 42))

        # --- 3. Overlay Typography (PIL) ---
        draw = ImageDraw.Draw(img, "RGBA")

        # Vignette overlay at bottom
        draw.rectangle([0, H - 550, W, H], fill=(10, 16, 38, 210))

        # Title text (top center)
        try:
            font_title = ImageFont.truetype("arial.ttf", size=64)
            font_sub   = ImageFont.truetype("arial.ttf", size=36)
        except IOError:
            font_title = ImageFont.load_default()
            font_sub   = ImageFont.load_default()

        # Draw white title with drop shadow
        tx, ty = 60, H - 500
        draw.text((tx + 2, ty + 2), title, fill=(0, 0, 0, 180), font=font_title)
        draw.text((tx, ty), title, fill=(255, 255, 255, 255), font=font_title)

        # Draw subtitle
        sx, sy = 60, ty + 85
        draw.text((sx, sy), sub, fill=(180, 200, 255, 230), font=font_sub)

        # Brand watermark
        try:
            font_brand = ImageFont.truetype("arial.ttf", size=26)
        except IOError:
            font_brand = ImageFont.load_default()
        draw.text((W - 220, H - 70), "ORUNEX AI", fill=(100, 150, 255, 180), font=font_brand)

        # Scene progress indicator (dot bar)
        dot_total = len(scenes)
        dot_w = 20
        dot_gap = 12
        bar_total_w = dot_total * dot_w + (dot_total - 1) * dot_gap
        bar_x = (W - bar_total_w) // 2
        bar_y = H - 100
        for di in range(dot_total):
            col = (100, 160, 255, 255) if di == idx else (80, 80, 120, 180)
            draw.ellipse(
                [bar_x + di * (dot_w + dot_gap), bar_y,
                 bar_x + di * (dot_w + dot_gap) + dot_w, bar_y + dot_w],
                fill=col
            )

        # --- 4. Save frame ---
        frame_file = os.path.join(temp_dir, f"frame_{idx}.png")
        img.save(frame_file)

        # --- 5. Build MoviePy Clip ---
        try:
            # MoviePy 2.x API
            img_clip = ImageClip(frame_file, duration=duration)

            # Ken Burns subtle zoom (scale from 1.0 to 1.06 over the clip)
            def make_resize(dur):
                return lambda t: 1.0 + 0.06 * (t / dur)
            img_clip = img_clip.resized(make_resize(duration))

            if audio_clip:
                img_clip = img_clip.with_audio(audio_clip)

        except Exception as e1:
            # MoviePy 1.x fallback
            try:
                img_clip = ImageClip(frame_file).set_duration(duration)
                img_clip = img_clip.resize(lambda t: 1 + 0.06 * (t / duration))
                if audio_clip:
                    img_clip = img_clip.set_audio(audio_clip)
            except Exception as e2:
                _progress(f"Clip creation error: {e2}", cb)
                continue

        clips.append(img_clip)
        _progress(f"  Scene {idx+1}/{len(scenes)} ready ({duration:.1f}s)", cb)

    if not clips:
        _progress("X No clips assembled — aborting render.", cb)
        return ""

    _progress("Concatenando escenas y renderizando comercial final MP4...", cb)
    try:
        final_clip = concatenate_videoclips(clips, method="compose")
    except Exception as ce:
        _progress(f"Concatenation error: {ce}", cb)
        return ""

    out_file = os.path.join(out_dir, f"Orunex_AI_Commercial_{int(time.time())}.mp4")
    try:
        final_clip.write_videofile(
            out_file,
            fps=fps,
            codec="libx264",
            audio_codec="aac",
            preset="ultrafast",
            logger=None
        )
        _progress(f"[OK] Commercial MP4 renderizado: {os.path.basename(out_file)}", cb)
    except Exception as we:
        _progress(f"Write error: {we}", cb)
        return ""

    return out_file

def generate_social_video_campaign(topic: str, out_dir: str, prefer_colab: bool = False, progress_cb=None) -> dict:
    """
    Motor Maestro de Marketing en Video V53.0
    Genera un paquete completo de campaña publicitaria:
    1. Guión AIDA con locución en español
    2. Renderizado local de video MP4 9:16 con imágenes IA y audio TTS
    3. Notebook de Google Colab GPU (.ipynb) para difusión SOTA (Wan2.1 / SVD)
    4. Estrategia para redes sociales (Instagram Reels / TikTok)
    """
    _progress(f"🎬 Iniciando Motor de Marketing en Video V53.0 para: '{topic}'", progress_cb)

    # 1. AI Scripting
    script = _generate_marketing_script(topic)
    scenes = script.get("scenes", [])

    # 2. Check for AI keyframe images in artifacts or current folder
    brain_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".gemini", "antigravity", "brain"))
    keyframe_images = []
    if os.path.exists(brain_dir):
        for root, dirs, files in os.walk(brain_dir):
            for f in files:
                if f.startswith("scene") and f.endswith(".jpg"):
                    keyframe_images.append(os.path.join(root, f))

    # 3. Render Master Video Local MP4 with Voiceover Audio
    os.makedirs(out_dir, exist_ok=True)
    video_path = _render_master_video(scenes, keyframe_images, out_dir, progress_cb)

    # 4. Generate Google Colab GPU Notebook
    _progress("⚡ Generando Notebook de Google Colab GPU para difusores SOTA...", progress_cb)
    from .colab_master import generate_colab_notebook
    colab_path = generate_colab_notebook(topic, "AI Video Render 9:16", out_dir)

    # 5. Package Campaign Dossier
    campaign = {
        "topic": topic,
        "campaign_title": script.get("campaign_title", f"Campaña: {topic}"),
        "target_audience": script.get("target_audience", "Público General"),
        "instagram_caption": script.get("instagram_caption", ""),
        "hashtags": " ".join(script.get("hashtags", [])),
        "video_mp4_path": video_path,
        "colab_notebook_path": colab_path,
        "scenes": scenes
    }

    safe_topic = "".join(c for c in topic[:25].replace(" ", "_") if c.isalnum() or c == "_")
    json_path = os.path.join(out_dir, f"Campaign_{safe_topic}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(campaign, f, indent=2, ensure_ascii=False)

    return campaign
