# Luồng chạy pipeline Place Search

Tài liệu này giải thích thứ tự chạy các bước và file nào xử lý từng bước. Pipeline đi từ dữ liệu crawl đến MySQL, Qdrant, rồi API tìm kiếm.

## Sơ đồ tổng quan

```text
URL
 ↓
core/pipeline.py crawl
 ↓
crawldata/pipeline.py
 ├─ crawldata/fetch.py       tải trang
 ├─ crawldata/extract.py     lấy nội dung, ảnh, tọa độ
 ├─ crawldata/ai_extract.py  trích xuất địa điểm bằng Gemini
 ├─ crawldata/enrich.py      ghép ảnh và bổ sung tọa độ
 └─ data/craw/places.json
 ↓
core/pipeline.py check
 └─ scripts/check_duplicates.py so với dữ liệu MySQL
 ↓
data/checked/places_*.json  ← người dùng xem lại dữ liệu
 ↓
core/pipeline.py import
 └─ crawldata/db.py          nhập địa điểm mới vào MySQL
 ↓
core/pipeline.py embed
 ├─ database/mysql.py        đọc dữ liệu MySQL
 ├─ embedding/vectors.py     tạo dense/sparse vector
 └─ indexing/qdrant.py       đồng bộ điểm lên Qdrant
 ↓
retrieval/query.py + retrieval/search.py
 ↓
app/router/api.py → app/main.py → API
```

## 1. Cài đặt và cấu hình

Chạy các lệnh từ bất kỳ thư mục nào sau khi cài package editable:

```bash
pip install -e ".[api]"
```

Tạo `.env` từ `.env.example`, sau đó điền các thông tin cần thiết:

- `GEMINI_API_KEY` cho bước trích xuất và embedding.
- Thông tin MySQL: `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `USER_ID`.
- `QDRANT_URL` và `COLLECTION` cho Qdrant.

Khởi chạy Qdrant nếu dùng cấu hình Docker trong project:

```bash
docker compose -f docker/docker-compose.yml up -d
```

MySQL cần chạy và có sẵn các bảng cần thiết trước khi nhập hoặc đồng bộ dữ liệu.

## 2. Crawl trang web

```bash
python -m core.pipeline crawl https://example.com
```

`core/pipeline.py` gọi `crawldata/pipeline.py`. Crawler tải URL, trích xuất nội dung, gọi Gemini để lấy địa điểm, làm giàu ảnh/tọa độ rồi lưu kết quả vào:

```text
data/craw/places.json
```

Các file chính ở bước này:

- `crawldata/fetch.py`: tải HTML, có thể dùng Playwright nếu trang cần render JavaScript.
- `crawldata/extract.py`: tìm vùng nội dung, ảnh và tham chiếu bản đồ.
- `crawldata/ai_extract.py`: trích xuất dữ liệu có cấu trúc từ bài viết; dùng cache trong `data/craw/ai_cache.json`.
- `crawldata/enrich.py`: ghép ảnh và bổ sung tọa độ.
- `crawldata/config.py`: thiết lập crawler và đường dẫn output.

Xem nhanh dữ liệu vừa crawl:

```bash
python -m core.pipeline inspect-crawl
```

## 3. Kiểm tra trùng và duyệt dữ liệu

```bash
python -m core.pipeline check
```

Lệnh này chạy `scripts/check_duplicates.py --run`. Script đọc `data/craw/places.json`, so sánh với MySQL rồi ghi kết quả vào:

- `data/checked/places_new.json`: địa điểm có thể nhập mới.
- `data/checked/places_duplicates.json`: bản ghi trùng.
- `data/checked/places_needs_review.json`: bản ghi cần kiểm tra thủ công.

Hãy xem lại các file kết quả trước khi nhập. Đây là điểm kiểm soát để loại bản ghi sai hoặc trùng.

## 4. Nhập địa điểm mới vào MySQL

Sau khi duyệt `places_new.json`, chạy:

```bash
python -m core.pipeline import
```

Lệnh gọi `import_places()` trong `crawldata/db.py`, đọc JSON đã kiểm tra, xác thực trường dữ liệu rồi upsert địa điểm và ảnh vào MySQL. `USER_ID` phải là ID hợp lệ trong hệ thống.

## 5. Tạo embedding và đồng bộ Qdrant

```bash
python -m core.pipeline embed
```

Luồng xử lý:

1. `database/mysql.py` đọc và chuẩn hóa dữ liệu địa điểm từ MySQL.
2. `indexing/qdrant.py` gán tag và tạo nội dung để lập chỉ mục.
3. `embedding/vectors.py` tạo dense vector bằng Gemini và sparse vector bằng FastEmbed.
4. `indexing/qdrant.py` upsert điểm vào collection, cập nhật payload và xóa điểm không còn trong MySQL.

Nội dung không đổi sẽ được nhận diện bằng hash để tránh tạo lại embedding không cần thiết. Qdrant phải truy cập được tại `QDRANT_URL`.

Kiểm tra collection:

```bash
python -m core.pipeline qdrant
```

## 6. Tìm kiếm và API

Tìm kiếm từ terminal:

```bash
python -m core.pipeline search "quán cà phê yên tĩnh gần Hồ Tây" --top-k 5
```

`retrieval/query.py` tách giá/quận và phân tích danh mục, tag, landmark. `retrieval/search.py` tạo embedding truy vấn, tìm dense/hybrid trên Qdrant, áp dụng bộ lọc và xếp hạng kết quả.

Chạy API:

```bash
uvicorn app.main:app --reload
```

- `app/main.py` là ASGI entry point.
- `app/router/api.py` khai báo `GET /health` và `GET /search`.

Ví dụ gọi API:

```text
GET /search?q=khách%20sạn%20yên%20tĩnh%20ở%20Tây%20Hồ&top_k=5
```

## 7. Đánh giá chất lượng tìm kiếm

```bash
python -m core.pipeline evaluate
```

Hàm đánh giá nằm trong `retrieval/search.py`, tính recall@k và MRR cho dense, hybrid và smart search. Hiện `EVAL_SET` đang để trống; cần thêm câu hỏi và tập ID đúng trước khi có kết quả đánh giá.

## Thứ tự chạy rút gọn

```text
1. Cấu hình .env và khởi chạy MySQL/Qdrant
2. python -m core.pipeline crawl <URL>
3. python -m core.pipeline check
4. Xem lại data/checked/places_*.json
5. python -m core.pipeline import
6. python -m core.pipeline embed
7. python -m core.pipeline search "câu hỏi"
   hoặc khởi chạy API bằng uvicorn app.main:app
```
