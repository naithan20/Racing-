from unittest.mock import MagicMock, patch

import pytest

from racingedge_data.providers.download_adapter import (
    DownloadHttpError,
    UnsupportedFileTypeError,
    download_file,
    preview_url,
)


def _mock_head_response(status_code=200, content_length=None, content_type=None):
    response = MagicMock()
    response.status_code = status_code
    response.headers = {}
    if content_length is not None:
        response.headers["Content-Length"] = str(content_length)
    if content_type is not None:
        response.headers["Content-Type"] = content_type
    return response


def _mock_get_response(status_code, chunks, content_length=None):
    response = MagicMock()
    response.status_code = status_code
    response.headers = {}
    if content_length is not None:
        response.headers["Content-Length"] = str(content_length)
    response.iter_content = MagicMock(return_value=iter(chunks))
    return response


class TestPreviewUrl:
    @patch("requests.head")
    def test_returns_hostname_extension_and_size(self, mock_head):
        mock_head.return_value = _mock_head_response(200, content_length=1234, content_type="text/csv")
        preview = preview_url("https://example.com/data/races.csv")
        assert preview.hostname == "example.com"
        assert preview.file_extension == ".csv"
        assert preview.content_length == 1234
        assert preview.content_type == "text/csv"
        assert preview.is_allowed_extension is True

    @patch("requests.head")
    def test_disallowed_extension_is_flagged_not_raised(self, mock_head):
        mock_head.return_value = _mock_head_response(200)
        preview = preview_url("https://example.com/tool.exe")
        assert preview.is_allowed_extension is False

    def test_non_http_scheme_raises(self):
        with pytest.raises(ValueError, match="http/https"):
            preview_url("ftp://example.com/data.csv")

    @patch("requests.head", side_effect=Exception("boom"))
    def test_head_failure_is_best_effort_not_fatal(self, mock_head):
        import requests

        mock_head.side_effect = requests.RequestException("unreachable")
        preview = preview_url("https://example.com/data.csv")
        assert preview.content_length is None
        assert preview.hostname == "example.com"


class TestDownloadFile:
    def test_rejects_disallowed_extension_without_any_request(self, tmp_path):
        dest = tmp_path / "tool.exe"
        with patch("requests.get") as mock_get:
            with pytest.raises(UnsupportedFileTypeError):
                download_file("https://example.com/tool.exe", dest)
            mock_get.assert_not_called()
        assert not dest.exists()

    @patch("requests.get")
    def test_downloads_full_file_and_computes_checksum(self, mock_get, tmp_path):
        content = b"race_date,course\n2024-01-01,Ascot\n"
        mock_get.return_value = _mock_get_response(200, [content[:10], content[10:]], content_length=len(content))
        dest = tmp_path / "races.csv"

        progress_events = []
        result = download_file(
            "https://example.com/races.csv", dest, on_progress=lambda p: progress_events.append(p)
        )

        assert dest.read_bytes() == content
        assert result.bytes_downloaded == len(content)
        assert result.resumed is False
        assert len(result.sha256) == 64
        assert progress_events[-1].bytes_downloaded == len(content)
        assert progress_events[-1].percent == pytest.approx(100.0)

    @patch("requests.get")
    def test_resumes_partial_download_via_range_header(self, mock_get, tmp_path):
        dest = tmp_path / "races.csv"
        dest.write_bytes(b"race_date,course\n")
        remaining = b"2024-01-01,Ascot\n"
        mock_get.return_value = _mock_get_response(206, [remaining])

        result = download_file("https://example.com/races.csv", dest)

        assert dest.read_bytes() == b"race_date,course\n2024-01-01,Ascot\n"
        assert result.resumed is True
        call_headers = mock_get.call_args.kwargs["headers"]
        assert call_headers["Range"] == "bytes=17-"

    @patch("requests.get")
    def test_restarts_from_zero_when_server_ignores_range(self, mock_get, tmp_path):
        dest = tmp_path / "races.csv"
        dest.write_bytes(b"STALE PARTIAL DATA")
        full_content = b"race_date,course\n2024-01-01,Ascot\n"
        mock_get.return_value = _mock_get_response(200, [full_content])

        result = download_file("https://example.com/races.csv", dest)

        assert dest.read_bytes() == full_content
        assert result.bytes_downloaded == len(full_content)

    @patch("time.sleep", return_value=None)
    @patch("requests.get")
    def test_retries_on_500_then_succeeds(self, mock_get, _mock_sleep, tmp_path):
        content = b"data"
        mock_get.side_effect = [
            _mock_get_response(500, []),
            _mock_get_response(200, [content], content_length=len(content)),
        ]
        dest = tmp_path / "races.csv"
        result = download_file("https://example.com/races.csv", dest)
        assert result.bytes_downloaded == len(content)
        assert mock_get.call_count == 2

    @patch("time.sleep", return_value=None)
    @patch("requests.get")
    def test_exhausts_retries_and_raises(self, mock_get, _mock_sleep, tmp_path):
        mock_get.return_value = _mock_get_response(503, [])
        dest = tmp_path / "races.csv"
        with pytest.raises(DownloadHttpError, match="Exhausted"):
            download_file("https://example.com/races.csv", dest, max_retries=3)
        assert mock_get.call_count == 3

    @patch("requests.get")
    def test_401_raises_immediately_without_retry(self, mock_get, tmp_path):
        mock_get.return_value = _mock_get_response(401, [])
        dest = tmp_path / "races.csv"
        with pytest.raises(DownloadHttpError, match="401"):
            download_file("https://example.com/races.csv", dest)
        assert mock_get.call_count == 1

    @patch("requests.get")
    def test_404_raises_immediately_without_retry(self, mock_get, tmp_path):
        mock_get.return_value = _mock_get_response(404, [])
        dest = tmp_path / "races.csv"
        with pytest.raises(DownloadHttpError, match="404"):
            download_file("https://example.com/races.csv", dest)
        assert mock_get.call_count == 1

    @patch("requests.get")
    def test_checksum_mismatch_raises(self, mock_get, tmp_path):
        content = b"data"
        mock_get.return_value = _mock_get_response(200, [content], content_length=len(content))
        dest = tmp_path / "races.csv"
        with pytest.raises(DownloadHttpError, match="Checksum mismatch"):
            download_file("https://example.com/races.csv", dest, expected_sha256="0" * 64)

    @patch("requests.get")
    def test_correct_checksum_passes(self, mock_get, tmp_path):
        import hashlib

        content = b"data"
        expected = hashlib.sha256(content).hexdigest()
        mock_get.return_value = _mock_get_response(200, [content], content_length=len(content))
        dest = tmp_path / "races.csv"
        result = download_file("https://example.com/races.csv", dest, expected_sha256=expected)
        assert result.sha256 == expected
