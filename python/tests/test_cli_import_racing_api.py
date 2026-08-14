import pytest

from racingedge_data.cli.import_racing_api import main


class TestImportRacingApiCli:
    def test_stops_at_credential_boundary_without_env_vars(self, monkeypatch, capsys):
        monkeypatch.delenv("RACING_API_USERNAME", raising=False)
        monkeypatch.delenv("RACING_API_PASSWORD", raising=False)
        monkeypatch.setattr("sys.argv", ["import_racing_api", "--from", "2024-01-01", "--to", "2024-01-31"])

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "RACING_API_USERNAME" in captured.err
        assert "RACING_API_PASSWORD" in captured.err
        assert "not been fabricated" in captured.err or "nothing has been imported" in captured.err

    def test_rejects_from_date_after_to_date(self, monkeypatch, capsys):
        monkeypatch.setenv("RACING_API_USERNAME", "fixture-user")
        monkeypatch.setenv("RACING_API_PASSWORD", "fixture-pass")
        monkeypatch.setattr("sys.argv", ["import_racing_api", "--from", "2024-02-01", "--to", "2024-01-01"])

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "--from must not be after --to" in captured.err

    def test_rejects_malformed_date(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["import_racing_api", "--from", "not-a-date", "--to", "2024-01-31"])
        with pytest.raises(SystemExit):
            main()
