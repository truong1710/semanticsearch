from types import SimpleNamespace

from retrieval import search


def _hit(place_id, dense_vector, rrf_score=0.1):
    return SimpleNamespace(
        id=place_id,
        payload={"id": place_id, "tags": []},
        vector={"dense": dense_vector},
        score=rrf_score,
    )


def test_smart_search_reranks_by_dense_similarity_and_applies_cutoff(monkeypatch):
    monkeypatch.setattr(search, "MIN_RELEVANCE_SCORE", 0.45)
    monkeypatch.setattr(search, "parse_query", lambda query: ("hotel", None, None))
    monkeypatch.setattr(search, "embed_dense", lambda *args, **kwargs: [[1.0, 0.0]])
    monkeypatch.setattr(search, "route_category", lambda *args: (None, {}))
    monkeypatch.setattr(search, "infer_query_tags", lambda *args: [])
    monkeypatch.setattr(search, "detect_landmark", lambda query: (None, None))
    monkeypatch.setattr(
        search,
        "search_hybrid",
        lambda **kwargs: [
            _hit("good", [0.8, 0.6], rrf_score=0.2),
            _hit("below-cutoff", [0.4, 0.916515], rrf_score=0.3),
        ],
    )

    hits = search.smart_search("hotel", top_k=5)

    assert [hit.payload["id"] for hit in hits] == ["good"]
    assert hits[0].score == 0.8


def test_search_hybrid_requests_dense_vectors_for_reranking(monkeypatch):
    captured = {}
    monkeypatch.setattr(search, "embed_sparse_query", lambda query: "sparse")

    def fake_query_points(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(points=[])

    monkeypatch.setattr(search.client, "query_points", fake_query_points)

    search.search_hybrid("hotel", q_dense=[1.0, 0.0])

    assert captured["with_vectors"] == ["dense"]


def test_load_eval_set_reads_labeled_queries(tmp_path, monkeypatch):
    eval_file = tmp_path / "search_eval.json"
    eval_file.write_text(
        '[{"query":"khách sạn yên tĩnh","relevant_ids":["place-1"]}]',
        encoding="utf-8",
    )
    monkeypatch.setattr(search, "SEARCH_EVAL_FILE", eval_file)

    assert search.load_eval_set() == [
        ("khách sạn yên tĩnh", {"place-1"}),
    ]
