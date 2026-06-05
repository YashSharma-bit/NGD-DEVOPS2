def test_normalisation_core():
    from scripts.clean_transform import normalise_name

    assert normalise_name("Bengaluru Dist.") == "Bengaluru Dist"

def test_normalisation_case_and_spaces():
    from scripts.clean_transform import normalise_name

    assert normalise_name("  bengaluru dist. ") == "Bengaluru District"

def test_non_district_name_unchanged():
    from scripts.clean_transform import normalise_name

    assert normalise_name("Mumbai") == "Mumbai"

def test_contains_district_keyword():
    from scripts.clean_transform import normalise_name

    result = normalise_name("Delhi Dist.")
    assert "District" in result 