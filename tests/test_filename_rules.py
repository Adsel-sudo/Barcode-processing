from barcode_tool.services.filename_extractor import extract_candidate_filename


def test_extract_candidate_filename_valid_samples() -> None:
    case1 = extract_candidate_filename("CuteBone Dog Swim Trunk...door Fun, Dinos DST10XL")
    assert case1.is_valid is True
    assert case1.value == "DST10XL"

    case2 = extract_candidate_filename("CuteBone One Piece Dog B...ol, Beach & Play LTDB11S")
    assert case2.is_valid is True
    assert case2.value == "LTDB11S"

    case3 = extract_candidate_filename("babygoal Baby Girl ...onths,YZX04-12-18M-B")
    assert case3.is_valid is True
    assert case3.value == "YZX04-12-18M-B"



def test_extract_candidate_filename_filters_invalid_values() -> None:
    invalid_inputs = [
        "New",
        "新品",
        "Made in China",
        "X01",
        "x0-test",
    ]

    for text in invalid_inputs:
        result = extract_candidate_filename(text)
        assert result.is_valid is False
        assert result.reason == "invalid-filename-value"
