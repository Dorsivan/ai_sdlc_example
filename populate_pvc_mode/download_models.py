#!/usr/bin/env python3

import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path


def log(message: str) -> None:
    print(message, flush=True)


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def split_csv_env(name: str) -> list[str]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return []
    return [item.strip() for item in raw.replace("\n", ",").split(",") if item.strip()]


def safe_model_dir_name(model_id: str) -> str:
    # Example:
    # RedHatAI/gpt-oss-20b -> RedHatAI__gpt-oss-20b
    return model_id.replace("/", "__")


def run_command(cmd: list[str], env: dict[str, str]) -> None:
    log("")
    log("Running command:")
    log(" ".join(shlex.quote(part) for part in cmd))
    log("")

    process = subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    assert process.stdout is not None

    for line in process.stdout:
        print(line, end="", flush=True)

    return_code = process.wait()
    if return_code != 0:
        raise RuntimeError(f"Command failed with exit code {return_code}")


def write_manifest(model_id: str, destination: Path) -> None:
    files = []

    for path in destination.rglob("*"):
        if not path.is_file():
            continue

        rel = path.relative_to(destination).as_posix()

        files.append(
            {
                "path": rel,
                "size_bytes": path.stat().st_size,
            }
        )

    manifest = {
        "model_id": model_id,
        "destination": str(destination),
        "created_at_epoch": int(time.time()),
        "file_count": len(files),
        "total_size_bytes": sum(item["size_bytes"] for item in files),
        "files": sorted(files, key=lambda item: item["path"]),
    }

    manifest_path = destination / "_download_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    marker_path = destination / "_DOWNLOAD_COMPLETE"
    marker_path.write_text(
        f"model_id={model_id}\ncompleted_at_epoch={manifest['created_at_epoch']}\n",
        encoding="utf-8",
    )


def chmod_group_writable(path: Path) -> None:
    try:
        run_command(["chmod", "-R", "g+rwX", str(path)], env=os.environ.copy())
    except Exception as exc:
        log(f"WARNING: chmod failed, continuing anyway: {exc}")


def download_model(model_id: str, destination: Path) -> None:
    repo_type = os.getenv("HF_REPO_TYPE", "model")
    revision = os.getenv("HF_REVISION", "").strip()

    include_patterns = split_csv_env("HF_INCLUDE")
    exclude_patterns = split_csv_env("HF_EXCLUDE")
    extra_args = shlex.split(os.getenv("HF_EXTRA_ARGS", ""))

    cmd = [
        "hf",
        "download",
        model_id,
        "--repo-type",
        repo_type,
        "--local-dir",
        str(destination),
    ]

    if revision:
        cmd.extend(["--revision", revision])

    for pattern in include_patterns:
        cmd.extend(["--include", pattern])

    for pattern in exclude_patterns:
        cmd.extend(["--exclude", pattern])

    cmd.extend(extra_args)

    env = os.environ.copy()

    # Keep HF cache and temp files in writable locations.
    env.setdefault("HOME", "/tmp")
    env.setdefault("TMPDIR", "/tmp")
    env.setdefault("HF_HOME", "/tmp/.cache/huggingface")

    # Since you already saw Xet issues, disable it by default.
    env.setdefault("HF_HUB_DISABLE_XET", "1")

    # Defaults are 10 seconds; that is often too low in enterprise clusters.
    env.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "600")
    env.setdefault("HF_HUB_ETAG_TIMEOUT", "120")

    destination.mkdir(parents=True, exist_ok=True)

    max_retries = int(os.getenv("HF_MAX_RETRIES", "5"))
    retry_sleep_seconds = int(os.getenv("HF_RETRY_SLEEP_SECONDS", "30"))

    for attempt in range(1, max_retries + 1):
        try:
            log(f"Starting download for model: {model_id}")
            log(f"Destination: {destination}")
            log(f"Attempt: {attempt}/{max_retries}")

            run_command(cmd, env=env)

            write_manifest(model_id, destination)

            if env_bool("CHMOD_GROUP_WRITABLE", True):
                chmod_group_writable(destination)

            log("")
            log(f"Download complete: {model_id}")
            log(f"Marker written: {destination / '_DOWNLOAD_COMPLETE'}")
            return

        except Exception as exc:
            log("")
            log(f"Download attempt failed: {exc}")

            if attempt >= max_retries:
                raise

            log(f"Sleeping {retry_sleep_seconds}s before retry...")
            time.sleep(retry_sleep_seconds)


def main() -> int:
    models_root = Path(os.getenv("MODELS_ROOT", "/models"))

    models = split_csv_env("HF_MODELS")
    single_model = os.getenv("MODEL_ID", "").strip()

    if not models and single_model:
        models = [single_model]

    if not models:
        log("ERROR: Set MODEL_ID or HF_MODELS.")
        return 2

    log("Downloader config:")
    log(f"MODELS_ROOT={models_root}")
    log(f"HF_MODELS={models}")
    log(f"HF_TOKEN set={bool(os.getenv('HF_TOKEN'))}")
    log(f"HF_HUB_DISABLE_XET={os.getenv('HF_HUB_DISABLE_XET', '1')}")
    log(f"HF_HUB_DOWNLOAD_TIMEOUT={os.getenv('HF_HUB_DOWNLOAD_TIMEOUT', '600')}")
    log(f"HF_HUB_ETAG_TIMEOUT={os.getenv('HF_HUB_ETAG_TIMEOUT', '120')}")

    models_root.mkdir(parents=True, exist_ok=True)

    for model_id in models:
        custom_model_dir = os.getenv("MODEL_DIR_NAME", "").strip()

        if custom_model_dir and len(models) == 1:
            destination = models_root / custom_model_dir
        else:
            destination = models_root / safe_model_dir_name(model_id)

        download_model(model_id=model_id, destination=destination)

    log("")
    log("All downloads completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())