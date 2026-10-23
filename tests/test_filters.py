from place_search.filters import (
    parse_price_range,
    parse_district,
    parse_query,
)

print(parse_price_range("4.000.000 - 8.000.000 VND/phòng 2 người."))
print(parse_price_range("từ 1,5 triệu"))
print(parse_district(
    "44 Lý Thường Kiệt, phường Trần Hưng Đạo, quận Hoàn Kiếm"
))
print(parse_query("khách sạn view hồ dưới 3 triệu ở Hoàn Kiếm"))