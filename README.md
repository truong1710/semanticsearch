# Place Search

Hệ thống thu thập địa điểm, lưu dữ liệu vào MySQL, tạo dense/sparse embedding và tìm kiếm qua Qdrant.

## Cấu trúc

```text
core/
└── pipeline.py   # File duy nhất trong core; điều phối các giai đoạn

common/           # Chuẩn hóa văn bản và taxonomy
crawldata/        # Tải trang, trích xuất, làm giàu và nhập dữ liệu crawl
database/         # Đọc địa điểm từ MySQL
embedding/        # Gemini dense embedding và FastEmbed BM25
indexing/         # Tạo collection và đồng bộ vector lên Qdrant
retrieval/        # Phân tích truy vấn, lọc, tìm kiếm và đánh giá
config.py         # Cấu hình chung

scripts/          # Các lệnh chạy pipeline và tiện ích quản trị
data/craw/        # Kết quả crawl ban đầu
data/checked/     # Kết quả khử trùng lặp và cần duyệt
app/
├── main.py       # ASGI entry point
└── router/api.py # HTTP routes
docker/           # Cấu hình dịch vụ Docker
```

## Pipeline dữ liệu

1. `python -m core.pipeline crawl [URL ...]` lưu dữ liệu vào `data/craw/places.json`.
2. `python -m core.pipeline check` so sánh với MySQL và ghi các nhóm kết quả vào `data/checked/`.
3. Duyệt file trong `data/checked/`, sau đó chạy `python -m core.pipeline import` để nhập địa điểm mới vào MySQL.
4. `python -m core.pipeline embed` đọc MySQL, tạo embedding và đồng bộ Qdrant.

Cài package để sử dụng các lệnh ở ngoài thư mục dự án:

```bash
pip install -e ".[api]"
```

Sau khi cài ở chế độ editable, có thể chạy module từ thư mục bất kỳ. Mỗi file Python có `main()` và ví dụ; các ví dụ cục bộ không gọi dịch vụ ngoài trừ khi có cờ rõ ràng:

```bash
python -m common.text
python -m common.taxonomy
python -m crawldata.extract
python -m crawldata.fetch
python -m retrieval.query
python -m embedding.vectors --embed dense --text "quán cà phê yên tĩnh"
python -m database.mysql --connect
```

Các lệnh có `--connect`, `--run`, `--sync` hoặc `--embed` cần cấu hình dịch vụ tương ứng trong `.env`.

Tạo `.env` từ `.env.example` và điền thông tin dịch vụ cần dùng. Chạy API bằng:

```bash
uvicorn app.main:app --reload
```

Tìm kiếm bằng `python -m core.pipeline search <câu hỏi>`; đánh giá bằng `python -m core.pipeline evaluate`.
