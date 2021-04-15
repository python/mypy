#!/usr/bin/env python3
"""Upload mypy packages to PyPI.

You must first tag the release, use `git push --tags` and wait for the wheel build in CI to complete.

"""

import argparse
import contextlib
import json
import re
import shutil
import subprocess
import tarfile
import tempfile
import venv
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, Iterator, List
from urllib.request import urlopen

BASE = "https://api.github.com/repos"
REPO = "mypyc/mypy_mypyc-wheels"


def is_whl_or_tar(name: str) -> bool:
    return name.endswith(".tar.gz") or name.endswith(".whl")


def get_release_for_tag(tag: str) -> Dict[str, Any]:
    with urlopen(f"{BASE}/{REPO}/releases/tags/{tag}") as f:
        data = json.load(f)
    assert data["tag_name"] == tag
    return data


def download_asset(asset: Dict[str, Any], dst: Path) -> Path:
    name = asset["name"]
    download_url = asset["browser_download_url"]
    assert is_whl_or_tar(name)
    with urlopen(download_url) as src_file:
        with open(dst / name, "wb") as dst_file:
            shutil.copyfileobj(src_file, dst_file)
    return dst / name


def download_all_release_assets(release: Dict[str, Any], dst: Path) -> None:
    print(f"Downloading assets...")
    with ThreadPoolExecutor() as e:
        for asset in e.map(lambda asset: download_asset(asset, dst), release["assets"]):
            print(f"Downloaded {asset}")


def check_sdist(dist: Path, version: str) -> None:
    tarfiles = list(dist.glob("*.tar.gz"))
    assert len(tarfiles) == 1
    sdist = tarfiles[0]
    assert version in sdist.name
    with tarfile.open(sdist) as f:
        version_py = f.extractfile(f"{sdist.name[:-len('.tar.gz')]}/mypy/version.py")
        assert version_py is not None
        version_py_contents = version_py.read().decode("utf-8")

        # strip a git hash from our version, if necessary, since that's not present in version.py
        match = re.match(r"(.*\+dev).*$", version)
        hashless_version = match.group(1) if match else version

        assert (
            f"'{hashless_version}'" in version_py_contents
        ), "Version does not match version.py in sdist"


def spot_check_dist(dist: Path, version: str) -> None:
    items = [item for item in dist.iterdir() if is_whl_or_tar(item.name)]
    assert len(items) > 10
    assert all(version in item.name for item in items)
    assert any(item.name.endswith("py3-none-any.whl") for item in items)


@contextlib.contextmanager
def tmp_twine() -> Iterator[Path]:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_venv_dir = Path(tmp_dir) / "venv"
        venv.create(tmp_venv_dir, with_pip=True)
        pip_exe = tmp_venv_dir / "bin" / "pip"
        subprocess.check_call([pip_exe, "install", "twine"])
        yield tmp_venv_dir / "bin" / "twine"


def upload_dist(dist: Path, dry_run: bool = True) -> None:
    with tmp_twine() as twine:
        files = [item for item in dist.iterdir() if is_whl_or_tar(item.name)]
        cmd: List[Any] = [twine, "upload"]
        cmd += files
        if dry_run:
            print("[dry run] " + " ".join(map(str, cmd)))
        else:
            print(" ".join(map(str, cmd)))
            subprocess.check_call(cmd)


def upload_to_pypi(version: str, dry_run: bool = True) -> None:
    assert re.match(r"v?0\.[0-9]{3}(\+\S+)?$", version)
    if "dev" in version:
        assert dry_run, "Must use --dry-run with dev versions of mypy"
    if version.startswith("v"):
        version = version[1:]

    target_dir = tempfile.mkdtemp()
    dist = Path(target_dir) / "dist"
    dist.mkdir()
    print(f"Temporary target directory: {target_dir}")

    release = get_release_for_tag(f"v{version}")
    download_all_release_assets(release, dist)

    spot_check_dist(dist, version)
    check_sdist(dist, version)
    upload_dist(dist, dry_run)
    print("<< All done! >>")


def main() -> None:
    parser = argparse.ArgumentParser(description="PyPI mypy package uploader")
    parser.add_argument(
        "--dry-run", action="store_true", default=False, help="Don't actually upload packages"
    )
    parser.add_argument("version", help="mypy version to release")
    args = parser.parse_args()

    upload_to_pypi(args.version, args.dry_run)


if __name__ == "__main__":
    main()
