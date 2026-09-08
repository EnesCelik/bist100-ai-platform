from app.realtime_trade_flow.member_codes import resolve_member_name


def test_resolve_member_name_known_code():
    assert resolve_member_name("YKR") == "Yapı Kredi Yatırım Menkul Değerler A.Ş."


def test_resolve_member_name_is_case_and_whitespace_insensitive():
    assert resolve_member_name(" ykr ") == "Yapı Kredi Yatırım Menkul Değerler A.Ş."


def test_resolve_member_name_unknown_code_falls_back_to_raw_code():
    assert resolve_member_name("XYZ") == "XYZ"
