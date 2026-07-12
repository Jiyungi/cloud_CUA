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


def test_service_launches_uvicorn_as_registered_process(tmp_path: Path, monkeypatch) -> None:
    command = {}

    class Process:
        pid = 4242

        def __init__(self, args, **_kwargs):
            command["args"] = args

        def poll(self):
            return None

    monkeypatch.setattr(service_runtime, "load_service_state", lambda: None)
    monkeypatch.setattr(service_runtime, "user_config_dir", lambda: tmp_path)
    monkeypatch.setattr(service_runtime, "service_stdout_path", lambda: tmp_path / "out.log")
    monkeypatch.setattr(service_runtime, "service_stderr_path", lambda: tmp_path / "err.log")
    monkeypatch.setattr(service_runtime, "save_service_state", lambda state: tmp_path / "service.json")
    monkeypatch.setattr(service_runtime, "service_is_healthy", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(service_runtime, "_available_port", lambda _port: 3111)
    monkeypatch.setattr(service_runtime.subprocess, "Popen", Process)

    state = service_runtime.ensure_service(python_executable="managed-python", preferred_port=3111)

    assert state.pid == 4242
    assert command["args"] == [
        "managed-python",
        "-I",
        "-m",
        "uvicorn",
        "cloud_cua.server:app",
        "--host",
        "127.0.0.1",
        "--port",
        "3111",
    ]
