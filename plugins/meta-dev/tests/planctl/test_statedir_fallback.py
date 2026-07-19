"""Focused coverage for managed-sandbox planctl state placement.

All paths are pytest temporaries.  No test writes to the live home/cache.
"""
import errno
import os
import stat

import pytest

from planctl import statedir


@pytest.fixture(autouse=True)
def _reset_fallback_notice(monkeypatch):
    monkeypatch.setattr(statedir, "_FALLBACK_NOTICE_EMITTED", False)


def _automatic_state(monkeypatch, tmp_path):
    """Enable automatic placement while keeping every candidate hermetic."""
    home = tmp_path / "home"
    temp = tmp_path / "tmp"
    root = tmp_path / "project"
    home.mkdir()
    temp.mkdir()
    root.mkdir()
    monkeypatch.delenv("META_DEV_STATE_DIR", raising=False)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("META_DEV_ROOT", str(root))
    monkeypatch.setattr(statedir.tempfile, "gettempdir", lambda: str(temp))
    monkeypatch.setattr(statedir, "_fs_of", lambda _path: ("ext4", "rw"))
    return home, temp, root


def test_explicit_override_is_verbatim_and_has_first_priority(
    monkeypatch, tmp_path, capsys
):
    override = str(tmp_path / "exact-override")
    monkeypatch.setenv("META_DEV_STATE_DIR", override)
    monkeypatch.setattr(
        statedir,
        "project_root",
        lambda: pytest.fail("explicit override must bypass project resolution"),
    )
    monkeypatch.setattr(
        statedir,
        "_fallback_state_dir",
        lambda _slug: pytest.fail("explicit override must never fall back"),
    )

    assert statedir.state_dir() == override
    assert os.path.isdir(override)
    assert capsys.readouterr().err == ""


def test_writable_home_uses_normal_per_project_cache(monkeypatch, tmp_path, capsys):
    home, _temp, root = _automatic_state(monkeypatch, tmp_path)

    selected = statedir.state_dir()

    expected = home / ".cache" / "meta-dev" / statedir.slugify(str(root))
    assert selected == str(expected)
    assert stat.S_IMODE(os.stat(selected).st_mode) == 0o700
    assert capsys.readouterr().err == ""


def test_forced_erofs_falls_back_stably_and_notices_once(
    monkeypatch, tmp_path, capsys
):
    _home, temp, root = _automatic_state(monkeypatch, tmp_path)
    calls = []

    def readonly(_slug):
        calls.append(True)
        raise OSError(errno.EROFS, "forced read-only cache")

    monkeypatch.setattr(statedir, "_normal_state_dir", readonly)

    first = statedir.state_dir()
    second = statedir.state_dir()

    expected = (
        temp
        / ("meta-dev-state-%s" % os.getuid())
        / statedir.slugify(str(root))
    )
    assert first == second == str(expected)
    assert len(calls) == 2
    assert stat.S_IMODE(os.stat(expected.parent).st_mode) == 0o700
    assert stat.S_IMODE(os.stat(expected).st_mode) == 0o700
    notices = capsys.readouterr().err.splitlines()
    assert notices == [
        "planctl: user cache is read-only; using private temp state at %s"
        % expected
    ]


def test_failed_real_write_probe_falls_back(monkeypatch, tmp_path):
    home, temp, root = _automatic_state(monkeypatch, tmp_path)
    real_probe = statedir._write_probe

    def deny_normal_cache(path):
        if os.path.commonpath((str(home), path)) == str(home):
            raise PermissionError(errno.EACCES, "managed sandbox denied write")
        real_probe(path)

    monkeypatch.setattr(statedir, "_write_probe", deny_normal_cache)

    selected = statedir.state_dir()

    assert selected == str(
        temp
        / ("meta-dev-state-%s" % os.getuid())
        / statedir.slugify(str(root))
    )


@pytest.mark.parametrize("failure_errno", [errno.ENOSPC, errno.EIO])
def test_unrelated_normal_cache_errors_propagate(
    monkeypatch, tmp_path, failure_errno
):
    _automatic_state(monkeypatch, tmp_path)
    monkeypatch.setattr(
        statedir,
        "_normal_state_dir",
        lambda _slug: (_ for _ in ()).throw(
            OSError(failure_errno, "must not be hidden")
        ),
    )
    monkeypatch.setattr(
        statedir,
        "_fallback_state_dir",
        lambda _slug: pytest.fail("unrelated errors must not trigger fallback"),
    )

    with pytest.raises(OSError) as caught:
        statedir.state_dir()
    assert caught.value.errno == failure_errno


def test_symlinked_temp_root_is_rejected(monkeypatch, tmp_path):
    _home, temp, _root = _automatic_state(monkeypatch, tmp_path)
    uid_root = temp / ("meta-dev-state-%s" % os.getuid())
    real = temp / "attacker-target"
    real.mkdir()
    uid_root.symlink_to(real, target_is_directory=True)
    monkeypatch.setattr(
        statedir,
        "_normal_state_dir",
        lambda _slug: (_ for _ in ()).throw(OSError(errno.EROFS, "forced")),
    )

    with pytest.raises(PermissionError, match="unsafe symlink"):
        statedir.state_dir()


def test_wrong_owner_temp_root_is_rejected(monkeypatch, tmp_path):
    _home, temp, _root = _automatic_state(monkeypatch, tmp_path)
    real_uid = os.getuid()
    fake_uid = real_uid + 1
    wrong_owner_root = temp / ("meta-dev-state-%s" % fake_uid)
    wrong_owner_root.mkdir(mode=0o700)
    monkeypatch.setattr(statedir.os, "getuid", lambda: fake_uid)
    monkeypatch.setattr(
        statedir,
        "_normal_state_dir",
        lambda _slug: (_ for _ in ()).throw(OSError(errno.EACCES, "forced")),
    )

    with pytest.raises(PermissionError, match="owned by uid"):
        statedir.state_dir()


def test_automatic_state_still_refuses_9p(monkeypatch, tmp_path):
    _automatic_state(monkeypatch, tmp_path)
    monkeypatch.setattr(statedir, "_fs_of", lambda _path: ("9p", "rw"))
    monkeypatch.setattr(
        statedir,
        "_fallback_state_dir",
        lambda _slug: pytest.fail("9p refusal must not be bypassed"),
    )

    with pytest.raises(SystemExit, match="refusing to write state onto"):
        statedir.state_dir()


def test_fallback_state_also_refuses_9p(monkeypatch, tmp_path):
    _automatic_state(monkeypatch, tmp_path)
    monkeypatch.setattr(
        statedir,
        "_normal_state_dir",
        lambda _slug: (_ for _ in ()).throw(OSError(errno.EROFS, "forced")),
    )
    monkeypatch.setattr(statedir, "_fs_of", lambda _path: ("9p", "rw"))

    with pytest.raises(SystemExit, match="refusing to write state onto"):
        statedir.state_dir()
