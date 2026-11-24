#!/usr/bin/env python3
"""
scripts/dev/prompt_compiler.py — Prompt and Persona Asset Compiler.

Compiles proprietary agent instructions and personas into encrypted binary bundles (.pfa)
using AES-256-GCM with HKDF-SHA256 key derivation.
Also provides the release packaging leak detection gate (AC-2: zero readable prompt files).
"""

from __future__ import annotations

import argparse
import json
import os
import struct
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

MAGIC_HEADER = b"PFA1"
BUNDLE_VERSION = 1
SALT_LENGTH = 16
NONCE_LENGTH = 12
HEADER_LENGTH = 4 + 2 + SALT_LENGTH + NONCE_LENGTH  # 34 bytes
INFO_STRING = b"PFA1-AES256GCM"


def derive_key(master_key: bytes, salt: bytes, info: bytes = INFO_STRING) -> bytes:
    """Derive a 32-byte (256-bit) AES key using HKDF-SHA256."""
    if not master_key:
        raise ValueError("prompt_compiler: master key cannot be empty")
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt if salt else b"\x00" * 32,
        info=info,
    )
    return hkdf.derive(master_key)


def compile_bundle(
    entries: Dict[str, str],
    master_key: bytes,
    salt: Optional[bytes] = None,
) -> bytes:
    """
    Compile a dictionary of prompt/persona files into an encrypted binary bundle.
    Layout: [Magic(4)][Version(2)][Salt(16)][Nonce(12)][Ciphertext + GCM Tag]
    """
    if not master_key:
        raise ValueError("prompt_compiler: master key cannot be empty")

    if salt is None:
        salt = os.urandom(SALT_LENGTH)
    elif len(salt) != SALT_LENGTH:
        raise ValueError(f"prompt_compiler: salt must be exactly {SALT_LENGTH} bytes")

    key = derive_key(master_key, salt)
    aesgcm = AESGCM(key)
    nonce = os.urandom(NONCE_LENGTH)

    payload = json.dumps(entries, ensure_ascii=False, sort_keys=True).encode("utf-8")
    aad = MAGIC_HEADER + struct.pack(">H", BUNDLE_VERSION)
    ciphertext = aesgcm.encrypt(nonce, payload, aad)

    header = MAGIC_HEADER + struct.pack(">H", BUNDLE_VERSION) + salt + nonce
    return header + ciphertext


def unpack_bundle_header(bundle_data: bytes) -> Tuple[bytes, bytes, bytes]:
    """Validate magic header and extract salt, nonce, and ciphertext."""
    if len(bundle_data) < HEADER_LENGTH + 16:
        raise ValueError("prompt_compiler: bundle too short or corrupted")

    magic = bundle_data[:4]
    if magic != MAGIC_HEADER:
        raise ValueError(f"prompt_compiler: invalid magic header: {magic!r}")

    version = struct.unpack(">H", bundle_data[4:6])[0]
    if version != BUNDLE_VERSION:
        raise ValueError(f"prompt_compiler: unsupported version: {version}")

    salt = bundle_data[6 : 6 + SALT_LENGTH]
    nonce = bundle_data[6 + SALT_LENGTH : HEADER_LENGTH]
    ciphertext = bundle_data[HEADER_LENGTH:]
    return salt, nonce, ciphertext


def decrypt_bundle(bundle_data: bytes, master_key: bytes) -> Dict[str, str]:
    """
    Transparently decrypt an asset bundle in-memory.
    Guarantees zero temporary disk writes or file leakage.
    """
    salt, nonce, ciphertext = unpack_bundle_header(bundle_data)
    key = derive_key(master_key, salt)
    aesgcm = AESGCM(key)

    aad = MAGIC_HEADER + struct.pack(">H", BUNDLE_VERSION)
    plaintext = aesgcm.decrypt(nonce, ciphertext, aad)
    return json.loads(plaintext.decode("utf-8"))


