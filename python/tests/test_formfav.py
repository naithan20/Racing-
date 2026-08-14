import pytest

from racingedge_data.providers.base import ProviderConfigurationError
from racingedge_data.providers.formfav import FormFavProvider


class TestFormFavPlaceholder:
    """FormFav has no real client in this build — see formfav.py's module
    docstring for exactly why (docs access blocked, no secondary source
    confirmed the contract). These tests only confirm the placeholder
    fails loudly and informatively rather than silently returning nothing
    or fabricating data."""

    @pytest.mark.parametrize(
        "method_name",
        ["fetch_form_stats", "fetch_career_stats", "fetch_jockey_stats", "fetch_trainer_stats", "fetch_course_stats"],
    )
    def test_every_method_raises_with_a_clear_explanation(self, method_name):
        provider = FormFavProvider(api_key="fixture-key")
        method = getattr(provider, method_name)
        with pytest.raises(ProviderConfigurationError, match="FORMFAV_API_KEY"):
            method()

    def test_reads_api_key_from_env_var(self, monkeypatch):
        monkeypatch.setenv("FORMFAV_API_KEY", "fixture-env-key")
        provider = FormFavProvider()
        assert provider.api_key == "fixture-env-key"
