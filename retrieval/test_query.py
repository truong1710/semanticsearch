from retrieval.query import parse_query


def test_landmark_name_is_not_parsed_as_a_district():
    _, _, district = parse_query("Tìm khách sạn 5 sao gần Hồ Hoàn Kiếm")

    assert district is None


def test_explicit_district_is_still_parsed_with_landmark():
    _, _, district = parse_query(
        "Tìm khách sạn gần Hồ Hoàn Kiếm ở quận Hoàn Kiếm"
    )

    assert district == "Hoàn Kiếm"
