import sys
import os
import queue
import numpy as np

try:
    from faster_whisper import WhisperModel
except ImportError:
    print("ERROR: faster-whisper not installed")
    sys.exit(1)

def main():
    # Phase 103: Dedicated Offline STT Worker
    model_size = sys.argv[1] if len(sys.argv) > 1 else "tiny"
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    
    # Simple loop to read audio data from stdin and print transcript
    # (simplified for example, real implementation would use a protocol)
    print("READY")
    sys.stdout.flush()
    
    # This is a stub for the full worker logic
    # In a real scenario, we'd pass raw audio via stdin or socket
    pass

if __name__ == "__main__":
    main()
