"""FastAPI application; start with ``uvicorn app.main:app``."""

from fastapi import FastAPI, Query

from retrieval.search import smart_search

app = FastAPI(title="Place Search")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/search")
def search(
    q: str = Query(..., min_length=1, max_length=200),
    top_k: int = Query(5, ge=1, le=20),
):
    hits = smart_search(q, top_k=top_k)
    return {
        "query": q,
        "results": [{**hit.payload, "score": round(hit.score, 4)} for hit in hits],
    }


def main():
    """Chạy riêng router API: ``python -m app.router.api``."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
