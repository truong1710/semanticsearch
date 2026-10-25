# Tài liệu các file trong dự án `hanoi-search`

Dự án là một hệ thống **tìm kiếm ngữ nghĩa địa điểm ở Hà Nội** (khách sạn, quán cà phê, công viên, bảo tàng/chùa, nhà hàng). Dữ liệu lấy từ MySQL, được chuyển thành vector bằng Gemini, lưu vào Qdrant, rồi tìm kiếm bằng cách kết hợp vector dense, BM25, bộ lọc và tag.

> Ghi chú: tài liệu này mô tả đúng các file bạn đã gửi. Tên một số file (như `db.py`, `sync_data.py`) được suy ra từ comment trong code vì bạn không gửi kèm tên file.

---

## 1. Luồng hoạt động tổng quát

**Đồng bộ dữ liệu (chạy `sync_data.py`)**

```
MySQL ──(db.py: load_places)──► danh sách địa điểm hợp lệ
        └─► (store.py: sync_places)
              ├─ gán tag bằng luật (taxonomy.py)
              ├─ ghép văn bản mô tả (place_to_text)
              ├─ embed dense bằng Gemini + sparse BM25 (embeddings.py)
              ├─ upsert vào Qdrant kèm payload (giá, quận, tọa độ, tag...)
              └─ xoá điểm không còn trong MySQL
```

**Tìm kiếm (`smart_search`)**

```
Câu hỏi ─► tách giá/quận (filters.py)
        ─► embed câu hỏi (embeddings.py)
        ─► đoán danh mục, tag, địa danh (query_analysis.py)
        ─► tạo bộ lọc Qdrant → tìm hybrid dense + sparse (search.py)
        ─► xếp hạng lại theo mức khớp tag → trả top K
```

---

## 2. Mô tả từng file

### `config.py` — Cấu hình chung

Nơi tập trung mọi tham số của hệ thống.

- **Qdrant/model**: tên collection (`COLLECTION`, mặc định `places_demo`), địa chỉ `QDRANT_URL`, model embedding `gemini-embedding-001`, số chiều `EMBED_DIM = 768`, `BATCH`, `TAG_VERSION`, thư mục cache model BM25.
- **Ngưỡng tìm kiếm**: `CATEGORY_THR`, `CATEGORY_MARGIN` (ngưỡng đoán danh mục), `TAG_THR` (ngưỡng đoán tag bằng embedding), `TAG_BOOST` (điểm cộng cho mỗi tag khớp), `CANDIDATE_MULT` (số ứng viên lấy ra trước khi xếp hạng lại).
- **MySQL**: `DB_CONFIG` đọc từ file `.env` (host, port, user, password, database).
- **`SQL_PLACES`**: câu truy vấn lấy địa điểm từ bảng `stopover`, kèm danh sách URL ảnh (`image_urls`) gộp từ bảng `stopover_image` bằng `JSON_ARRAYAGG`.
- **`ALLOWED_STATUS`**: lọc theo trạng thái (hiện `None` = lấy tất cả).

### `db.py` — Đọc dữ liệu từ MySQL

Hàm chính: `load_places()`.

- Kết nối MySQL bằng `pymysql` (con trỏ streaming `SSDictCursor`) và chạy `SQL_PLACES`.
- **Kiểm tra từng dòng**, dòng lỗi được ghi vào danh sách `skipped` kèm lý do:
  1. Tọa độ thiếu hoặc nằm ngoài phạm vi hợp lệ.
  2. `category_id` chưa được ánh xạ (`CATEGORY_ID_MAP`) hoặc không có trong `CATEGORY_VI`.
  3. `status` không nằm trong `ALLOWED_STATUS`.
- Hàm phụ: `_s` (đổi giá trị thành chuỗi an toàn), `_bit_to_int` (đổi cột BIT của MySQL sang số), `_parse_image_urls` (đọc JSON danh sách ảnh, bỏ giá trị rỗng và trùng, giữ thứ tự).
- Trả về danh sách dict địa điểm đã chuẩn hóa (`id`, `name`, `address`, `description`, `latitude`, `longitude`, `price_range`, `category`, `image_urls`...) và in thống kê số địa điểm, số ảnh, lý do bỏ qua.
- Phần code cũ (không có ảnh) vẫn còn ở đầu file dưới dạng comment.

### `text_utils.py` — Làm sạch văn bản

- **`clean_text`**: giải mã HTML entity, bỏ thẻ HTML (BeautifulSoup), chuẩn hóa Unicode NFC, xoá ký tự vô hình, URL, emoji, gom khoảng trắng.
- **`fold`**: hạ chữ thường và **bỏ dấu tiếng Việt** (`"Công viên"` → `"cong vien"`, `đ` → `d`). Được dùng ở khắp nơi để so khớp không phân biệt dấu.

### `taxonomy.py` — Danh mục, tag và luật gán tag

