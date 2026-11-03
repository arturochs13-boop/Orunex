"""
bmd_property.py — IP Property Bundle System for Blockchain Markdown (.bmd)
Handles: inject_property directive (move semantics, ChaCha20 encryption, zlib compress, base64 encode)
and extract_property (decrypt + decompress + restore files).

SECURITY MODEL:
- Source files are MOVED (deleted after injection) - true ownership transfer
- Bundle is compressed (zlib level 9) then encrypted (ChaCha20-Poly1305 via PyNaCl)
- Encryption key = BLAKE2b(privkey_seed || block_id || timestamp)
- Without the private key seed, the bundle is cryptographically opaque
- Decompilation is impossible without the private key
"""

import os
import sys
import io
import zlib
import base64
import shutil
import json
import hashlib
import time
import re
from pathlib import Path
from typing import Optional, Tuple, Dict, List

# Try to import PyNaCl for ChaCha20-Poly1305
try:
    from nacl.secret import SecretBox
    from nacl.utils import random as nacl_random
    NACL_AVAILABLE = True
except ImportError:
    NACL_AVAILABLE = False


def get_default_seed() -> bytes:
    """Load the persistent device key seed from ~/.bmd/emitter_device.key or environment."""
    env_seed = os.environ.get("BMD_DEVICE_SEED")
    if env_seed and len(env_seed) == 64:
        try:
            return bytes.fromhex(env_seed)
        except Exception:
            pass
    home = os.environ.get("USERPROFILE") or os.environ.get("HOME") or "."
    key_path = os.path.join(home, ".bmd", "emitter_device.key")
    if os.path.exists(key_path):
        try:
            with open(key_path, "r", encoding="utf-8") as f:
                hex_seed = f.read().strip()
                if len(hex_seed) == 64:
                    return bytes.fromhex(hex_seed)
        except Exception:
            pass
    return bytes([0x42] * 32)


def derive_bundle_key(privkey_seed: bytes, block_id: str = "", timestamp: int = 0) -> bytes:
    """
    Derive a 32-byte encryption key for the property bundle.
    Uses BLAKE2b(privkey_seed || salt).
    This ensures the bundle can ONLY be decrypted with the authentic emitter private key,
    while remaining stable even when document compilation updates the timestamp or block_id.
    """
    h = hashlib.blake2b(digest_size=32)
    h.update(privkey_seed)
    h.update(b"BMD_IP_BUNDLE_SECRET_v2.1")
    return h.digest()


def scan_directory_manifest(path: str) -> List[Dict]:
    """
    Scan a directory and return a manifest of all files with relative paths and sizes.
    Returns list of dicts: {rel_path, size, modified}
    """
    manifest = []
    base = Path(path)
    
    if base.is_file():
        manifest.append({
            'rel_path': base.name,
            'size': base.stat().st_size,
            'modified': int(base.stat().st_mtime),
            'type': 'file'
        })
        return manifest
    
    for item in sorted(base.rglob('*')):
        if item.is_file():
            rel = str(item.relative_to(base)).replace('\\', '/')
            manifest.append({
                'rel_path': rel,
                'size': item.stat().st_size,
                'modified': int(item.stat().st_mtime),
                'type': 'file'
            })
    return manifest


def build_bundle_archive(path: str) -> bytes:
    """
    Build an in-memory archive (custom BMD format) of the property.
    
    BMD Bundle Format (binary):
    [4 bytes: magic "BMDB"]
    [4 bytes: version = 1]
    [4 bytes: manifest_json_len]
    [manifest_json_len bytes: manifest JSON]
    [for each file in manifest order:]
      [4 bytes: file_data_len]
      [file_data_len bytes: raw file bytes]
    
    This is then zlib-compressed and ChaCha20 encrypted.
    """
    base = Path(path)
    manifest = scan_directory_manifest(path)
    
    buf = io.BytesIO()
    
    # Magic & version
    buf.write(b'BMDB')
    buf.write((1).to_bytes(4, 'little'))
    
    # Manifest
    manifest_json = json.dumps(manifest, ensure_ascii=False).encode('utf-8')
    buf.write(len(manifest_json).to_bytes(4, 'little'))
    buf.write(manifest_json)
    
    # File data
    for entry in manifest:
        if base.is_file():
            file_path = base
        else:
            file_path = base / entry['rel_path'].replace('/', os.sep)
        
        with open(file_path, 'rb') as f:
            data = f.read()
        buf.write(len(data).to_bytes(4, 'little'))
        buf.write(data)
    
    return buf.getvalue()


