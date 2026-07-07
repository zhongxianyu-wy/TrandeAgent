"""Git 版本管理 via subprocess（T08）。

技术约束：不引入 gitpython，全部用 Python 内置 subprocess 调用 git 命令。
"""
from __future__ import annotations

import subprocess
from pathlib import Path


class GitError(RuntimeError):
    """git 命令执行失败。"""


def _repo_root(path: Path) -> Path:
    """返回文件所在 git 仓库根目录（失败则回退到父目录）。"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            cwd=str(path.parent),
            check=True,
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return path.parent


def _relpath(path: Path) -> str:
    """返回文件相对于仓库根的路径（git 命令需要 repo-relative）。"""
    root = _repo_root(path)
    try:
        rel = path.resolve().relative_to(root.resolve())
        return str(rel)
    except ValueError:
        return path.name


def _run_git(args: list[str], cwd: Path) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            cwd=str(cwd),
            check=True,
        )
    except FileNotFoundError as e:
        raise GitError("未找到 git 命令，请确认 git 已安装") from e
    except subprocess.CalledProcessError as e:
        raise GitError(e.stderr.strip() or str(e)) from e
    return result.stdout


def git_commit(path: Path, message: str) -> str:
    """git add + commit 配置文件，返回 commit hash。

    若无可提交内容（文件未变更），返回当前 HEAD hash。
    """
    rel = _relpath(path)
    cwd = _repo_root(path)
    _run_git(["add", rel], cwd)
    # 尝试提交；若没有变更则跳过（"nothing to commit" 可能在 stdout）
    try:
        subprocess.run(
            ["git", "commit", "-m", message],
            capture_output=True,
            text=True,
            cwd=str(cwd),
            check=True,
        )
    except subprocess.CalledProcessError as e:
        combined = ((e.stdout or "") + (e.stderr or "")).lower()
        if "nothing to commit" in combined or "no changes" in combined:
            pass
        else:
            raise GitError((e.stderr or e.stdout or str(e)).strip()) from e
    except FileNotFoundError as e:
        raise GitError("未找到 git 命令，请确认 git 已安装") from e
    return _run_git(["rev-parse", "HEAD"], cwd).strip()


def git_log(path: Path, n: int = 10) -> list[dict]:
    """获取配置文件的 git 历史，返回 [{hash, date, message}]。"""
    rel = _relpath(path)
    cwd = _repo_root(path)
    out = _run_git(
        ["log", f"-{n}", "--pretty=format:%H|%ai|%s", "--", rel], cwd
    )
    entries: list[dict] = []
    for line in out.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("|", 2)
        if len(parts) < 3:
            continue
        entries.append({"hash": parts[0], "date": parts[1], "message": parts[2]})
    return entries


def git_show_file(path: Path, commit_hash: str) -> str:
    """读取某个 commit 下配置文件的内容。"""
    rel = _relpath(path)
    cwd = _repo_root(path)
    return _run_git(["show", f"{commit_hash}:{rel}"], cwd)


def git_rollback(path: Path, commit_hash: str) -> None:
    """把配置文件回滚到指定 commit（仅 checkout 该文件，不影响其他）。"""
    rel = _relpath(path)
    cwd = _repo_root(path)
    _run_git(["checkout", commit_hash, "--", rel], cwd)


def is_git_repo(path: Path) -> bool:
    """判断文件是否在 git 仓库内。"""
    try:
        _run_git(["rev-parse", "--is-inside-work-tree"], _repo_root(path))
        return True
    except GitError:
        return False
