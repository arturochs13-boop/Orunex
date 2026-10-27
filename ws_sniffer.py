import websocket
import json
import time

def on_message(ws, message):
    data = json.loads(message)
    print(f"RAW WS EVENT: {json.dumps(data, indent=2)}")
    with open("simplex_raw_log.json", "a") as f:
        f.write(json.dumps(data) + "\n")

def on_error(ws, error):
    print(f"WS ERROR: {error}")

def on_close(ws, close_status_code, close_msg):
    print("WS CLOSED")

def on_open(ws):
    print("WS CONNECTED - SNIFFER STARTING...")
    # Trigger /sa to force an event for invite link
    ws.send(json.dumps({"corrId": "sniffer", "cmd": "/sa"}))

if __name__ == "__main__":
    ws = websocket.WebSocketApp("ws://127.0.0.1:5227",
                              on_open=on_open,
                              on_message=on_message,
                              on_error=on_error,
                              on_close=on_close)
    
    print("Sniffing Simplex traffic on port 5227 for 30s...")
    import threading
    ws_thread = threading.Thread(target=ws.run_forever)
    ws_thread.daemon = True
    ws_thread.start()
    
    time.sleep(30)
    ws.close()
    print("Sniffer finished. Check simplex_raw_log.json")
