from unittest.mock import MagicMock, patch

import pytest

from racingedge_data.providers import kaggle_adapter
from racingedge_data.providers.kaggle_adapter import (
    KaggleAdapter,
    KaggleNotConfiguredError,
    KaggleTermsNotAcceptedError,
    has_kaggle_credentials,
)


class TestHasKaggleCredentials:
    def test_true_via_env_vars(self, monkeypatch):
        monkeypatch.setenv("KAGGLE_USERNAME", "someone")
        monkeypatch.setenv("KAGGLE_KEY", "abc123")
        assert has_kaggle_credentials() is True

    def test_true_via_kaggle_json_file(self, tmp_path, monkeypatch):
        monkeypatch.delenv("KAGGLE_USERNAME", raising=False)
        monkeypatch.delenv("KAGGLE_KEY", raising=False)
        (tmp_path / "kaggle.json").write_text('{"username": "x", "key": "y"}')
        assert has_kaggle_credentials(config_dir=str(tmp_path)) is True

    def test_false_when_neither_present(self, tmp_path, monkeypatch):
        monkeypatch.delenv("KAGGLE_USERNAME", raising=False)
        monkeypatch.delenv("KAGGLE_KEY", raising=False)
        assert has_kaggle_credentials(config_dir=str(tmp_path)) is False


class TestKaggleAdapterNotConfigured:
    def test_raises_without_reaching_the_real_kaggle_import(self, monkeypatch):
        monkeypatch.setattr(kaggle_adapter, "has_kaggle_credentials", lambda **_: False)
        with patch.object(kaggle_adapter, "_import_kaggle_api") as mock_import:
            adapter = KaggleAdapter()
            with pytest.raises(KaggleNotConfiguredError, match="not connected"):
                adapter.download_dataset("owner/dataset", "/tmp/wherever")
            mock_import.assert_not_called()


class TestKaggleAdapterDownload:
    def _adapter_with_mock_client(self):
        mock_client = MagicMock()
        adapter = KaggleAdapter(client_factory=lambda: mock_client)
        return adapter, mock_client

    def test_download_dataset_calls_client_with_expected_args(self, tmp_path):
        adapter, mock_client = self._adapter_with_mock_client()
        dest = adapter.download_dataset("someowner/some-dataset", tmp_path, unzip=True)
        assert dest == tmp_path
        mock_client.dataset_download_files.assert_called_once_with(
            "someowner/some-dataset", path=str(tmp_path), unzip=True, quiet=True
        )

    def test_creates_dest_dir_if_missing(self, tmp_path):
        dest_dir = tmp_path / "nested" / "dir"
        adapter, mock_client = self._adapter_with_mock_client()
        adapter.download_dataset("someowner/some-dataset", dest_dir)
        assert dest_dir.exists()

    def test_403_raises_terms_not_accepted_with_dataset_url(self, tmp_path):
        adapter, mock_client = self._adapter_with_mock_client()
        error = Exception("Forbidden")
        error.status = 403
        mock_client.dataset_download_files.side_effect = error

        with pytest.raises(KaggleTermsNotAcceptedError) as excinfo:
            adapter.download_dataset("someowner/some-dataset", tmp_path)
        assert "someowner/some-dataset" in str(excinfo.value)
        assert "kaggle.com" in str(excinfo.value)

    def test_401_raises_not_configured(self, tmp_path):
        adapter, mock_client = self._adapter_with_mock_client()
        error = Exception("Unauthorized")
        error.status = 401
        mock_client.dataset_download_files.side_effect = error

        with pytest.raises(KaggleNotConfiguredError, match="reconnect"):
            adapter.download_dataset("someowner/some-dataset", tmp_path)

    def test_404_raises_not_configured_with_dataset_ref(self, tmp_path):
        adapter, mock_client = self._adapter_with_mock_client()
        error = Exception("Not found")
        error.status = 404
        mock_client.dataset_download_files.side_effect = error

        with pytest.raises(KaggleNotConfiguredError, match="not found"):
            adapter.download_dataset("someowner/some-dataset", tmp_path)

    def test_unrecognised_error_is_reraised_unchanged(self, tmp_path):
        adapter, mock_client = self._adapter_with_mock_client()
        mock_client.dataset_download_files.side_effect = ValueError("something else entirely")

        with pytest.raises(ValueError, match="something else entirely"):
            adapter.download_dataset("someowner/some-dataset", tmp_path)


class TestListDatasetFiles:
    def test_maps_file_objects_to_dataclasses(self):
        mock_client = MagicMock()
        file_obj = MagicMock()
        file_obj.name = "races.csv"
        file_obj.total_bytes = 12345
        mock_client.dataset_list_files.return_value = MagicMock(files=[file_obj])

        adapter = KaggleAdapter(client_factory=lambda: mock_client)
        files = adapter.list_dataset_files("someowner/some-dataset")

        assert len(files) == 1
        assert files[0].name == "races.csv"
        assert files[0].size_bytes == 12345