- **`TAXONOMY`**: danh sách tag chia nhóm: không khí (yên tĩnh, sôi động, lãng mạn), đối tượng (gia đình, cặp đôi, đi một mình, công tác), tiện ích (view hồ, ban công, hồ bơi, ẩm thực địa phương, bữa sáng, spa), phong cách (cổ điển, tân cổ điển, hiện đại, sang trọng, tối giản, Đông Dương).
- **`TAG_VI`**: cách diễn đạt tiếng Việt của mỗi tag, dùng khi ghép văn bản mô tả địa điểm.
- **`CATEGORY_VI`**: tên tiếng Việt của 5 danh mục (`cat-hotel`, `cat-cafe`, `cat-park`, `cat-culture`, `cat-restaurant`).
- **`TAG_RULES`**: các regex nhận diện tag trong phần mô tả.
- **`NEG_PREFIX`**: phát hiện từ phủ định ("không", "chưa", "chẳng"...) đứng trước bằng chứng để tránh gán nhầm (ví dụ "không ồn" khác "ồn").
- **`rule_tags_with_evidence`**: chạy luật lên mô tả, trả về dict `{tag: đoạn văn bản làm bằng chứng}`. Nếu cùng lúc có `quiet` và `lively` thì bỏ cả hai.
- **`validate_tags`**: kiểm tra tag trùng, tag ngoài danh sách, và xung đột `quiet` + `lively`.

### `filters.py` — Tách điều kiện cứng từ câu hỏi và dữ liệu

- **`DISTRICTS`**: 12 quận, 1 thị xã và 17 huyện của Hà Nội.
- **`parse_price_range`**: đọc chuỗi giá như `"3.000.000 - 5.000.000 VND/phòng"` thành `(giá_min, giá_max)` bằng VND, hiểu cả `triệu/tr/m`, `k/nghìn/ngàn`, bỏ số nhỏ hơn 10.000. `"Liên hệ"` trả về `(None, None)`.
- **`parse_district`**: tìm tên quận trong địa chỉ, không phân biệt dấu.
- **`parse_query`**: tách câu hỏi thành `(nội dung tìm kiếm, giá tối đa, quận)`. Ví dụ `"Tìm khách sạn dưới 3 triệu ở Tây Hồ"` → `("Tìm khách sạn ở", 3000000, "Tây Hồ")`. Phần giá và quận bị cắt khỏi câu để không làm nhiễu embedding.
- **`normalize_text`, `_to_vnd`**: hàm phụ chuẩn hóa chuỗi và quy đổi tiền.

### `embeddings.py` — Tạo vector

- **Dense**: `embed_dense` gọi API Gemini (`gemini-embedding-001`, 768 chiều), chia batch, chuẩn hóa vector về độ dài 1, nghỉ 0,2 giây giữa các batch. `task_type` là `RETRIEVAL_DOCUMENT` cho văn bản địa điểm và `RETRIEVAL_QUERY` cho câu người dùng.
- **Sparse**: BM25 bằng FastEmbed (`embed_sparse_docs`, `embed_sparse_query`), văn bản được bỏ dấu (`fold`) trước khi tạo vector.
- Cuối file có một `assert` gọi thử API khi import để phát hiện sớm lỗi key hoặc model. Cần có `GEMINI_API_KEY` trong `.env`.

### `query_analysis.py` — Hiểu câu hỏi

- **`route_category`**: đoán người dùng muốn danh mục nào. Ưu tiên từ khóa (`keyword_category`, ví dụ "khách sạn", "cà phê", "chùa"); nếu không có thì so vector câu hỏi với các **prototype** của từng danh mục, chỉ chọn khi điểm ≥ `CATEGORY_THR` và hơn danh mục thứ hai ít nhất `CATEGORY_MARGIN`.
- **`infer_query_tags`**: suy ra tag người dùng muốn bằng ba cách: cụm từ không dấu trong `QUERY_TAG_RULES`, khớp mờ (`fuzzy_contains`, chịu lỗi gõ cho cụm dài), và độ giống vector với `TAG_PROTOTYPES` (≥ `TAG_THR`). Nếu có cả `quiet` và `lively` thì bỏ cả hai.
- **`detect_landmark`**: nhận ra địa danh có sẵn tọa độ (Hồ Hoàn Kiếm, Phố Cổ, Hồ Tây, Văn Miếu) để tìm theo bán kính.
- Các vector prototype được tính một lần khi import (`CAT_VECS`, `TAG_VECS`). Hàm `similarities` lấy điểm giống cao nhất trong số các prototype của mỗi nhóm.

### `store.py` — Đồng bộ dữ liệu vào Qdrant

