"""Publish the browser edition to GitHub Pages (branch gh-pages).

    python scripts/publish_pages.py

Builds the static site and force-pushes it as the only commit of the gh-pages branch of this
repository's `origin`. Site address: https://<user>.github.io/<repo>/
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_static import ROOT, build  # noqa: E402


def git(*args: str, cwd: Path) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


def main() -> None:
    remote = git("remote", "get-url", "origin", cwd=ROOT)
    commit = git("rev-parse", "--short", "HEAD", cwd=ROOT)
    with tempfile.TemporaryDirectory(prefix="ahdaf-pages-") as tmp:
        site = build(Path(tmp) / "site")
        git("init", "-q", "-b", "gh-pages", cwd=site)
        for key in ("user.name", "user.email"):
            value = git("config", key, cwd=ROOT)
            git("config", key, value, cwd=site)
        git("add", "-A", cwd=site)
        git("commit", "-q", "-m", f"Publish browser edition from {commit}", cwd=site)
        subprocess.check_call(["git", "push", "-q", "-f", remote, "gh-pages"], cwd=site)
    owner_repo = remote.rstrip("/").removesuffix(".git").split("github.com/")[-1]
    owner, repo = owner_repo.split("/")[-2:]
    print(f"published -> https://{owner}.github.io/{repo}/")


if __name__ == "__main__":
    main()
