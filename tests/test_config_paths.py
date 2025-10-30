import os
from pathlib import Path
from typing import Dict

import pytest

import measureit
import measureit.config as config
import measureit.tools.util as util


@pytest.fixture(autouse=True)
def reset_measureit_config(monkeypatch):
    """Ensure each test starts with a clean configuration state."""
    config._DATA_DIR_OVERRIDE = None  # type: ignore[attr-defined]
    monkeypatch.delenv("MEASUREIT_HOME", raising=False)
    monkeypatch.delenv("MeasureItHome", raising=False)
    yield
    config._DATA_DIR_OVERRIDE = None  # type: ignore[attr-defined]


def _fake_user_data_dir(target: Path):
    return lambda *_, **__: str(target)


def test_get_path_uses_platformdirs_and_creates(tmp_path, monkeypatch):
    base = tmp_path / "platform_home"
    monkeypatch.setattr(config, "user_data_dir", _fake_user_data_dir(base))

    databases = config.get_path("databases")
    logs = config.get_path("logs")

    assert databases == base / "Databases"
    assert logs == base / "logs"
    assert databases.exists()
    assert logs.exists()


def test_get_path_respects_measurithome_env(tmp_path, monkeypatch):
    home = tmp_path / "env_home"
    monkeypatch.setenv("MEASUREIT_HOME", str(home))

    cfg_dir = config.get_path("cfg")
    assert cfg_dir == home / "cfg"
    assert cfg_dir.exists()


def test_get_path_respects_legacy_measureithome(tmp_path, monkeypatch):
    legacy_home = tmp_path / "legacy_home"
    monkeypatch.setenv("MeasureItHome", str(legacy_home))

    origin = config.get_path("origin_files")
    assert origin == legacy_home / "Origin Files"
    assert origin.exists()


def test_set_data_dir_overrides_environment(tmp_path, monkeypatch):
    env_home = tmp_path / "env_home"
    custom_home = tmp_path / "custom_home"
    monkeypatch.setenv("MEASUREIT_HOME", str(env_home))

    result = measureit.set_data_dir(custom_home)
    assert result == custom_home
    cfg_dir = measureit.get_path("cfg")
    assert cfg_dir == custom_home / "cfg"
    assert cfg_dir.exists()
    assert Path(measureit.get_path("databases")).parent == custom_home
    assert Path(measureit.get_path("logs")).parent == custom_home


def test_set_data_dir_updates_environment_variables(tmp_path):
    custom_home = tmp_path / "custom_env"
    measureit.set_data_dir(custom_home)

    assert measureit.get_path("databases").parent == custom_home
    assert measureit.get_path("logs").parent == custom_home
    assert os.environ["MEASUREIT_HOME"] == str(custom_home)
    assert os.environ["MeasureItHome"] == str(custom_home)


def test_get_path_rejects_unknown_subdir(monkeypatch):
    monkeypatch.setattr(
        config, "user_data_dir", _fake_user_data_dir(Path("/tmp/unused"))
    )
    with pytest.raises(ValueError):
        config.get_path("unknown")  # type: ignore[arg-type]


def test_database_creation_uses_configured_path(tmp_path, monkeypatch):
    base = tmp_path / "db_home"
    monkeypatch.setattr(config, "user_data_dir", _fake_user_data_dir(base))

    created: Dict[str, str] = {}

    def fake_init(path: str):
        created["path"] = path

    def fake_new_experiment(*_, **__):
        return None

    monkeypatch.setattr(util, "initialise_or_create_database_at", fake_init)
    monkeypatch.setattr(util.qc, "new_experiment", fake_new_experiment)

    util.init_database("example", "exp", "sample")

    expected_path = base / "Databases" / "example.db"
    assert created["path"] == str(expected_path)
    assert expected_path.parent.exists()
    expected_path.touch()
    assert expected_path.exists()
