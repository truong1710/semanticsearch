from fastapi import FastAPI, Query
from .search import smart_search

app = FastAPI(title="Place Search")

@app.get("/health")
def health(): 
    return {"status": "ok"}

@app.get("/search")

# ... là yêu cầu phải gửi trong python
def search(q: str = Query(..., min_length=1, max_length=200),
           top_k: int = Query(5, ge=1, le=20)):
    hits = smart_search(q, top_k=top_k)
    return {
        "query": q,
        "results": [
            
            {
                **h.payload,
                "score": round(h.score, 4),
            }
            for h in hits
        ]
    }

           