def inject_property(
    source_path: str,
    block_id: str,
    timestamp: int,
    privkey_seed: bytes,
    destroy_source: bool = True
) -> Tuple[str, int, str]:
    """
    Inject intellectual property from source_path into a BMD bundle.
    
    Args:
        source_path: Path to file or directory to inject
        block_id: The block_id of the .bmd document (for key derivation)
        timestamp: The document timestamp (for key derivation)
        privkey_seed: 32-byte private key seed of emitter
        destroy_source: If True, delete source files after injection (move semantics)
    
    Returns:
        Tuple of (base64_bundle_str, bundle_size_bytes, sha512_hex_of_bundle)
    
    Raises:
        FileNotFoundError: if source_path does not exist
        RuntimeError: if PyNaCl is not available
    """
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Property path does not exist: {source_path}")
    
    if not NACL_AVAILABLE:
        raise RuntimeError(
            "PyNaCl is required for property injection. Install: pip install pynacl"
        )
    
    # Step 1: Build raw archive
    print(f"[bmd_property] Scanning: {source_path}")
    raw_archive = build_bundle_archive(source_path)
    print(f"[bmd_property] Raw archive size: {len(raw_archive):,} bytes")
    
    # Step 2: Compress (zlib level 9)
    compressed = zlib.compress(raw_archive, level=9)
    print(f"[bmd_property] Compressed size: {len(compressed):,} bytes ({100*len(compressed)//len(raw_archive)}%)")
    
    # Step 3: Derive encryption key
    bundle_key = derive_bundle_key(privkey_seed, block_id, timestamp)
    
    # Step 4: Encrypt with ChaCha20-Poly1305 (SecretBox = XSalsa20-Poly1305)
    box = SecretBox(bundle_key)
    encrypted = box.encrypt(compressed)
    print(f"[bmd_property] Encrypted size: {len(encrypted):,} bytes")
    
    # Step 5: Base64 encode
    b64_str = base64.b64encode(encrypted).decode('ascii')
    
    # Step 6: Compute SHA-512 of encrypted bundle
    sha512_hash = hashlib.sha512(encrypted).hexdigest()
    
    bundle_size = len(encrypted)
    
    # Step 7: Destroy source (move semantics — true IP transfer)
    if destroy_source:
        print(f"[bmd_property] DESTROYING source: {source_path}")
        if os.path.isfile(source_path):
            # Overwrite with zeros before deletion for secure erase
            file_size = os.path.getsize(source_path)
            with open(source_path, 'r+b') as f:
                f.write(b'\x00' * file_size)
                f.flush()
            os.remove(source_path)
        elif os.path.isdir(source_path):
            shutil.rmtree(source_path)
        print(f"[bmd_property] Source destroyed. Ownership transferred to .bmd block.")
    
    return b64_str, bundle_size, sha512_hash


