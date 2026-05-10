"""Publish the React + FastAPI terminal to a Hugging Face Docker Space.

Requires either HF_TOKEN in the environment or a local Hugging Face login.
The upload bundle is intentionally selective so Shiny deployment metadata,
node_modules, caches, and generated test artifacts are never pushed.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


DEFAULT_REPO_ID = "jviola1019/mlb-show-investment-terminal"


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def copy_tree(src: Path, dst: Path) -> None:
    ignore = shutil.ignore_patterns(
        "node_modules",
        "dist",
        "test-results",
        "playwright-report",
        "__pycache__",
        "*.pyc",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
    )
    shutil.copytree(src, dst, ignore=ignore)


def build_bundle(root: Path, bundle: Path) -> None:
    copy_file(root / "huggingface" / "README.md", bundle / "README.md")
    copy_file(root / "Dockerfile.react", bundle / "Dockerfile")
    copy_file(root / "pyproject.toml", bundle / "pyproject.toml")
    copy_file(root / "requirements-api.txt", bundle / "requirements-api.txt")
    copy_tree(root / "python", bundle / "python")
    frontend = bundle / "frontend"
    for name in ("package.json", "package-lock.json", "index.html", "tsconfig.json", "vite.config.ts"):
        copy_file(root / "frontend" / name, frontend / name)
    copy_tree(root / "frontend" / "src", frontend / "src")
    public_dir = root / "frontend" / "public"
    if public_dir.exists():
        copy_tree(public_dir, frontend / "public")


def hf_space_url(repo_id: str) -> str:
    owner, name = repo_id.split("/", 1)
    return f"https://{owner}-{name}.hf.space"


def smoke(url: str, timeout_s: int) -> None:
    deadline = time.time() + timeout_s
    health_url = f"{url.rstrip('/')}/api/health"
    last_error = ""
    while time.time() < deadline:
        try:
            with urlopen(health_url, timeout=20) as response:  # noqa: S310 - user-selected public Space URL
                body = response.read().decode("utf-8")
            if '"status":"ok"' in body.replace(" ", ""):
                with urlopen(url, timeout=20) as response:  # noqa: S310
                    if response.status < 400:
                        return
            last_error = body
        except (OSError, URLError) as exc:
            last_error = str(exc)
        time.sleep(20)
    raise RuntimeError(f"Space smoke test did not pass before timeout. Last error: {last_error}")


def retry_step(label: str, fn, attempts: int = 4):
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:  # pragma: no cover - network dependent
            last_exc = exc
            if attempt == attempts:
                break
            wait_s = min(45, 5 * attempt)
            print(f"{label} failed on attempt {attempt}/{attempts}; retrying in {wait_s}s: {exc}", file=sys.stderr)
            time.sleep(wait_s)
    assert last_exc is not None
    raise last_exc


def publish(repo_id: str, private: bool, wait: bool, timeout_s: int) -> str:
    try:
        from huggingface_hub import HfApi
        from huggingface_hub.utils import HfHubHTTPError
    except ImportError as exc:
        raise SystemExit(
            "Missing dependency: install with `python -m pip install -e .[deploy]` "
            "or `python -m pip install huggingface_hub`."
        ) from exc

    if not os.environ.get("HF_TOKEN") and not os.environ.get("HUGGING_FACE_HUB_TOKEN"):
        token_file = Path.home() / ".cache" / "huggingface" / "token"
        if not token_file.exists():
            raise SystemExit(
                "No Hugging Face token found. Set HF_TOKEN or run `huggingface-cli login`, "
                "then rerun this script."
            )

    root = project_root()
    with tempfile.TemporaryDirectory(prefix="mlb-show-hf-space-") as tmp:
        bundle = Path(tmp) / "space"
        build_bundle(root, bundle)
        api = HfApi()
        try:
            retry_step("create_repo", lambda: api.create_repo(
                repo_id=repo_id,
                repo_type="space",
                space_sdk="docker",
                private=private,
                exist_ok=True,
            ))
        except HfHubHTTPError as exc:
            raise SystemExit(f"Could not create or access Space {repo_id}: {exc}") from exc
        retry_step("upload_folder", lambda: api.upload_folder(
            repo_id=repo_id,
            repo_type="space",
            folder_path=str(bundle),
            commit_message="Deploy React Python MLB investment terminal",
        ))

    url = hf_space_url(repo_id)
    if wait:
        smoke(url, timeout_s=timeout_s)
    return url


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-id", default=DEFAULT_REPO_ID)
    parser.add_argument("--private", action="store_true")
    parser.add_argument("--no-wait", action="store_true")
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args(argv)
    url = publish(args.repo_id, args.private, wait=not args.no_wait, timeout_s=args.timeout)
    print(url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
