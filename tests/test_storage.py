"""Tests for StorageService."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from services.storage_service import StorageService


def test_storage_basic_operations():
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage = StorageService(data_dir=tmp_dir)
        assert storage.get("nonexistent") is None
        assert storage.get("nonexistent", default="fallback") == "fallback"

        storage.set("key1", "value1")
        assert storage.get("key1") == "value1"

        storage.set("key2", {"a": 1, "b": 2})
        assert storage.get("key2") == {"a": 1, "b": 2}

        storage.flush()

        # New instance pointing to the same directory should read the flushed state
        storage2 = StorageService(data_dir=tmp_dir)
        assert storage2.get("key1") == "value1"
        assert storage2.get("key2") == {"a": 1, "b": 2}

        storage.remove("key1")
        assert storage.get("key1") is None
        storage.flush()

        storage3 = StorageService(data_dir=tmp_dir)
        assert storage3.get("key1") is None
        assert storage3.get("key2") == {"a": 1, "b": 2}


def test_storage_rejects_non_dict_json_and_uses_backup():
    with tempfile.TemporaryDirectory() as tmp_dir:
        Path(tmp_dir, "storage.json").write_text("[1, 2, 3]", encoding="utf-8")
        storage = StorageService(data_dir=tmp_dir)
        assert storage.get("anything") is None, "non-dict JSON must not brick reads"


def test_storage_falls_back_to_bak_on_corrupt_primary():
    with tempfile.TemporaryDirectory() as tmp_dir:
        Path(tmp_dir, "storage.json").write_text("{broken", encoding="utf-8")
        Path(tmp_dir, "storage.json.bak").write_text('{"k": "v"}', encoding="utf-8")
        storage = StorageService(data_dir=tmp_dir)
        assert storage.get("k") == "v"


def test_storage_rejects_non_serializable_set():
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage = StorageService(data_dir=tmp_dir)
        with pytest.raises(TypeError):
            storage.set("bad", {1, 2, 3})
        storage.set("good", "ok")
        storage.flush()
        assert json.loads(Path(tmp_dir, "storage.json").read_text(encoding="utf-8")) == {
            "good": "ok"
        }


def test_storage_get_returns_detached_copy():
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage = StorageService(data_dir=tmp_dir)
        storage.set("items", [1, 2])
        storage.get("items").append(99)
        assert storage.get("items") == [1, 2], "caller mutation must not poison the cache"
