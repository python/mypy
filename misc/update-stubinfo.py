import argparse
from pathlib import Path

import tomli as tomllib


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--typeshed", type=Path, required=True)
    args = parser.parse_args()

    typeshed_p_to_d = {}
    for stub in (args.typeshed / "stubs").iterdir():
        if not stub.is_dir():
            continue
        try:
            metadata = tomllib.loads((stub / "METADATA.toml").read_text())
        except FileNotFoundError:
            continue
        d = metadata.get("stub_distribution", f"types-{stub.name}")
        for p in stub.iterdir():
            if not p.stem.isidentifier():
                continue
            if p.is_dir() and not any(f.suffix == ".pyi" for f in p.iterdir()):
                # ignore namespace packages
                continue
            if p.is_file() and p.suffix != ".pyi":
                continue
            typeshed_p_to_d[p.stem] = d

    import mypy.stubinfo

    mypy_p = set(mypy.stubinfo.non_bundled_packages_flat) | set(
        mypy.stubinfo.legacy_bundled_packages
    )

    for p in typeshed_p_to_d.keys() & mypy_p:
        mypy_d = mypy.stubinfo.non_bundled_packages_flat.get(p)
        mypy_d = mypy_d or mypy.stubinfo.legacy_bundled_packages.get(p)
        if mypy_d != typeshed_p_to_d[p]:
            raise ValueError(
                f"stub_distribution mismatch for {p}: {mypy_d} != {typeshed_p_to_d[p]}"
            )

    print("=" * 40)
    print("Add the following to non_bundled_packages_flat:")
    print("=" * 40)
    for p in sorted(typeshed_p_to_d.keys() - mypy_p):
        if p in {
            "pika",  # see comment in stubinfo.py
            "distutils",  # don't recommend types-setuptools here
        }:
            continue
        print(f'"{p}": "{typeshed_p_to_d[p]}",')
    print()

    print("=" * 40)
    print("Consider removing the following packages no longer in typeshed:")
    print("=" * 40)
    for p in sorted(mypy_p - typeshed_p_to_d.keys()):
        if p in {"lxml", "pandas", "scipy"}:  # never in typeshed
            continue
        print(p)


if __name__ == "__main__":
    main()
