def test_normalisation():
    from scripts.clean_transform import normalise_name

    result = normalise_name("Bengaluru Dist.")
    assert result == "Bengaluru District"