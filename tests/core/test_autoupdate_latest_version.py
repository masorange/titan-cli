from titan_cli.utils.autoupdate import latest_installable_version


def _file(name, yanked=False):
    return {"filename": name, "yanked": yanked}


def test_picks_newest_stable_version():
    index = {"files": [
        _file("titan_cli-0.11.0-py3-none-any.whl"),
        _file("titan_cli-0.11.0.tar.gz"),
        _file("titan_cli-0.12.0-py3-none-any.whl"),
    ]}
    assert latest_installable_version(index) == "0.12.0"


def test_ignores_yanked_and_prerelease_versions():
    index = {"files": [
        _file("titan_cli-0.11.0-py3-none-any.whl"),
        _file("titan_cli-0.12.0-py3-none-any.whl", yanked="broken"),
        _file("titan_cli-0.13.0rc1-py3-none-any.whl"),
    ]}
    assert latest_installable_version(index) == "0.11.0"


def test_returns_none_without_files():
    assert latest_installable_version({"files": []}) is None
