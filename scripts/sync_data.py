from place_search.db import load_places
from place_search.store import sync_places

if __name__ == "__main__":
    sync_places(load_places())