"""Sanity tests for the configuration module. This is the first real
test in the project and verifies Phase 1 is actually wired correctly."""

from iptv_manager.config.settings import PublishTarget, Settings, get_settings


def test_settings_load_with_defaults():
    settings = Settings(github_repository=None)
    assert settings.publish_target == PublishTarget.BOTH
    assert settings.master_playlist_filename == "master.m3u"


def test_get_settings_is_cached():
    assert get_settings() is get_settings()


def test_raw_github_url_built_correctly():
    settings = Settings(github_repository="budi/iptv-repo", github_branch="main")
    assert settings.raw_github_url == (
        "https://raw.githubusercontent.com/budi/iptv-repo/main/"
        "data/master/master.m3u"
    )


def test_github_pages_url_built_correctly():
    settings = Settings(github_repository="budi/iptv-repo")
    assert settings.github_pages_url == "https://budi.github.io/iptv-repo/master.m3u"


def test_no_repository_means_no_urls():
    settings = Settings(github_repository=None)
    assert settings.raw_github_url is None
    assert settings.github_pages_url is None


def test_path_traversal_rejected():
    import pytest

    with pytest.raises(ValueError):
        Settings(data_dir="../../etc")
