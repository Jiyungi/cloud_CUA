from pathlib import Path

from cloud_cua import service_runtime


def test_managed_runtime_python_uses_user_runtime_venv(tmp_path: Path, monkeypatch) -> None:
    runtime_python = tmp_path / "runtime-venv" / ("Scripts/python.exe" if service_runtime.os.name == "nt" else "bin/python")
    runtime_python.parent.mkdir(parents=True)
    runtime_python.touch()
    monkeypatch.setattr(service_runtime, "user_config_dir", lambda: tmp_path)

    assert service_runtime._managed_runtime_python() == str(runtime_python)


def test_managed_runtime_python_returns_none_when_not_installed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(service_runtime, "user_config_dir", lambda: tmp_path)

    assert service_runtime._managed_runtime_python() is None
