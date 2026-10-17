#!/usr/bin/env python3
"""Read-only guard: identify the official repository, branch and dirty worktree."""
from __future__ import annotations
import argparse
import subprocess
from pathlib import Path

OFFICIAL = 'https://github.com/AcTweeteR/TwT-Actualizador.git'

def git(path: Path, *args: str) -> str:
    result = subprocess.run(['git', '-C', str(path), *args], capture_output=True, text=True, check=True)
    return result.stdout.strip()

def inspect(path: Path, require_clean: bool = False, require_branch: str | None = None) -> dict[str, str]:
    root = Path(git(path, 'rev-parse', '--show-toplevel')).resolve()
    if root != path.resolve():
        raise ValueError(f'Not repository root: {path} (actual {root})')
    remote = git(root, 'remote', 'get-url', 'origin')
    if remote != OFFICIAL:
        raise ValueError(f'Unexpected origin: {remote}')
    branch = git(root, 'branch', '--show-current')
    if not branch:
        raise ValueError('Detached HEAD')
    if require_branch and branch != require_branch:
        raise ValueError(f'Expected {require_branch}, found {branch}')
    status = git(root, 'status', '--porcelain=v1')
    if require_clean and status:
        raise ValueError('Working tree contains uncommitted changes')
    return {'root': str(root), 'branch': branch, 'commit': git(root, 'rev-parse', '--short', 'HEAD'), 'dirty': str(bool(status)).lower()}

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--require-clean', action='store_true')
    parser.add_argument('--require-branch')
    args = parser.parse_args()
    try:
        for k,v in inspect(args.root, args.require_clean, args.require_branch).items():
            print(f'{k}={v}')
    except (ValueError, subprocess.CalledProcessError) as error:
        parser.exit(2, f'WORKSPACE_GUARD_FAIL: {error}\n')

if __name__ == '__main__':
    main()