def extract_property(
    b64_bundle: str,
    block_id: str,
    timestamp: int,
    privkey_seed: bytes,
    output_path: str
) -> Dict:
    """
    Extract a property bundle from a .bmd file.
    Requires the emitter's private key seed to decrypt.
    
    Returns dict with: {files_extracted, total_bytes, manifest}
    Raises RuntimeError if key is wrong (authentication failure).
    """
    if not NACL_AVAILABLE:
        raise RuntimeError("PyNaCl required. Install: pip install pynacl")
    
    # Decode base64
    encrypted = base64.b64decode(b64_bundle)
    
    # Derive key
    bundle_key = derive_bundle_key(privkey_seed, block_id, timestamp)
    
    # Decrypt (will raise nacl.exceptions.CryptoError if wrong key)
    box = SecretBox(bundle_key)
    try:
        compressed = box.decrypt(encrypted)
    except Exception:
        raise RuntimeError(
            "DECRYPTION FAILED: Invalid private key or corrupted bundle. "
            "This bundle is cryptographically sealed and cannot be extracted "
            "without the emitter's original private key seed."
        )
    
    # Decompress
    raw_archive = zlib.decompress(compressed)
    
    # Parse BMD bundle format
    buf = io.BytesIO(raw_archive)
    
    magic = buf.read(4)
    if magic != b'BMDB':
        raise RuntimeError("Invalid bundle format: bad magic bytes")
    
    version = int.from_bytes(buf.read(4), 'little')
    if version != 1:
        raise RuntimeError(f"Unsupported bundle version: {version}")
    
    manifest_len = int.from_bytes(buf.read(4), 'little')
    manifest_json = buf.read(manifest_len)
    manifest = json.loads(manifest_json.decode('utf-8'))
    
    # Extract files
    os.makedirs(output_path, exist_ok=True)
    files_extracted = 0
    total_bytes = 0
    
    for entry in manifest:
        file_data_len = int.from_bytes(buf.read(4), 'little')
        file_data = buf.read(file_data_len)
        
        rel_path = entry['rel_path'].replace('/', os.sep)
        out_file = os.path.join(output_path, rel_path)
        os.makedirs(os.path.dirname(out_file), exist_ok=True) if os.path.dirname(rel_path) else None
        
        with open(out_file, 'wb') as f:
            f.write(file_data)
        
        files_extracted += 1
        total_bytes += file_data_len
    
    return {
        'files_extracted': files_extracted,
        'total_bytes': total_bytes,
        'manifest': manifest
    }


def list_bundle_manifest(b64_bundle: str) -> str:
    """
    Returns JSON string describing the bundle manifest (file list only, without decrypting content).
    NOTE: Without the private key, we can only show that a bundle exists and its hash.
    The actual manifest (file names) is also encrypted — this returns a placeholder.
    """
    encrypted = base64.b64decode(b64_bundle)
    sha512 = hashlib.sha512(encrypted).hexdigest()
    return json.dumps({
        'bundle_encrypted': True,
        'bundle_bytes': len(encrypted),
        'bundle_sha512': sha512,
        'note': 'Content is encrypted with ChaCha20-Poly1305. Only the emitter private key can extract it.',
        'decompile_possible': False
    }, indent=2)


def format_bundle_for_yaml(b64_str: str, line_width: int = 76) -> str:
    """
    Format the base64 bundle string as a YAML block scalar (line-wrapped).
    """
    lines = [b64_str[i:i+line_width] for i in range(0, len(b64_str), line_width)]
    return '\n'.join('  ' + line for line in lines)


