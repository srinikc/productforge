"""IS-PF-0049: connect_remote must NOT mutate an ancestor (framework) repo's remote.

A product dir with no ``.git`` is inside the framework repo, so ``is_repo()`` is true but the
remote must not be changed there; only a repo that IS its own root may be connected.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.vcs import VCSManager  # noqa: E402


def _git(d, *a):
    return subprocess.run(["git", *a], cwd=d, capture_output=True, text=True)


def test_connect_remote_refuses_ancestor_repo():
    root = tempfile.mkdtemp()
    try:
        _git(root, "init", "-q")
        _git(root, "config", "user.email", "t@local")
        _git(root, "config", "user.name", "t")
        _git(root, "remote", "add", "origin", "https://example.com/framework.git")

        prod = os.path.join(root, "products", "P")
        os.makedirs(prod, exist_ok=True)

        v = VCSManager(prod)
        assert v.is_repo() is True
        assert v.is_own_repo() is False
        r = v.connect_remote("https://example.com/product.git")
        assert r.get("ok") is False, "must refuse to set the remote on an ancestor repo"
        assert _git(root, "remote", "get-url", "origin").stdout.strip() == \
            "https://example.com/framework.git", "framework remote must be unchanged"

        v2 = VCSManager(root)
        assert v2.is_own_repo() is True
        r2 = v2.connect_remote("https://example.com/framework2.git")
        assert r2.get("ok") is True
        assert _git(root, "remote", "get-url", "origin").stdout.strip() == \
            "https://example.com/framework2.git"
    finally:
        shutil.rmtree(root, ignore_errors=True)
