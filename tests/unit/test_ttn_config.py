from ttn_bot.config import Settings


def test_allowed_user_ids_accept_comma_separated_string() -> None:
    settings = Settings(BOT_TOKEN="token", ALLOWED_USER_IDS="881751023,797858007")

    assert settings.allowed_user_ids == [881751023, 797858007]


def test_allowed_user_ids_accept_json_list_string() -> None:
    settings = Settings(BOT_TOKEN="token", ALLOWED_USER_IDS="[881751023,797858007]")

    assert settings.allowed_user_ids == [881751023, 797858007]
