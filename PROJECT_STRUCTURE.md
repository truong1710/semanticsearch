# Cấu trúc project Place Search

Project thu thập địa điểm, đưa dữ liệu qua khâu kiểm tra và MySQL, tạo dense/sparse embedding, lưu lên Qdrant rồi phục vụ tìm kiếm qua API.

## Cây thư mục

```text
semanticsearch/
├── app/
│   ├── main.py
│   └── router/
│       └── api.py
├── common/
│   ├── taxonomy.py
│   └── text.py
├── core/
│   └── pipeline.py
├── crawldata/
│   ├── ai_extract.py
│   ├── config.py
│   ├── db.py
│   ├── enrich.py
│   ├── extract.py
│   ├── fetch.py
│   ├── pipeline.py
│   └── utils.py
├── database/
│   └── mysql.py
├── data/
│   ├── checked/
│   │   ├── places_duplicates.json
│   │   ├── places_needs_review.json
│   │   └── places_new.json
│   └── craw/
│       └── places.json
├── docker/
│   └── docker-compose.yml
├── embedding/
│   └── vectors.py
├── indexing/
│   └── qdrant.py
├── retrieval/
│   ├── query.py
│   └── search.py
├── scripts/
│   ├── check_duplicates.py
│   └── debug_images.py
├── config.py
├── pyproject.toml
├── uv.lock
├── README.md
├── PROJECT_STRUCTURE.md
├── .env.example
└── .gitignore
```

`.venv/` là môi trường Python cục bộ và `place_search.egg-info/` là metadata được tạo khi cài package ở chế độ editable. Đây là các artifact cài đặt, không phải mã nguồn chính.

## Chức năng từng thư mục và file

### `app/` — HTTP API

- `main.py`: điểm vào ASGI; chạy API bằng `uvicorn app.main:app` hoặc `python -m app.main`.
- `router/api.py`: tạo FastAPI app, cung cấp `GET /health` và `GET /search?q=...&top_k=...`.

### `common/` — Thành phần dùng chung

- `text.py`: làm sạch HTML/văn bản và chuẩn hóa chữ tiếng Việt không dấu qua `clean_text()` và `fold()`.
- `taxonomy.py`: khai báo danh mục, tag, luật nhận dạng tag, xử lý phủ định và kiểm tra tag xung đột.

### `core/` — Điều phối lệnh

- `pipeline.py`: file duy nhất trong `core/`; gom các giai đoạn thành CLI chung: crawl, kiểm tra trùng, nhập MySQL, đồng bộ embedding, tìm kiếm, đánh giá, xem JSON crawl và kiểm tra Qdrant.

### `crawldata/` — Thu thập và nhập dữ liệu crawl

- `config.py`: tùy chọn crawler, vùng tọa độ Hà Nội, selector HTML, cache và đường dẫn output.
- `fetch.py`: tải trang bằng HTTP hoặc Playwright, thử nút “xem thêm”, thu thập link chi tiết.
- `extract.py`: phân tích HTML, lấy nội dung, ảnh, link Google Maps và tọa độ trong URL.
- `ai_extract.py`: gọi Gemini để trích xuất địa điểm từ nội dung trang; quản lý cache kết quả AI.
- `enrich.py`: ghép ảnh với địa điểm, lấy tọa độ từ trang hoặc geocoding và lọc tọa độ dùng chung.
- `utils.py`: chuẩn hóa URL, tên/địa chỉ, tọa độ và sinh ID ổn định cho địa điểm.
- `pipeline.py`: ghép các bước tải trang → trích xuất → làm giàu → lưu `data/craw/places.json`.
- `db.py`: đọc file JSON đã kiểm tra, chuẩn hóa bản ghi, upsert địa điểm và ảnh vào MySQL; cũng có các lệnh kiểm tra kết nối/dữ liệu.

### `database/` — Đọc dữ liệu cho hệ thống tìm kiếm

- `mysql.py`: đọc các địa điểm hiện có từ bảng MySQL của ứng dụng, kiểm tra tọa độ/danh mục/trạng thái và chuẩn hóa ảnh.

`database/mysql.py` đọc dữ liệu nguồn để lập chỉ mục; `crawldata/db.py` nhập các kết quả crawl đã duyệt. Hai file phục vụ hai chiều dữ liệu khác nhau.

