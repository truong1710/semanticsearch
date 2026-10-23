from place_search.taxonomy import rule_tags_with_evidence


def test_quiet_not_negated_by_khong_gian():
    tags = rule_tags_with_evidence("không gian nghỉ dưỡng sang trọng và yên tĩnh")
    assert "quiet" in tags


def test_negation_removes_pool():
    assert "pool" not in rule_tags_with_evidence("khách sạn không có hồ bơi")


def test_quiet_and_lively_conflict_removes_both():
    tags = rule_tags_with_evidence("yên tĩnh nhưng cũng rất náo nhiệt")
    assert "quiet" not in tags and "lively" not in tags


def test_couple_does_not_imply_romantic():
    tags = rule_tags_with_evidence("phù hợp cặp đôi")
    assert "couple" in tags and "romantic" not in tags