def compile_directory(dir_path: Path | str, master_key: bytes) -> bytes:
    """Walk a directory and compile all .md, .json, and .txt files into an encrypted bundle."""
    dir_p = Path(dir_path)
    if not dir_p.is_dir():
        raise FileNotFoundError(f"Directory not found: {dir_path}")

    entries: Dict[str, str] = {}
    for path in sorted(dir_p.rglob("*")):
        if path.is_file() and path.suffix.lower() in {".md", ".json", ".txt"}:
            rel = path.relative_to(dir_p).as_posix()
            entries[rel] = path.read_text(encoding="utf-8")

    return compile_bundle(entries, master_key)


def verify_no_plaintext_prompts(
    distribution_path: Path | str,
    fail_closed: bool = True,
) -> List[str]:
    """
    Release packaging scanner: ensures shipped customer distributions contain
    zero readable system prompt markdown files (AC-2).
    """
    dist_p = Path(distribution_path)
    if not dist_p.exists():
        return []

    leaks: List[str] = []
    # Identify prompt/persona patterns that should NEVER be shipped in plaintext
    prompt_indicators = ["persona", "system_prompt", "agent_instructions", "role_contract"]

    for path in dist_p.rglob("*"):
        if path.is_file():
            if path.suffix.lower() in {".md", ".prompt"}:
                # Check for sensitive prompt tokens
                content = path.read_text(encoding="utf-8", errors="ignore").lower()
                rel = path.relative_to(dist_p).as_posix()
                if any(ind in rel.lower() for ind in prompt_indicators) or any(
                    ind in content for ind in prompt_indicators
                ):
                    leaks.append(rel)

    if leaks and fail_closed:
        raise ValueError(
            f"RELEASE GATE FAILURE: Plaintext prompt files detected in customer distribution: {leaks}"
        )

    return leaks


# Binary Bundle Layout Schema v1 (PFA1):
# [Magic: 4 bytes "PFA1"][Version: 2 bytes uint16][Salt: 16 bytes][Nonce: 12 bytes][Ciphertext + 16-byte GCM Tag]
# Compatible with Go package productforge/promptcompiler (go/promptcompiler/compiler.go).


def resolve_compiler_config(config_path: Optional[Path | str] = None, allow_default_key: bool = True) -> dict:
    """Resolve compiler configuration, prompt directories, and master encryption key."""
    env_key = os.environ.get("PF_PROMPT_KEY")
    if not env_key:
        if not allow_default_key:
            raise ValueError("FAIL-CLOSED: PF_PROMPT_KEY environment variable is required for production asset compilation.")
        master_key = b"pf-default-asset-compiler-key-32"
    else:
        master_key = env_key.encode("utf-8")

    return {
        "master_key": master_key,
        "input_dir": Path("templates/prompts"),
        "output_bundle": Path("data/assets/prompts.pfa"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Prompt and Persona Asset Compiler")
    parser.add_argument("--compile", metavar="DIR", help="Compile directory of prompts into bundle")
    parser.add_argument("--output", "-o", metavar="OUT", default="prompts.pfa", help="Output bundle path")
    parser.add_argument("--verify", metavar="DIST_DIR", help="Verify no plaintext prompts in distribution")
    parser.add_argument("--key", help="Master encryption key (defaults to $PF_PROMPT_KEY)")

    args = parser.parse_args()

    key = (args.key or os.environ.get("PF_PROMPT_KEY", "pf-default-asset-compiler-key-32")).encode("utf-8")

    if args.verify:
        leaks = verify_no_plaintext_prompts(args.verify, fail_closed=False)
        if leaks:
            print(f"FAILED: Found {len(leaks)} plaintext prompt file(s) in distribution:")
            for leak in leaks:
                print(f"  - {leak}")
            return 1
        print("PASS: Zero plaintext prompt files detected in distribution payload.")
        return 0

    if args.compile:
        bundle = compile_directory(args.compile, key)
        out_p = Path(args.output)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_bytes(bundle)
        print(f"Compiled bundle ({len(bundle)} bytes) written to: {out_p}")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