- **`ensure_collection`**: tạo collection nếu chưa có, gồm vector `dense` (cosine) và `sparse` (BM25, IDF), cùng các payload index (`category`, `tags`, `location`, `price_min`, `price_max`, `district`).
- **`place_to_text`**: ghép văn bản dùng để embed: *tên + danh mục + địa chỉ + mô tả + đặc điểm (tag)*.
- **`build_payload`**: payload lưu kèm mỗi điểm: toàn bộ trường gốc, `location`, `tags`, `tag_source`, `price_min`, `price_max`, `district`, `text_hash`.
- **`ingest_places`**: tối ưu chi phí bằng `text_hash` (hash của tên model + số chiều + văn bản). Văn bản không đổi thì giữ vector cũ, chỉ ghi lại payload; văn bản đổi hoặc điểm mới thì mới embed lại và upsert.
- **`sync_places`**: quy trình chính: gán tag bằng luật, ingest, rồi **xoá các điểm không còn trong MySQL**. Có chốt an toàn: nếu MySQL không trả dòng nào thì huỷ đồng bộ để tránh xoá sạch Qdrant.
- **`point_id`**: sinh UUID cố định từ id địa điểm (`uuid5`), nên đồng bộ nhiều lần không tạo trùng.

### `search.py` — Tìm kiếm

- **`_flt`**: tạo bộ lọc Qdrant theo danh mục, bán kính địa lý, giá (`price_max < giá người dùng nêu`) và quận.
- **`search_dense`**: chỉ tìm bằng vector dense.
- **`search_hybrid`**: tìm dense và sparse song song rồi trộn bằng RRF (Reciprocal Rank Fusion).
- **`smart_search`**: pipeline đầy đủ: tách giá/quận → embed → đoán danh mục, tag, địa danh → tìm kiếm (nếu có địa danh mà không ra kết quả thì nới lỏng bán kính, nhưng **không bỏ** giá, quận, danh mục) → xếp hạng lại: điểm hybrid chuẩn hóa + `TAG_BOOST` × số tag khớp. Có chế độ `debug` in toàn bộ quá trình phân tích.
- **`show_smart`**: in kết quả ra màn hình để thử nhanh.

### `evaluate.py` — Đánh giá chất lượng

- `EVAL_SET`: danh sách `(câu hỏi, tập id địa điểm đúng)`, hiện đang để trống.
- `evaluate`: tính **recall@k** và **MRR** cho một hàm tìm kiếm.
- `run_all`: so sánh ba chế độ `dense`, `hybrid` và `smart (đầy đủ)`. Nếu `EVAL_SET` trống thì bỏ qua.

### `sync_data.py` (trong thư mục `scripts/`)

Script chạy tay để đồng bộ: gọi `load_places()` rồi `sync_places()`. Bạn chưa gửi nội dung file này nên mô tả dựa vào cách bạn chạy (`python sync_data.py`) và log in ra.

---

## 3. Bảng tóm tắt

| File | Vai trò | Phụ thuộc chính |
|---|---|---|
| `config.py` | Cấu hình, SQL, ngưỡng | `.env` |
| `db.py` | Đọc và kiểm tra dữ liệu MySQL | `config`, `taxonomy` |
| `text_utils.py` | Làm sạch chữ, bỏ dấu | — |
| `taxonomy.py` | Tag, danh mục, luật gán tag | `text_utils` |
| `filters.py` | Đọc giá, quận, tách điều kiện câu hỏi | `text_utils` |
| `embeddings.py` | Vector dense (Gemini) và sparse (BM25) | `config`, `text_utils` |
| `query_analysis.py` | Đoán danh mục, tag, địa danh | `embeddings`, `config`, `text_utils` |
| `store.py` | Ghi dữ liệu vào Qdrant | `embeddings`, `taxonomy`, `filters` |
| `search.py` | Tìm kiếm thông minh | `store`, `embeddings`, `filters`, `query_analysis` |
| `evaluate.py` | Đo recall và MRR | `search` |

---

## 4. Một số điểm cần lưu ý trong code hiện tại

1. **Đổi model embedding thì phải sync lại toàn bộ.** `text_hash` chứa tên model nên điểm cũ sẽ được embed lại, nhưng các ngưỡng `CATEGORY_THR`, `TAG_THR` được tune cho model đang dùng và có thể phải chỉnh lại.
2. **`district` có thể là `None`** nếu địa chỉ không ghi tên quận (ví dụ chỉ có tên phường). Khi người dùng lọc theo quận, những địa điểm này sẽ bị loại.
3. **`NEG_PREFIX` trong `taxonomy.py` được định nghĩa hai lần**; bản định nghĩa sau (có `(?!\s+gian)` để không nhầm "không gian") mới là bản có hiệu lực. `NEG_SUFFIX` đã khai báo nhưng chưa được dùng.
4. **Một số thứ import nhưng chưa dùng**: `TAG_RULES` trong `query_analysis.py`, `search_dense` không nằm trong `smart_search`. Không gây lỗi, có thể dọn cho gọn.
5. **`LANDMARKS` chỉ có 4 địa danh.** Muốn tìm theo bán kính cho nhiều nơi hơn thì thêm vào đó.
6. **Tag từ luật dựa vào mô tả.** Nếu mô tả không nhắc "hồ bơi" bằng chữ thì địa điểm sẽ không có tag `pool`, dù thực tế có.