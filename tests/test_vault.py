import base64
import json

import pytest

from nexivra.vault import ProviderVault, VaultError

KEY = base64.urlsafe_b64encode(b"k" * 32)


@pytest.fixture
def vault(tmp_path):
    return ProviderVault(tmp_path / "vault.json", master_key=KEY)


def test_store_and_get_roundtrip(vault):
    vault.store("nvidia", "nvapi-test-key-123")
    assert vault.get("nvidia") == "nvapi-test-key-123"


def test_masked_never_reveals_secret(vault):
    vault.store("nvidia", "nvapi-supersecretkey")
    masked = vault.masked("nvidia")
    assert "supersecret" not in masked
    assert masked is not None and masked.endswith("***")


def test_repr_has_no_secret(vault):
    vault.store("zai", "zai-key-value")
    assert "zai-key-value" not in repr(vault)


def test_rotate_replaces_key(vault):
    vault.store("nvidia", "old")
    vault.rotate("nvidia", "new")
    assert vault.get("nvidia") == "new"


def test_remove(vault):
    vault.store("nvidia", "x")
    assert vault.remove("nvidia") is True
    assert not vault.exists("nvidia")
    assert vault.remove("nvidia") is False


def test_get_missing_raises(vault):
    with pytest.raises(VaultError):
        vault.get("nope")


def test_no_overwrite_guard(vault):
    vault.store("nvidia", "a")
    with pytest.raises(VaultError):
        vault.store("nvidia", "b", allow_overwrite=False)


def test_persistence_across_instances(tmp_path):
    path = tmp_path / "vault.json"
    v1 = ProviderVault(path, master_key=KEY)
    v1.store("nvidia", "nvapi-abc")
    v2 = ProviderVault(path, master_key=KEY)
    assert v2.get("nvidia") == "nvapi-abc"


def test_file_on_disk_contains_no_plaintext_secret(tmp_path):
    path = tmp_path / "vault.json"
    v = ProviderVault(path, master_key=KEY)
    v.store("nvidia", "nvapi-PLAINTEXT")
    raw = path.read_text()
    assert "nvapi-PLAINTEXT" not in raw
    blob = json.loads(raw)
    assert "cipher" in blob["nvidia"]


def test_test_connection_reports_health_not_secret(vault):
    vault.store("nvidia", "nvapi-k")
    result = vault.test_connection("nvidia", lambda key: key.startswith("nvapi-"))
    assert result["status"] == "ok"
    assert "nvapi-k" not in str(result)
    assert vault.test_connection("missing", lambda k: True)["status"] == "no_key"


def test_tampered_cipher_raises(tmp_path):
    path = tmp_path / "vault.json"
    v = ProviderVault(path, master_key=KEY)
    v.store("nvidia", "nvapi-x")
    blob = json.loads(path.read_text())
    blob["nvidia"]["cipher"] = "AAAA" + blob["nvidia"]["cipher"][4:]
    path.write_text(json.dumps(blob))
    v2 = ProviderVault(path, master_key=KEY)
    with pytest.raises(Exception):
        v2.get("nvidia")
