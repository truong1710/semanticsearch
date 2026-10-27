import json
import unicodedata

import pytest

from indexing import ai_tagger
from common.taxonomy import (
    ALLOWED_TAGS,
    rule_tags_with_evidence as rules,
    validate_tags,
)


# ---------- taxonomy ----------

@pytest.mark.parametrize("text,tag", [
    ("Không khí yên tĩnh, thư thái", "quiet"),
    ("Bầu không khí lãng mạn", "romantic"),
    ("Không khí gia đình ấm cúng", "family"),
    ("Không chỉ có hồ bơi mà còn có spa", "pool"),
    ("Phòng nhìn ra hồ Tây", "lake-view"),
    ("Khách sạn dành cho khách công tác", "business"),
    ("Có đặc sản bún chả Hà Nội", "local-food"),
])
def test_tag_found(text, tag):
    assert tag in rules(text)


@pytest.mark.parametrize("text,tag", [
    ("Không có hồ bơi", "pool"),
    ("Chưa có bữa sáng", "breakfast"),
    ("Nằm bên hồ Hoàn Kiếm", "lake-view"),
    ("Phòng có bàn làm việc", "business"),
    ("Công tác vệ sinh sạch sẽ", "business"),
    ("Giường êm ái", "quiet"),
    ("Nhà hàng do gia đình quản lý", "family"),
    ("Nằm trong khách sạn Grand Plaza", "luxury"),
    ("Phục vụ hải sản tươi sống", "local-food"),
])
def test_tag_not_found(text, tag):
    assert tag not in rules(text)


def test_negation_does_not_leak_across_clauses():
    assert "pool" in rules("Không có spa, có hồ bơi")


def test_conflict_drops_both():
    found = rules("Yên tĩnh nhưng cũng rất sôi động")
    assert "quiet" not in found and "lively" not in found


def test_nfd_input_is_normalized():
    text = unicodedata.normalize("NFD", "Không gian yên tĩnh")
    assert "quiet" in rules(text)


def test_category_filters_hotel_only_tags():
    found = rules("Công viên có hồ bơi và yên tĩnh", category="cat-park")
    assert "pool" not in found and "quiet" in found


def test_validate_tags():
    assert validate_tags(["quiet", "lively"])
    assert validate_tags(["pool"], category="cat-park")
    assert validate_tags(["abc"])
    assert not validate_tags(["quiet", "pool"], category="cat-hotel")


# ---------- ai_tagger ----------

@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(ai_tagger, "CACHE_PATH", tmp_path / "ai_tags.json")
    monkeypatch.setattr(ai_tagger, "_cache", None)
    monkeypatch.setattr(ai_tagger, "BACKOFF_SECONDS", 0)


TEXT = "Khách sạn có thiết kế hiện đại và buffet sáng phong phú."
ALLOWED = sorted(ALLOWED_TAGS)


def _stub(monkeypatch, responses):
    calls = []

    def fake(prompt):
        calls.append(prompt)
        r = responses[min(len(calls) - 1, len(responses) - 1)]
        if isinstance(r, Exception):
            raise r
        return r

    monkeypatch.setattr(ai_tagger, "generate_text", fake)
    return calls


def test_valid_evidence_accepted_and_cached(monkeypatch):
    calls = _stub(monkeypatch, [json.dumps({"modern": "thiết kế hiện đại"})])
    assert ai_tagger.suggest_tags(TEXT, [], ALLOWED) == ["modern"]
    assert ai_tagger.suggest_tags(TEXT, [], ALLOWED) == ["modern"]
    assert len(calls) == 1
    assert ai_tagger.CACHE_PATH.exists()


def test_fabricated_evidence_rejected(monkeypatch):
    _stub(monkeypatch, [json.dumps({"pool": "có hồ bơi lớn"})])
    assert ai_tagger.suggest_tags(TEXT, [], ALLOWED) == []


def test_unknown_and_existing_tags_rejected(monkeypatch):
    _stub(monkeypatch, [json.dumps({
        "modern": "thiết kế hiện đại", "made-up": "buffet sáng"})])
    out = ai_tagger.suggest_tags(TEXT, ["modern"], ALLOWED)
    assert out == []


def test_conflict_with_existing_excluded_from_prompt(monkeypatch):
    calls = _stub(monkeypatch, [json.dumps({})])
    ai_tagger.suggest_tags(TEXT, ["quiet"], ALLOWED)
    assert '"lively"' not in calls[0].split("CÁC TAG ĐƯỢC PHÉP")[1]


def test_ai_conflicting_pair_dropped(monkeypatch):
    text = "Quán yên tĩnh và sôi động"
    _stub(monkeypatch, [json.dumps({"quiet": "yên tĩnh", "lively": "sôi động"})])
    assert ai_tagger.suggest_tags(text, [], ALLOWED) == []


def test_category_restricts_candidates(monkeypatch):
    calls = _stub(monkeypatch, [json.dumps({})])
    ai_tagger.suggest_tags("Công viên rộng", [], ALLOWED, category="cat-park")
    assert '"pool"' not in calls[0]


def test_markdown_and_extra_prose_tolerated(monkeypatch):
    raw = 'Đây là kết quả:\n```json\n{"modern": "thiết kế hiện đại"}\n```'
    _stub(monkeypatch, [raw])
    assert ai_tagger.suggest_tags(TEXT, [], ALLOWED) == ["modern"]


def test_retry_then_success(monkeypatch):
    calls = _stub(monkeypatch, [
        RuntimeError("429"), json.dumps({"modern": "thiết kế hiện đại"})])
    assert ai_tagger.suggest_tags(TEXT, [], ALLOWED) == ["modern"]
    assert len(calls) == 2


def test_all_attempts_fail_returns_empty(monkeypatch):
    _stub(monkeypatch, [RuntimeError("down")])
    assert ai_tagger.suggest_tags(TEXT, [], ALLOWED) == []
    assert not ai_tagger.CACHE_PATH.exists()


def test_cache_write_failure_keeps_result(monkeypatch):
    _stub(monkeypatch, [json.dumps({"modern": "thiết kế hiện đại"})])

    def boom(_):
        raise OSError("disk full")

    monkeypatch.setattr(ai_tagger, "_save_cache", boom)
    assert ai_tagger.suggest_tags(TEXT, [], ALLOWED) == ["modern"]


def test_corrupt_cache_recovers(monkeypatch):
    ai_tagger.CACHE_PATH.write_text("{hỏng", encoding="utf-8")
    _stub(monkeypatch, [json.dumps({"modern": "thiết kế hiện đại"})])
    assert ai_tagger.suggest_tags(TEXT, [], ALLOWED) == ["modern"]