### `embedding/` — Tạo vector

- `vectors.py`: tạo dense vector bằng Gemini và sparse/BM25 vector bằng FastEmbed. Model/API được khởi tạo khi cần dùng, không gọi API chỉ vì import module.

### `indexing/` — Lưu và đồng bộ Qdrant

- `qdrant.py`: tạo collection/index, tạo payload và ID ổn định, bỏ qua embed lại nếu nội dung không đổi, upsert điểm mới và xóa điểm đã bị loại khỏi MySQL.

### `retrieval/` — Hiểu câu hỏi và tìm kiếm

- `query.py`: tách giá/quận khỏi câu hỏi; phân loại danh mục, suy ra tag và nhận diện landmark.
- `search.py`: tìm dense, hybrid dense+sparse, lọc/xếp hạng lại theo tag; chứa luôn hàm đánh giá recall@k và MRR.

### `data/` — Dữ liệu đầu vào và kết quả kiểm tra

- `craw/places.json`: dữ liệu thô do crawler tạo.
- `checked/places_new.json`: địa điểm mới sau khi so với MySQL.
- `checked/places_duplicates.json`: bản ghi bị nhận diện trùng.
- `checked/places_needs_review.json`: bản ghi cần người dùng xem lại.

### `scripts/` — Tiện ích chạy riêng

- `check_duplicates.py`: so sánh JSON crawl với MySQL và ghi ba file kết quả vào `data/checked/`. Cần truyền `--run` để thực hiện truy vấn/ghi file.
- `debug_images.py`: đối chiếu số lượng ảnh giữa MySQL và Qdrant; cần truyền `--run` để kết nối dịch vụ.

### `docker/` — Dịch vụ phụ trợ

- `docker-compose.yml`: cấu hình chạy Qdrant cục bộ, mở cổng `6333` và lưu dữ liệu vào `qdrant_data/`.

## File cấu hình ở thư mục gốc

- `config.py`: cấu hình chung cho MySQL, Qdrant, model embedding, cache model và ngưỡng tìm kiếm. Đọc `.env` dựa trên đường dẫn project, không dựa vào thư mục hiện hành.
- `.env.example`: mẫu biến môi trường cần thiết; sao chép thành `.env` rồi điền thông tin kết nối/API key.
- `.gitignore`: loại môi trường ảo, cache, dữ liệu tạm và file `.env` khỏi Git.
- `pyproject.toml`: metadata package, dependency và cấu hình setuptools.
- `uv.lock`: khóa phiên bản dependency để đồng bộ môi trường cài đặt bằng `uv`.
- `README.md`: hướng dẫn cài đặt và chạy nhanh.
- `PROJECT_STRUCTURE.md`: tài liệu cấu trúc và vai trò file hiện tại.

## Luồng dữ liệu chính

```text
URL
  → crawldata (tải, trích xuất, làm giàu)
  → data/craw/places.json
  → check trùng và duyệt
  → data/checked/places_new.json
  → crawldata/db.py nhập địa điểm mới vào MySQL
  → database/mysql.py đọc dữ liệu MySQL
  → embedding + indexing/qdrant.py đồng bộ vector
  → retrieval/search.py phục vụ tìm kiếm
  → app/router/api.py trả kết quả HTTP
```

## Lệnh chạy thường dùng

Cài package editable để chạy module từ thư mục bất kỳ:

```bash
pip install -e ".[api]"
```

Các lệnh pipeline phải chạy theo thứ tự kiểm tra và duyệt dữ liệu trước khi nhập:

```bash
python -m core.pipeline crawl https://example.com
python -m core.pipeline check
python -m core.pipeline import
python -m core.pipeline embed
```

Các lệnh tìm kiếm và API:

```bash
python -m core.pipeline search "quán cà phê yên tĩnh gần Hồ Tây"
python -m core.pipeline evaluate
uvicorn app.main:app --reload
```

Các đường dẫn tới `.env`, cache và JSON mặc định được tính từ vị trí file trong project. Những lệnh kết nối Gemini, MySQL hoặc Qdrant vẫn cần cấu hình thông tin dịch vụ tương ứng trong `.env`.
