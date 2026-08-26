from pathlib import Path

from ttn_bot.models import TtnEditData
from ttn_bot.storage import Storage


def test_storage_saves_and_deletes_user_template(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "bot.sqlite3")
    storage.init()
    data = TtnEditData(
        vehicle="Авто",
        driver="Водитель",
        ttn_series="ЕМ",
        ttn_number="1926709",
        goods_accepted_by="Принял",
        release_allowed_by="Разрешил",
        shipper_handed_over_by="Сдал",
    )

    storage.save_user_template(100, data)

    assert storage.get_user_template(100) == data
    assert storage.delete_user_template(100) is True
    assert storage.get_user_template(100) is None

