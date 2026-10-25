"""ASGI entry point: run with ``uvicorn app.main:app``."""

from app.router.api import app


def main():
    """Start the API directly with ``python -m app.main``."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


__all__ = ["app"]


if __name__ == "__main__":
    main()
