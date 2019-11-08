#!/usr/bin/env python3
# Script for downloading mypyc-compiled mypy wheels in preparation for a release

import os
import os.path
import sys
from urllib.request import urlopen


PLATFORMS = [
    'macosx_10_{macos_ver}_x86_64',
    'manylinux1_x86_64',
    'win_amd64',
]
MIN_VER = 5
MAX_VER = 8
BASE_URL = "https://github.com/mypyc/mypy_mypyc-wheels/releases/download"
URL = "{base}/v{version}/mypy-{version}-cp3{pyver}-cp3{pyver}{abi_tag}-{platform}.whl"

def download(url):
    print('Downloading', url)
    name = os.path.join('dist', os.path.split(url)[1])
    with urlopen(url) as f:
        data = f.read()
    with open(name, 'wb') as f:
        f.write(data)

def download_files(version):
    for pyver in range(MIN_VER, MAX_VER + 1):
        for platform in PLATFORMS:
            abi_tag = "" if pyver >= 8 else "m"
            macos_ver = 9 if pyver >= 8 else 6
            url = URL.format(
                base=BASE_URL,
                version=version,
                pyver=pyver,
                abi_tag=abi_tag,
                platform=platform.format(macos_ver=macos_ver)
            )
            # argh, there is an inconsistency here and I don't know why
            if 'win_' in platform:
                parts = url.rsplit('/', 1)
                parts[1] = parts[1].replace("+dev", ".dev")
                url = '/'.join(parts)

            download(url)

def main(argv):
    if len(argv) != 2:
        sys.exit("Usage: download-mypy-wheels.py version")

    os.makedirs('dist', exist_ok=True)
    download_files(argv[1])

if __name__ == '__main__':
    main(sys.argv)
