"""ASGI entry point; run with ``uvicorn app.main:app``."""

from app.router.api import app


def main():
    """Run API locally: ``python -m app.main``."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
