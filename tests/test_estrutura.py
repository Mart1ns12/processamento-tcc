def test_pacotes_importam():
    import processamento
    import processamento.diagnostico

    assert processamento.diagnostico is not None