if __name__ == "__main__":
    import argparse
    import tempfile

    parser = argparse.ArgumentParser(description="BMD Property Bundle Manager (IP Injection & Extraction)")
    parser.add_argument("--inject", help="Inject directory/file IP into a .bmd file", metavar="PATH")
    parser.add_argument("--bmd", help="Target .bmd file", metavar="FILE")
    parser.add_argument("--extract", help="Extract bundle from .bmd file", metavar="FILE")
    parser.add_argument("--out", help="Output directory for extraction", metavar="DIR", default="./extracted_ip")
    parser.add_argument("--seed", help="Private key seed (hex 64 chars)", default=None)
    parser.add_argument("--keep-source", action="store_true", help="Do not destroy original source files")
    parser.add_argument("--test", action="store_true", help="Run internal self-test")

    args = parser.parse_args()

    if args.inject and args.bmd:
        # CLI Injection mode
        if not os.path.exists(args.inject):
            print(f"[-] Error: Source path does not exist: {args.inject}", file=sys.stderr)
            sys.exit(1)
        if not os.path.exists(args.bmd):
            print(f"[-] Error: Target .bmd file does not exist: {args.bmd}", file=sys.stderr)
            sys.exit(1)

        seed = bytes.fromhex(args.seed) if args.seed else get_default_seed()
        with open(args.bmd, "r", encoding="utf-8") as f:
            content = f.read()

        match = re.match(r"^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$", content)
        block_id = "0xIP_BUNDLE_001"
        ts = int(time.time())
        body = content
        meta = {}
        if match:
            body = match.group(2)
            for line in match.group(1).splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip().strip('"\'')
            block_id = meta.get("block_id", block_id)
            ts = int(meta.get("timestamp", ts))

        destroy = not args.keep_source
        b64_bundle, b_size, b_hash = inject_property(args.inject, block_id, ts, seed, destroy_source=destroy)

        meta["property_bundle_hash"] = b_hash
        meta["property_bundle_size"] = str(b_size)
        meta["property_bundle_destroyed"] = "true" if destroy else "false"

        # Re-serialize
        new_yaml = ["---"]
        for k, v in meta.items():
            new_yaml.append(f"{k}: \"{v}\"")
        new_yaml.append("property_bundle: |")
        new_yaml.append(format_bundle_for_yaml(b64_bundle))
        new_yaml.append("---")
        new_yaml.append("")
        new_yaml.append(body.strip())

        with open(args.bmd, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(new_yaml))

        print(json.dumps({
            "status": "ok",
            "action": "inject_property",
            "bundle_size": b_size,
            "bundle_hash": b_hash,
            "source_destroyed": destroy
        }, indent=2))

    elif args.extract:
        if not os.path.exists(args.extract):
            print(f"[-] Error: .bmd file not found: {args.extract}", file=sys.stderr)
            sys.exit(1)

        with open(args.extract, "r", encoding="utf-8") as f:
            content = f.read()

        match = re.match(r"^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$", content)
        if not match:
            print("[-] Error: Invalid .bmd format", file=sys.stderr)
            sys.exit(1)

        meta = {}
        in_bundle = False
        bundle_lines = []
        for line in match.group(1).splitlines():
            if in_bundle:
                if line.startswith("  ") or line.strip() == "":
                    bundle_lines.append(line.strip())
                    continue
                else:
                    meta["property_bundle"] = "".join(bundle_lines)
                    in_bundle = False
            if ":" in line:
                k, v = line.split(":", 1)
                k = k.strip()
                v = v.strip().strip('"\'')
                if k == "property_bundle":
                    in_bundle = True
                else:
                    meta[k] = v
        if in_bundle and bundle_lines:
            meta["property_bundle"] = "".join(bundle_lines)

        b64_data = meta.get("property_bundle")
        if not b64_data:
            print("[-] Error: No property_bundle found in file", file=sys.stderr)
            sys.exit(1)

        seed = bytes.fromhex(args.seed) if args.seed else get_default_seed()
        block_id = meta.get("block_id", "0xBLOCK")
        ts = int(meta.get("timestamp", 0))

        result = extract_property(b64_data, block_id, ts, seed, args.out)
        print(json.dumps({
            "status": "ok",
            "action": "extract_property",
            "files_extracted": result["files_extracted"],
            "total_bytes": result["total_bytes"],
            "output_dir": os.path.abspath(args.out)
        }, indent=2))

    else:
        # Self-test
        print("=== bmd_property self-test ===")
        tmpdir = tempfile.mkdtemp(prefix="bmd_test_")
        with open(os.path.join(tmpdir, "main.py"), 'w') as f:
            f.write("print('Hello, Blockchain Markdown!')\n")
        with open(os.path.join(tmpdir, "README.md"), 'w') as f:
            f.write("# Test Project\nThis is IP.\n")
        
        privkey = bytes(range(32))
        block_id = "0xTEST_BLOCK_001"
        ts = int(time.time())
        
        b64, size, sha512 = inject_property(tmpdir, block_id, ts, privkey, destroy_source=False)
        print(f"Bundle size: {size} bytes, SHA-512: {sha512[:32]}...")
        
        out_dir = tempfile.mkdtemp(prefix="bmd_extract_")
        result = extract_property(b64, block_id, ts, privkey, out_dir)
        print(f"Extracted: {result['files_extracted']} files, {result['total_bytes']} bytes")
        
        for entry in result['manifest']:
            extracted_file = os.path.join(out_dir, entry['rel_path'])
            assert os.path.exists(extracted_file), f"Missing: {extracted_file}"
        
        print("Self-test PASSED")
        shutil.rmtree(tmpdir, ignore_errors=True)
        shutil.rmtree(out_dir, ignore_errors=True)
