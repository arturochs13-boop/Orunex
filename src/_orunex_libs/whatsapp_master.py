"""
whatsapp_master.py — Orunex WhatsApp Web Master Engine V53.0
Permite a Orunex enviar mensajes a contactos específicos a través de WhatsApp Web o la App de WhatsApp.
"""
import os
import sys
import time
import urllib.parse
import webbrowser
import pyautogui # type: ignore

def send_whatsapp_message(contact_or_number: str, message: str) -> dict:
    """
    Envía un mensaje a un contacto o número telefónico vía WhatsApp.
    1. Si es un número (ej. +521234567890 o 1234567890), usa la API api.whatsapp.com/send
    2. Si es el nombre de un contacto, abre WhatsApp Web/Desktop y usa automatización UI
    """
    clean_target = contact_or_number.strip()
    clean_msg = message.strip()
    
    # Comprobar si es número telefónico (contiene principalmente dígitos y opcional +)
    digits = "".join(c for c in clean_target if c.isdigit())
    
    if len(digits) >= 10:
        # Enviar vía URL Directa de WhatsApp Web
        encoded_msg = urllib.parse.quote(clean_msg)
        wa_url = f"https://web.whatsapp.com/send?phone={digits}&text={encoded_msg}"
        
        webbrowser.open(wa_url)
        time.sleep(8) # Esperar a que cargue la interfaz de WhatsApp Web
        
        # Presionar ENTER para enviar
        pyautogui.press('enter')
        time.sleep(1)
        return {
            "status": "success",
            "method": "direct_url",
            "target": digits,
            "message": clean_msg,
            "detail": f"Mensaje enviado con éxito al número {digits} vía WhatsApp Web."
        }
    else:
        # Enviar buscando por nombre de contacto en WhatsApp Web
        webbrowser.open("https://web.whatsapp.com")
        time.sleep(7)
        
        # Buscar cuadro de búsqueda (Ctrl + F o Ctrl + Alt + /)
        pyautogui.hotkey('ctrl', 'alt', '/')
        time.sleep(1)
        
        # Escribir nombre del contacto
        pyautogui.write(clean_target, interval=0.05)
        time.sleep(2)
        pyautogui.press('enter')
        time.sleep(1.5)
        
        # Escribir el mensaje
        pyautogui.write(clean_msg, interval=0.03)
        time.sleep(1)
        pyautogui.press('enter')
        
        return {
            "status": "success",
            "method": "contact_search",
            "target": clean_target,
            "message": clean_msg,
            "detail": f"Mensaje enviado con éxito al contacto '{clean_target}' en WhatsApp Web."
        }
