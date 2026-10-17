from __future__ import annotations

import io
import stat
import tarfile
import zipfile
from pathlib import Path

import pytest

from redot_compat.archive.extract import extract_archive
from redot_compat.config import ArchiveLimits
from redot_compat.errors import UnsafeArchiveError


def _zip(path: Path, members: list[tuple[str, bytes]]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in members:
            archive.writestr(name, content)


def _tar(path: Path, members: list[tuple[str, bytes]]) -> None:
    with tarfile.open(path, "w") as archive:
        for name, content in members:
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))


def test_extracts_safe_zip_after_complete_preflight(tmp_path: Path) -> None:
    archive = tmp_path / "safe.zip"
    target = tmp_path / "target"
    _zip(archive, [("addons/example/plugin.cfg", b"[plugin]\nname='Example'\n")])

    summary = extract_archive(archive, target)

    assert (target / "addons/example/plugin.cfg").is_file()
    assert summary.entry_count == 1
    assert summary.expanded_bytes == 24


@pytest.mark.parametrize(
    "member",
    [
        "../escape.txt",
        "/absolute.txt",
        "C:/drive.txt",
        "//server/share.txt",
        "\\\\server\\share.txt",
        "CON",
        "folder/AUX.txt",
        "folder/.. /ambiguous.txt",
    ],
)
def test_rejects_unsafe_zip_paths_without_partial_target(tmp_path: Path, member: str) -> None:
    archive = tmp_path / "unsafe.zip"
    target = tmp_path / "target"
    _zip(archive, [("safe.txt", b"safe"), (member, b"bad")])

    with pytest.raises(UnsafeArchiveError):
        extract_archive(archive, target)

    assert not target.exists()
    assert not (tmp_path / "escape.txt").exists()


def test_rejects_case_collisions(tmp_path: Path) -> None:
    archive = tmp_path / "collision.zip"
    _zip(archive, [("Addons/Plugin.cfg", b"a"), ("addons/plugin.cfg", b"b")])

    with pytest.raises(UnsafeArchiveError, match="collision"):
        extract_archive(archive, tmp_path / "target")


def test_rejects_zip_symlink(tmp_path: Path) -> None:
    archive_path = tmp_path / "link.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        info = zipfile.ZipInfo("link")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(info, "outside")

    with pytest.raises(UnsafeArchiveError, match="link"):
        extract_archive(archive_path, tmp_path / "target")


def test_rejects_tar_links_and_cleans_target(tmp_path: Path) -> None:
    archive_path = tmp_path / "link.tar"
    with tarfile.open(archive_path, "w") as archive:
        safe = tarfile.TarInfo("safe.txt")
        safe.size = 4
        archive.addfile(safe, io.BytesIO(b"safe"))
        link = tarfile.TarInfo("link")
        link.type = tarfile.SYMTYPE
        link.linkname = "../outside"
        archive.addfile(link)

    target = tmp_path / "target"
    with pytest.raises(UnsafeArchiveError, match="link"):
        extract_archive(archive_path, target)

    assert not target.exists()


def test_rejects_entry_and_ratio_limits(tmp_path: Path) -> None:
    archive = tmp_path / "limits.zip"
    _zip(archive, [("one", b"0" * 10_000), ("two", b"2")])

    with pytest.raises(UnsafeArchiveError):
        extract_archive(
            archive,
            tmp_path / "target",
            limits=ArchiveLimits(max_entries=1, max_expansion_ratio=2),
        )


def test_rejects_non_empty_target(tmp_path: Path) -> None:
    archive = tmp_path / "safe.tar"
    _tar(archive, [("file.txt", b"safe")])
    target = tmp_path / "target"
    target.mkdir()
    (target / "existing").write_text("do not overwrite", encoding="utf-8")

    with pytest.raises(UnsafeArchiveError, match="empty new path"):
        extract_archive(archive, target)

    assert (target / "existing").read_text(encoding="utf-8") == "do not overwrite"


