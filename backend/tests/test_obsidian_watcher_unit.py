"""Unit tests for the watcher helpers (no DB / no real watcher loop)."""

from __future__ import annotations

from app.services.obsidian.watcher import is_drvfs_path


def test_drvfs_paths_detected() -> None:
    assert is_drvfs_path("/c/Users/Maurizio/vault") is True
    assert is_drvfs_path("/d/myProjects/vault") is True
    assert is_drvfs_path("/mnt/c/Users/Maurizio/vault") is True
    assert is_drvfs_path("/mnt/d/projects/vault") is True


def test_native_linux_paths_not_drvfs() -> None:
    assert is_drvfs_path("/vault") is False
    assert is_drvfs_path("/srv/sportedge/vault") is False
    assert is_drvfs_path("/home/user/vault") is False


def test_case_insensitive() -> None:
    # Real-world drives may come in either case
    assert is_drvfs_path("/C/Users/Maurizio/vault") is True
    assert is_drvfs_path("/MNT/c/Users/Mao/vault") is True
