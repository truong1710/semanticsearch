import sys
from place_search.search import show_smart

if __name__ == "__main__":
    show_smart(" ".join(sys.argv[1:]) or "quán cà phê yên tĩnh gần Hồ Tây")