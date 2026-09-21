"""Tests for StorageService."""

from __future__ import annotations

import tempfile

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
