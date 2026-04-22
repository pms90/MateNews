from __future__ import annotations

import shutil
import subprocess
from datetime import datetime
from pathlib import Path


class PublishError(RuntimeError):
    pass


def publish_site(
    source_dir: Path,
    target_dir: Path,
    repo_dir: Path,
    commit_message: str | None = None,
    remote: str = "origin",
    branch: str | None = None,
    push: bool = True,
) -> tuple[int, str | None]:
    if not source_dir.exists():
        raise PublishError(f"Build directory not found: {source_dir}")

    synchronized_files = sync_site_directory(source_dir, target_dir)
    git_root = _git_root(repo_dir)
    if git_root is None:
        raise PublishError(
            f"Synchronized {synchronized_files} files into {target_dir}, but no Git repository was found in {repo_dir}."
        )

    target_for_git = target_dir.resolve()
    try:
        relative_target = target_for_git.relative_to(git_root)
    except ValueError as exc:
        raise PublishError(f"Target directory {target_dir} must be inside the Git repository {git_root}.") from exc

    _git(repo_dir, "add", "--all", str(relative_target))
    if _has_staged_changes(repo_dir):
        resolved_message = commit_message or default_commit_message()
        _git(repo_dir, "commit", "-m", resolved_message)
        if push:
            push_args = ["push", remote]
            if branch:
                push_args.append(branch)
            _git(repo_dir, *push_args)
        return synchronized_files, resolved_message

    return synchronized_files, None


def sync_site_directory(source_dir: Path, target_dir: Path) -> int:
    source_dir = source_dir.resolve()
    target_dir = target_dir.resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    synchronized = 0
    existing_entries = {path.name: path for path in target_dir.iterdir()}
    source_entries = {path.name: path for path in source_dir.iterdir()}

    for name, existing_path in existing_entries.items():
        if name == ".git":
            continue
        if name not in source_entries:
            if existing_path.is_dir():
                shutil.rmtree(existing_path)
            else:
                existing_path.unlink()

    for name, source_path in source_entries.items():
        destination = target_dir / name
        if source_path.is_dir():
            if destination.exists():
                shutil.rmtree(destination)
            shutil.copytree(source_path, destination)
            synchronized += sum(1 for path in source_path.rglob("*") if path.is_file())
        else:
            shutil.copy2(source_path, destination)
            synchronized += 1

    return synchronized


def default_commit_message(now: datetime | None = None) -> str:
    current = now or datetime.now()
    return f"Publish MateNews site {current:%Y-%m-%d %H:%M:%S}"


def _git_root(repo_dir: Path) -> Path | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_dir), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    return Path(completed.stdout.strip()).resolve()


def _has_staged_changes(repo_dir: Path) -> bool:
    completed = subprocess.run(
        ["git", "-C", str(repo_dir), "diff", "--cached", "--quiet"],
        check=False,
    )
    return completed.returncode == 1


def _git(repo_dir: Path, *args: str) -> None:
    try:
        subprocess.run(["git", "-C", str(repo_dir), *args], check=True)
    except FileNotFoundError as exc:
        raise PublishError("Git is not installed or not available in PATH.") from exc
    except subprocess.CalledProcessError as exc:
        raise PublishError(f"Git command failed: git {' '.join(args)}") from exc