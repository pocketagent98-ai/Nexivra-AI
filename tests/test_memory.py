import json

from nexivra.memory import ResearchMemory


class _FakeReport:
    def __init__(self, sources):
        self._sources = sources

    def to_dict(self):
        return {"sources": self._sources}


def test_remember_and_recall(tmp_path):
    mem = ResearchMemory(tmp_path / "memory.json")
    mem.remember("proj", "What was the 2025 revenue of Acme Corp?", _FakeReport([{"url": "https://a.example"}]))
    mem.remember("proj", "What was Acme Corp headcount growth?", _FakeReport([]))
    hits = mem.recall("What was the 2025 revenue of Acme Corp?", "proj")
    assert hits and "revenue" in hits[0]["question"]


def test_recall_no_overlap_returns_empty(tmp_path):
    mem = ResearchMemory(tmp_path / "memory.json")
    mem.remember("proj", "What was the 2025 revenue of Acme Corp?", _FakeReport([]))
    assert mem.recall("completely different unrelated topic zzz") == []


def test_persistence(tmp_path):
    path = tmp_path / "memory.json"
    mem = ResearchMemory(path)
    mem.remember("proj", "What was the 2025 revenue of Acme Corp?", _FakeReport([]))
    mem2 = ResearchMemory(path)
    assert mem2.recall("2025 revenue Acme Corp", "proj")


def test_no_secret_bodies_stored(tmp_path):
    path = tmp_path / "memory.json"
    mem = ResearchMemory(path)
    mem.remember("proj", "question", _FakeReport([]))
    raw = path.read_text()
    assert "api" not in json.loads(raw)["proj"][0] or isinstance(json.loads(raw), dict)
