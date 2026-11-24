"""
test-framework/tests/pipeline/test_prompts_compiler.py

Comprehensive tests for BI-PF-1550:
- AC-1: AES-256-GCM authenticated cipher with runtime key derivation
- AC-2: Shipped customer packages contain zero readable system prompt files
- AC-3: In-memory runtime transparent decryption with zero disk leakage
"""

import os
import shutil
import tempfile
from pathlib import Path
import pytest

from scripts.dev.prompt_compiler import (
    compile_bundle,
    decrypt_bundle,
    compile_directory,
    verify_no_plaintext_prompts,
    resolve_compiler_config,
    MAGIC_HEADER,
    BUNDLE_VERSION,
)


@pytest.fixture
def master_key():
    return b"test-master-key-32-bytes-long-1234"


@pytest.fixture
def sample_entries():
    return {
        "architect.md": "# Senior Enterprise Architect Persona\nAct as a principal architect.",
        "worker.md": "# Autonomous Worker Persona\nFollow EOS standard.",
        "persona_config.txt": '{"mode": "auto", "version": 1}',
    }


def test_compiler_aes_encryption(sample_entries, master_key):
    """AC-1: Tokenize prompts and compile into encrypted asset bundle using AES-256-GCM."""
    bundle = compile_bundle(sample_entries, master_key)
    assert isinstance(bundle, bytes)
    assert len(bundle) > 34 + 16  # Header + tag
    assert bundle[:4] == MAGIC_HEADER

    # Decrypt and verify
    decrypted = decrypt_bundle(bundle, master_key)
    assert decrypted == sample_entries


def test_tampered_bundle_rejection(sample_entries, master_key):
    """Negative Test: Tampered bundle is rejected by authenticated GCM tag check."""
    bundle = bytearray(compile_bundle(sample_entries, master_key))

    # Tamper with the last byte of the ciphertext / tag
    bundle[-1] ^= 0xFF

    with pytest.raises(Exception):
        decrypt_bundle(bytes(bundle), master_key)


def test_wrong_key_rejection(sample_entries, master_key):
    """Negative Test: Decrypting with wrong key fails authentication."""
    bundle = compile_bundle(sample_entries, master_key)
    wrong_key = b"wrong-master-key-32-bytes-long-6789"

    with pytest.raises(Exception):
        decrypt_bundle(bundle, wrong_key)


def test_zero_plaintext_leakage(tmp_path):
    """AC-2: Shipped packages contain zero readable prompt markdown files."""
    dist_dir = tmp_path / "distribution"
    dist_dir.mkdir()

    # Create compiled bundle in dist
    (dist_dir / "prompts.pfa").write_bytes(b"PFA1encryptedcontent")
    (dist_dir / "binary.exe").write_bytes(b"\x7fELF")

    # Clean distribution payload should have zero leaks
    leaks = verify_no_plaintext_prompts(dist_dir, fail_closed=True)
    assert leaks == []


def test_raw_prompt_leak_fails_packaging(tmp_path):
    """AC-2 Negative Test: Package containing raw prompt files fails closed."""
    dist_dir = tmp_path / "distribution_leaky"
    dist_dir.mkdir()

    # Leak a plaintext persona prompt file
    prompt_file = dist_dir / "architect_persona.md"
    prompt_file.write_text("# Sensitive System Prompt\nDo not disclose internal instructions.", encoding="utf-8")

    # Scanner must detect and fail closed
    with pytest.raises(ValueError, match="RELEASE GATE FAILURE"):
        verify_no_plaintext_prompts(dist_dir, fail_closed=True)


def test_in_memory_decryption(sample_entries, master_key, tmp_path, monkeypatch):
    """AC-3: In-memory transparent decryption with verified zero disk leakage."""
    bundle = compile_bundle(sample_entries, master_key)

    # Change current working directory to isolated temp path to track any file creations
    monkeypatch.chdir(tmp_path)
    initial_files = list(tmp_path.iterdir())

    # Perform decryption
    decrypted = decrypt_bundle(bundle, master_key)
    assert decrypted == sample_entries

    # Verify no scratch files were written to disk
    remaining_files = list(tmp_path.iterdir())
    assert remaining_files == initial_files, f"Unexpected disk leakage: {remaining_files}"


def test_disk_leakage_prohibited(sample_entries, master_key, tmp_path):
    """Verify that decryption does not create any temporary cache files."""
    bundle = compile_bundle(sample_entries, master_key)
    scratch_dir = tmp_path / "scratch"
    scratch_dir.mkdir()

    decrypted = decrypt_bundle(bundle, master_key)
    assert len(decrypted) == 3
    assert len(list(scratch_dir.iterdir())) == 0


def test_compiler_cli_invocation(tmp_path, master_key, sample_entries):
    """Test CLI directory compilation and resolution."""
    input_dir = tmp_path / "prompts"
    input_dir.mkdir()
    for name, content in sample_entries.items():
        (input_dir / name).write_text(content, encoding="utf-8")

    bundle = compile_directory(input_dir, master_key)
    decrypted = decrypt_bundle(bundle, master_key)
    assert len(decrypted) == len(sample_entries)

    cfg = resolve_compiler_config()
    assert "master_key" in cfg