@pytest.mark.parametrize(
    "component",
    [
        "file:stream",
        "a<b",
        "a>b",
        'a"b',
        "a|b",
        "a?b",
        "a*b",
        *[f"a{chr(value)}b" for value in [*range(32), 127]],
        "trailing.",
        "trailing ",
        *[
            f"{name}{suffix}"
            for name in [
                "con",
                "PrN",
                "aux",
                "nul",
                "COM0",
                "LPT0",
                "CONIN$",
                "conout$",
                *[
                    f"{prefix}{digit}"
                    for prefix in ("COM", "LPT")
                    for digit in "123456789\u00b9\u00b2\u00b3"
                ],
            ]
            for suffix in ("", ".txt")
        ],
    ],
)
def test_all_windows_unsafe_components(component: str) -> None:
    from redot_compat.archive.safety import normalize_member_path

    with pytest.raises(UnsafeArchiveError):
        normalize_member_path(f"folder/{component}", ArchiveLimits())


@pytest.mark.parametrize(
    "names",
    [
        ["a", "a/b"],
        ["a/b", "a"],
        ["A", "a/b"],
        ["A/b", "a/c"],
    ],
)
@pytest.mark.parametrize("kind", ["zip", "tar"])
def test_path_conflicts_rejected_before_extraction(
    tmp_path: Path, names: list[str], kind: str
) -> None:
    archive = tmp_path / f"conflict.{kind}"
    (_zip if kind == "zip" else _tar)(archive, [(name, b"data") for name in names])
    target = tmp_path / "target"
    with pytest.raises(UnsafeArchiveError, match=r"conflict|collision"):
        extract_archive(archive, target)
    assert not target.exists()


@pytest.mark.parametrize(
    "kind", [tarfile.LNKTYPE, tarfile.SYMTYPE, tarfile.CHRTYPE, tarfile.BLKTYPE, tarfile.FIFOTYPE]
)
def test_tar_special_members(tmp_path: Path, kind: bytes) -> None:
    path = tmp_path / "special.tar"
    with tarfile.open(path, "w") as archive:
        member = tarfile.TarInfo("special")
        member.type = kind
        member.linkname = "outside"
        archive.addfile(member)
    target = tmp_path / "target"
    with pytest.raises(UnsafeArchiveError, match=r"link|special file"):
        extract_archive(path, target)
    assert not target.exists()


def test_destination_commonpath_value_error_is_unsafe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from redot_compat.archive import extract

    def invalid(paths: object) -> str:
        raise ValueError("different drives")

    monkeypatch.setattr(extract.os.path, "commonpath", invalid)
    with pytest.raises(UnsafeArchiveError):
        extract._safe_destination(tmp_path, Path("file"))


def test_extraction_value_error_is_unsafe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from redot_compat.archive import extract

    archive = tmp_path / "safe.zip"
    _zip(archive, [("file", b"safe")])

    def invalid(*args: object, **kwargs: object) -> None:
        raise ValueError("invalid metadata")

    monkeypatch.setattr(extract, "validate_entries", invalid)
    with pytest.raises(UnsafeArchiveError):
        extract_archive(archive, tmp_path / "target")


def test_zip_stream_exceeding_preflight_size_hits_copy_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import copy

    archive = tmp_path / "underreported.zip"
    _zip(archive, [("file", b"x" * 32)])
    original_infolist = zipfile.ZipFile.infolist
    original_open = zipfile.ZipFile.open

    def underreported(self: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
        infos = [copy.copy(info) for info in original_infolist(self)]
        for info in infos:
            info.file_size = 1
        return infos

    def real_stream(self: zipfile.ZipFile, name, *args, **kwargs):  # type: ignore[no-untyped-def]
        # Keep real ZIP streams while simulating untrusted preflight size metadata.
        if isinstance(name, zipfile.ZipInfo):
            name = name.filename
        return original_open(self, name, *args, **kwargs)

    monkeypatch.setattr(zipfile.ZipFile, "infolist", underreported)
    monkeypatch.setattr(zipfile.ZipFile, "open", real_stream)
    target = tmp_path / "target"
    with pytest.raises(UnsafeArchiveError, match="while extracting"):
        extract_archive(archive, target, limits=ArchiveLimits(max_file_bytes=16))
    assert not target.exists()
