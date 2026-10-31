# API tìm kiếm địa điểm

Tài liệu này mô tả API được khai báo trong `app/router/api.py`. API dùng FastAPI để kiểm tra trạng thái dịch vụ và tìm địa điểm phù hợp với câu hỏi. Endpoint tìm kiếm gọi `smart_search()` trong `retrieval/search.py`, vì vậy cần cấu hình các dịch vụ và thông tin kết nối tương ứng trong `.env`.

## Chạy API

Từ thư mục gốc dự án, bật môi trường ảo rồi chạy:

```bash
source .venv/bin/activate
uvicorn app.main:app --reload
```

Mặc định API lắng nghe tại `http://127.0.0.1:8000`. Có thể xem giao diện thử API tại `http://127.0.0.1:8000/docs`.

## `GET /health`

Kiểm tra ứng dụng API có đang hoạt động hay không. Endpoint này không nhận input và không kiểm tra kết nối tới MySQL, Qdrant hay Gemini.

Response `200 OK`:

```json
{"status": "ok"}
```

## `GET /search`

Tìm địa điểm dựa trên câu hỏi tự nhiên. API phân tích truy vấn, tìm kiếm và xếp hạng kết quả qua `smart_search()`.

### Input

Các tham số được truyền trên URL dưới dạng query parameters:

| Tên | Bắt buộc | Mặc định | Quy tắc | Ý nghĩa |
|---|---|---:|---|---|
| `q` | Có | — | Chuỗi dài 1–200 ký tự | Câu hỏi tìm kiếm, ví dụ tên loại địa điểm, khu vực hoặc nhu cầu. |
| `top_k` | Không | `5` | Số nguyên từ 1 đến 20 | Số kết quả tối đa muốn nhận. |

Ví dụ:

```http
GET /search?q=quán%20cà%20phê%20yên%20tĩnh%20ở%20Tây%20Hồ&top_k=3
```

Hoặc dùng curl:

```bash
curl --get 'http://127.0.0.1:8000/search' \
  --data-urlencode 'q=quán cà phê yên tĩnh ở Tây Hồ' \
  --data-urlencode 'top_k=3'
```

### Output

Response `200 OK` có dạng:

```json
{
  "query": "quán cà phê yên tĩnh ở Tây Hồ",
  "results": [
    {
      "id": "place-123",
      "name": "Tên địa điểm",
      "address": "Địa chỉ",
      "score": 0.8421
    }
  ]
}
```

- `query`: nội dung truy vấn đã gửi.
- `results`: danh sách tối đa `top_k` địa điểm. Các trường địa điểm được lấy từ payload của bản ghi trong Qdrant, nên cụ thể những trường nào xuất hiện phụ thuộc dữ liệu đã được lập chỉ mục. Ví dụ có thể gồm `id`, `name`, `address`, `category`, `tags`, `images` và `location`.
- `score`: điểm tương đồng cosine của kết quả, được làm tròn đến 4 chữ số thập phân. Đây là điểm xếp hạng, không phải xác suất.

Nếu không tìm thấy kết quả phù hợp, `results` là mảng rỗng:

```json
{"query": "nội dung tìm kiếm", "results": []}
```

### Lỗi input

FastAPI trả `422 Unprocessable Entity` nếu thiếu `q`, `q` rỗng/dài hơn 200 ký tự, hoặc `top_k` không phải số nguyên trong khoảng 1–20. Lỗi kết nối tới dịch vụ tìm kiếm có thể khiến request thất bại; cần kiểm tra cấu hình `.env` và trạng thái Qdrant/các dịch vụ được pipeline sử dụng.
