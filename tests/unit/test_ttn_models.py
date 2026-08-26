from ttn_bot.models import parse_edit_data_message


def test_parse_edit_data_message_splits_series_and_number() -> None:
    data = parse_edit_data_message(
        "\n".join(
            [
                "Автомобиль: Газель NN ВА9712-7",
                "Водитель: Мартиневский Иван Васильевич",
                "Серия и номер ТТН: ЕМ 1926709",
                "Товар к перевозке принял: Мартиневский Иван Васильевич",
                "Отпуск разрешил: Китасов А.С.",
                "Сдал грузоотправитель: Китасов А.С.",
            ]
        )
    )

    assert data.ttn_series == "ЕМ"
    assert data.ttn_number == "1926709"
    assert data.series_and_number == "ЕМ 1926709"


def test_parse_edit_data_message_autofills_dependent_people() -> None:
    data = parse_edit_data_message(
        "\n".join(
            [
                "Автомобиль: Газель NN ВА9712-7",
                "Водитель: Мартиневский Иван Васильевич",
                "Серия и номер ТТН: ЕМ 1926709",
                "Отпуск разрешил: Китасов А.С.",
            ]
        )
    )

    assert data.goods_accepted_by == "Мартиневский Иван Васильевич"
    assert data.shipper_handed_over_by == "Китасов А.С."
