from cloud_cua.cli import main


def test_open_dashboard_cli_uses_authorized_launcher(monkeypatch, capsys) -> None:
    class Client:
        def open_dashboard(self, repo_path, run_id, open_browser=True):
            assert repo_path == "C:/work/app"
            assert run_id == "run-123"
            assert open_browser is False
            return {
                "dashboard_url": "http://127.0.0.1:3000/?repo_path=app&run_id=run-123",
                "launch_url": "http://127.0.0.1:3000/?repo_path=app&run_id=run-123&launch_token=secret",
                "opened": False,
            }

    monkeypatch.setattr("cloud_cua.cli.CloudCUAClient", Client)

    assert main(["open-dashboard", "--repo-path", "C:/work/app", "--run-id", "run-123", "--no-browser"]) == 0
    output = capsys.readouterr().out
    assert "Cloud CUA dashboard:" in output
    assert "One-time launch URL:" in output


def test_dashboard_cli_opens_repo_without_existing_run(monkeypatch, capsys) -> None:
    class Client:
        def open_dashboard(self, repo_path, run_id="", open_browser=True):
            assert repo_path == "C:/work/new-app"
            assert run_id == ""
            assert open_browser is True
            return {"dashboard_url": "http://127.0.0.1:3000/?repo_path=new-app&run_id=", "launch_url": "unused", "opened": True}

    monkeypatch.setattr("cloud_cua.cli.CloudCUAClient", Client)

    assert main(["dashboard", "--repo-path", "C:/work/new-app"]) == 0
    assert "Cloud CUA dashboard:" in capsys.readouterr().out
