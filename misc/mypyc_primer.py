"""Compile downstream projects with a PR's mypyc, comparing failures with its target branch.

See .github/mypyc_primer.toml for the project recipes. This runner intentionally
returns success for completed comparisons, including confirmed regressions;
infrastructure errors return failure. A separate trusted workflow posts results.

The script can also be used to validate changes locally, eg.
    python misc/mypyc_primer.py check --project <name> --head-sha <commit-with-changes>
        --base-sha <base-branch-commit> --output-dir <dir>
It will compile and test the project first using mypyc pinned to <commit-with-changes>.
If it fails, it will repeat the process with mypyc pinned to <base-branch-commit> so
a failure introduced by the change can be distinguished from upstream/infra failures.

The second run can be skipped by passing "--attempt head" on the command line;
in that case --base-sha can be omitted.
Since it's meant for CI it prints a lot of logs to stdout, so for local testing it's best
to redirect it to a file.
"""

from __future__ import annotations

import argparse
import codecs
import json
import os
import re
import selectors
import shlex
import signal
import subprocess
import sys
import tempfile
import time
from collections import deque
from contextlib import nullcontext
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, TypedDict

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

CONFIG = Path(__file__).resolve().parents[1] / ".github/mypyc_primer.toml"
ATTEMPT_TIMEOUT = 20 * 60
CLONE_TIMEOUT = 5 * 60
SHA_PATTERN = re.compile(r"[0-9a-f]{40}")
NAME_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")
CI_FILES = {
    ".github/mypyc_primer.toml",
    ".github/workflows/mypyc_primer.yml",
    ".github/workflows/mypyc_primer_comment.yml",
    "misc/mypyc_primer.py",
}


@dataclass
class Project:
    name: str
    repository: str
    ref: str
    python_version: str
    compiled_modules: list[str]
    setup: list[str]
    build: list[str]
    test: list[str]
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class Attempt:
    status: str
    stage: str
    returncode: int | None = None
    tail: str = ""


class CommandError(Exception):
    def __init__(self, returncode: int, message: str) -> None:
        super().__init__(message)
        self.returncode = returncode


class Log:
    """Stream output to Actions, retaining only a bounded failure excerpt."""

    def __init__(self) -> None:
        self.lines: deque[str] = deque(maxlen=20)

    def write(self, text: str) -> None:
        sys.stdout.write(text)
        sys.stdout.flush()
        if self.lines and not self.lines[-1].endswith("\n"):
            text = self.lines.pop() + text
        # Keep enough of each line to detect truncation, including its newline.
        self.lines.extend(line[-20002:] for line in text.splitlines(keepends=True))

    def tail(self) -> str:
        tail = "".join(self.lines).rstrip("\n")
        # Bound the JSON artifact even if a tool emits a very long final line.
        return tail if len(tail) <= 20000 else "[excerpt truncated]\n" + tail[-20000:]


class CommandOptions(TypedDict):
    env: dict[str, str]
    log: Log
    deadline: float


class AttemptOptions(TypedDict):
    project_source: Path
    project_sha: str
    constraints: Path
    timeout: float


def validate_env(env: object, name: str) -> dict[str, str]:
    if not isinstance(env, dict) or any(
        not isinstance(key, str)
        or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key)
        or not isinstance(value, str)
        or key in {"PATH", "PYTHONPATH", "VIRTUAL_ENV", "PIP_CONSTRAINT", "MYPY_USE_MYPYC"}
        for key, value in env.items()
    ):
        raise ValueError(f"{name}: invalid or reserved environment variable")
    return env


def load_projects(path: Path) -> list[Project]:
    with path.open("rb") as f:
        config = tomllib.load(f)
    entries = config.get("projects")
    if not isinstance(entries, list) or not 1 <= len(entries) <= 100:
        raise ValueError("Catalog must contain 1 to 100 projects")
    shared_env = validate_env(config.get("env", {}), "[env]")
    projects = []
    names: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Each project must be a TOML table")
        name = entry.get("name")
        if not isinstance(name, str) or not NAME_PATTERN.fullmatch(name):
            raise ValueError("Project names must be short lowercase artifact-safe identifiers")
        if name in names:
            raise ValueError(f"Duplicate project: {name}")
        names.add(name)
        for key in ("repository", "ref", "python_version"):
            value = entry.get(key)
            if not isinstance(value, str) or not value or value.startswith("-"):
                raise ValueError(f"{name}: invalid {key}")
        if not entry["repository"].startswith("https://"):
            raise ValueError(f"{name}: repository must use HTTPS")
        if not re.fullmatch(r"3\.\d+", entry["python_version"]):
            raise ValueError(f"{name}: python_version must be a CPython major.minor")
        for key in ("setup", "build", "test", "compiled_modules"):
            value = entry.get(key)
            if not isinstance(value, list) or not value:
                raise ValueError(f"{name}: {key} must be a nonempty list")
            if any(not isinstance(item, str) or not item.strip() for item in value):
                raise ValueError(f"{name}: {key} must contain nonempty strings")
        env = validate_env(entry.get("env", {}), name)
        entry["env"] = {**shared_env, **env}
        projects.append(Project(**entry))
    return projects


def eligible_path(path: str) -> bool:
    if path in CI_FILES or path.startswith(".github/scripts/mypyc_primer_comment"):
        return True
    return (
        path.startswith("mypyc/")
        and not path.startswith(
            ("mypyc/doc/", "mypyc/test/", "mypyc/test-data/", "mypyc/external/googletest/")
        )
        and path != "mypyc/lib-rt/test_capi.cc"
        and not path.endswith((".md", ".rst"))
    )


def changed_paths(source: Path, base: str, head: str) -> list[str]:
    # --no-renames preserves both paths of a rename across the eligibility boundary.
    data = subprocess.check_output(
        ["git", "diff", "--name-only", "--no-renames", "-z", f"{base}...{head}"], cwd=source
    )
    return [os.fsdecode(path) for path in data.split(b"\0") if path]


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf8")


def outputs(values: dict[str, str]) -> None:
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf8") as f:
            for key, value in values.items():
                f.write(f"{key}={value}\n")


def prepare(args: argparse.Namespace) -> None:
    projects = load_projects(args.config)
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
    pr = event["pull_request"]
    head = pr["head"]["sha"]
    if not any(
        eligible_path(path) for path in changed_paths(args.mypy_source, pr["base"]["sha"], head)
    ):
        outputs({"eligible": "false", "matrix": '{"include":[]}'})
        return
    base = pr["base"]["sha"]
    if not SHA_PATTERN.fullmatch(base):
        raise ValueError("Could not resolve target branch")
    matrix = [{"name": p.name, "python_version": p.python_version} for p in projects]
    write_json(
        args.output_dir / "manifest.json",
        {
            "version": 1,
            "pr_number": pr["number"],
            "head_sha": head,
            "base_sha": base,
            "base_ref": pr["base"]["ref"],
            "run_id": os.environ["GITHUB_RUN_ID"],
            "run_attempt": int(os.environ["GITHUB_RUN_ATTEMPT"]),
            "projects": matrix,
        },
    )
    outputs({"eligible": "true", "matrix": json.dumps({"include": matrix}), "base_sha": base})


def execute(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    log: Log,
    deadline: float,
    capture: bool = False,
) -> str:
    log.write(f"\n$ {shlex.join(command)}\n")
    captured: list[str] = []
    with (
        subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE if capture else subprocess.STDOUT,
            start_new_session=True,
        ) as process,
        selectors.DefaultSelector() as selector,
    ):
        for pipe in (process.stdout, process.stderr):
            if pipe is not None:
                selector.register(
                    pipe,
                    selectors.EVENT_READ,
                    codecs.getincrementaldecoder("utf8")(errors="replace"),
                )

        def stream(deadline: float | None) -> None:
            while selector.get_map():
                timeout = None if deadline is None else deadline - time.monotonic()
                if timeout is not None and timeout <= 0:
                    raise subprocess.TimeoutExpired(command, 0)
                for key, _ in selector.select(timeout):
                    data = os.read(key.fd, 8192)
                    text = key.data.decode(data, final=not data)
                    log.write(text)
                    if capture and key.fileobj is process.stdout:
                        captured.append(text)
                    if not data:
                        selector.unregister(key.fileobj)

        try:
            stream(deadline)
            process.wait(timeout=max(0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            # Kill compiler/pytest children too, leaving enough time for the comparison.
            if sys.platform != "win32":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
            stream(None)
            process.wait()
            log.write("\nAttempt exceeded its time limit.\n")
            raise CommandError(124, "Attempt exceeded its time limit") from None
        log.write(f"\nExit code: {process.returncode}\n")
        if process.returncode:
            raise CommandError(process.returncode, f"Command exited with {process.returncode}")
        return "".join(captured)


def clone_checkout(
    repository: str,
    revision: str,
    destination: Path,
    *,
    cwd: Path,
    env: dict[str, str],
    log: Log,
    deadline: float,
) -> None:
    options: CommandOptions = {"env": env, "log": log, "deadline": deadline}
    # Fetch the pinned commit only, including for local repositories where
    # `git clone --depth=1` would otherwise ignore the depth limit.
    execute(["git", "init", "--quiet", str(destination)], cwd=cwd, **options)
    execute(
        ["git", "fetch", "--quiet", "--depth=1", "--no-tags", "--", repository, revision],
        cwd=destination,
        **options,
    )
    execute(["git", "checkout", "--quiet", "--detach", "FETCH_HEAD"], cwd=destination, **options)


def environment(project: Project, venv: Path) -> dict[str, str]:
    env = os.environ.copy()
    for key in (
        "PYTHONPATH",
        "PYTHONHOME",
        "VIRTUAL_ENV",
        "PIP_CONSTRAINT",
        "PIP_BUILD_CONSTRAINT",
        "HATCH_BUILD_HOOKS_ENABLE",
        "MYPY_USE_MYPYC",
        "NO_COLOR",
    ):
        env.pop(key, None)
    env.update(project.env)
    env.update(
        PATH=str(venv / "bin") + os.pathsep + env["PATH"],
        VIRTUAL_ENV=str(venv),
        MYPY_USE_MYPYC="0",
        PYTHONNOUSERSITE="1",
        PYTHONUNBUFFERED="1",
        PIP_DISABLE_PIP_VERSION_CHECK="1",
    )
    return env


def snapshot_dependencies(data: str, path: Path, project: Project) -> None:
    # Direct references (including the project checkout) must not leak between attempts.
    excluded = {project.name.replace("_", "-"), "mypy", "librt"}
    lines = []
    for line in data.splitlines():
        name, separator, _ = line.partition("==")
        if separator and name.lower().replace("_", "-") not in excluded:
            lines.append(line)
    path.write_text("\n".join(lines) + "\n", encoding="utf8")


def run_attempt(
    project: Project,
    *,
    project_source: Path,
    project_sha: str,
    compiler_repository: str,
    compiler_sha: str,
    directory: Path,
    log: Log,
    constraints: Path,
    baseline: bool,
    timeout: float = ATTEMPT_TIMEOUT,
) -> Attempt:
    directory.mkdir()
    venv = directory / "venv"
    source = directory / "project"
    compiler = directory / "compiler"
    env = environment(project, venv)
    if baseline and constraints.exists():
        env["PIP_CONSTRAINT"] = str(constraints)
    deadline = time.monotonic() + timeout
    stage = "setup"
    status = "passed"
    returncode = None
    log.write(
        f"{project.name}: checking compiler {compiler_sha} ({'target branch' if baseline else 'PR'})\n"
    )
    log.write(
        f"Project: {project.name} {project_sha}\nCompiler: {compiler_sha}\nPython: {sys.version}\n"
    )
    kwargs: CommandOptions = {"env": env, "log": log, "deadline": deadline}
    try:
        clone_checkout(str(project_source), project_sha, source, cwd=directory, **kwargs)
        clone_checkout(compiler_repository, compiler_sha, compiler, cwd=directory, **kwargs)
        execute([sys.executable, "-m", "venv", str(venv)], cwd=source, **kwargs)
        execute(
            ["python", "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"],
            cwd=source,
            **kwargs,
        )
        for command in project.setup:
            execute(["bash", "-euo", "pipefail", "-c", command], cwd=source, **kwargs)
        if not baseline:
            snapshot_dependencies(
                execute(
                    ["python", "-m", "pip", "freeze", "--all"], cwd=source, capture=True, **kwargs
                ),
                constraints,
                project,
            )
        stage = "compiler"
        execute(
            ["python", "-m", "pip", "install", "-r", str(compiler / "mypy-requirements.txt")],
            cwd=source,
            **kwargs,
        )
        execute(
            [
                "python",
                "-m",
                "pip",
                "install",
                "--no-build-isolation",
                "--force-reinstall",
                "--no-deps",
                str(compiler / "mypyc/lib-rt"),
                str(compiler),
            ],
            cwd=source,
            **kwargs,
        )
        verify_compiler = (
            "import importlib.metadata, json, pathlib, sys, mypyc; "
            "d = importlib.metadata.distribution('mypy'); "
            "u = json.loads(d.read_text('direct_url.json')); "
            "assert u['url'] == pathlib.Path(sys.argv[1]).as_uri(), u; "
            "assert pathlib.Path(mypyc.__file__).is_relative_to(sys.prefix), mypyc.__file__; "
            "print('Compiler installed from', u['url'])"
        )
        execute(["python", "-c", verify_compiler, str(compiler)], cwd=source, **kwargs)
        if not baseline:
            snapshot_dependencies(
                execute(
                    ["python", "-m", "pip", "freeze", "--all"], cwd=source, capture=True, **kwargs
                ),
                constraints,
                project,
            )
        stage = "build"
        log.write(f"\n{project.name}: compiling\n")
        for command in project.build:
            execute(["bash", "-euo", "pipefail", "-c", command], cwd=source, **kwargs)
        # Detect a recipe that silently replaces the selected compiler while building.
        execute(["python", "-c", verify_compiler, str(compiler)], cwd=source, **kwargs)
        stage = "compiled-import"
        verify_modules = (
            "import importlib, importlib.machinery, pathlib, sys; "
            "modules = [importlib.import_module(n) for n in sys.argv[1:]]; "
            "assert all(m.__file__ and any(m.__file__.endswith(s) for s in "
            "importlib.machinery.EXTENSION_SUFFIXES) and "
            "pathlib.Path(m.__file__).is_relative_to(sys.prefix) for m in modules), "
            "[(m.__name__, m.__file__) for m in modules]; "
            "print('Compiled imports:', [(m.__name__, m.__file__) for m in modules])"
        )
        execute(["python", "-c", verify_modules, *project.compiled_modules], cwd=source, **kwargs)
        stage = "test"
        log.write(f"\n{project.name}: testing\n")
        for command in project.test:
            execute(["bash", "-euo", "pipefail", "-c", command], cwd=source, **kwargs)
    except (CommandError, OSError) as error:
        status = "error" if stage == "setup" or isinstance(error, OSError) else "failed"
        returncode = error.returncode if isinstance(error, CommandError) else None
        log.write(f"\n{stage}: {error}\n")
    return Attempt(status, stage, returncode, log.tail())


def compare(
    project: Project,
    *,
    output_dir: Path,
    work_dir: Path,
    mypy_source: Path,
    head_sha: str | None = None,
    base_sha: str | None = None,
    timeout: float = ATTEMPT_TIMEOUT,
    attempt: str = "both",
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    result: dict[str, Any] = {
        "version": 1,
        "name": project.name,
        "python_version": python_version,
        "head_sha": head_sha,
        "base_sha": base_sha,
        "project_sha": None,
        "head": None,
        "base": None,
    }
    result_path = output_dir / f"{project.name}.json"
    if attempt == "base":
        result = json.loads(result_path.read_text(encoding="utf8"))
        if (
            result["name"] != project.name
            or result["python_version"] != python_version
            or (head_sha is not None and result["head_sha"] != head_sha)
            or not SHA_PATTERN.fullmatch(result["head_sha"])
            or (result["base_sha"] is not None and result["base_sha"] != base_sha)
            or result["head"]["status"] != "failed"
            or result["base"] is not None
            or not SHA_PATTERN.fullmatch(result["project_sha"])
        ):
            raise ValueError("Target-branch comparison does not match the saved PR result")
        result["base_sha"] = base_sha
    # Separate CI steps share the snapshot and constraints in RUNNER_TEMP.
    # Local comparisons retain their automatic temporary-directory cleanup.
    directory_context = (
        tempfile.TemporaryDirectory(prefix=f"{project.name}-", dir=work_dir)
        if attempt == "both"
        else nullcontext(str(work_dir / f"mypyc-primer-{project.name}"))
    )
    with directory_context as temporary:
        directory = Path(temporary)
        project_source = directory / "project-source"
        active = "base" if attempt == "base" else "head"
        log = Log()
        try:
            if attempt == "head":
                directory.mkdir()
            if attempt != "base":
                sha = prepare_project_source(project, directory, project_source, timeout, log)
                if not SHA_PATTERN.fullmatch(sha):
                    raise ValueError("Could not resolve project revision")
                result["project_sha"] = sha
            constraints = directory / "constraints.txt"
            common: AttemptOptions = {
                "project_source": project_source,
                "project_sha": result["project_sha"],
                "constraints": constraints,
                "timeout": timeout,
            }
            if attempt != "base":
                assert head_sha is not None
                result["head"] = asdict(
                    run_attempt(
                        project,
                        **common,
                        compiler_repository=str(mypy_source),
                        compiler_sha=head_sha,
                        directory=directory / "head",
                        log=log,
                        baseline=False,
                    )
                )
            if attempt != "head" and result["head"]["status"] == "failed":
                assert base_sha is not None
                active = "base"
                log = Log()
                result["base"] = asdict(
                    run_attempt(
                        project,
                        **common,
                        compiler_repository=str(mypy_source),
                        compiler_sha=base_sha,
                        directory=directory / "base",
                        log=log,
                        baseline=True,
                    )
                )
        except (CommandError, OSError, ValueError) as error:
            log.write(f"\nInfrastructure error: {error}\n")
            result[active] = asdict(Attempt("error", "setup", tail=log.tail()))
    write_json(result_path, result)
    outputs({"compare_base": str(result["head"]["status"] == "failed").lower()})
    return result


def prepare_project_source(
    project: Project, directory: Path, project_source: Path, timeout: float, log: Log
) -> str:
    kwargs: CommandOptions = {
        "env": environment(project, directory / "unused"),
        "log": log,
        "deadline": time.monotonic() + min(timeout, CLONE_TIMEOUT),
    }
    execute(
        [
            "git",
            "clone",
            "--quiet",
            "--no-checkout",
            "--",
            project.repository,
            str(project_source),
        ],
        cwd=directory,
        **kwargs,
    )
    # Prefer the remote branch; a tag or pinned SHA is also supported.
    try:
        sha = execute(
            ["git", "rev-parse", "--verify", f"refs/remotes/origin/{project.ref}^{{commit}}"],
            cwd=project_source,
            **kwargs,
            capture=True,
        ).strip()
    except CommandError:
        sha = execute(
            ["git", "rev-parse", "--verify", f"{project.ref}^{{commit}}"],
            cwd=project_source,
            **kwargs,
            capture=True,
        ).strip()
    return sha


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=CONFIG)
    subparsers = parser.add_subparsers(dest="command", required=True)
    preparation = subparsers.add_parser("prepare")
    preparation.add_argument("--mypy-source", type=Path, default=Path.cwd())
    preparation.add_argument("--output-dir", type=Path, required=True)
    check = subparsers.add_parser("check")
    check.add_argument("--project", required=True)
    check.add_argument("--mypy-source", type=Path, default=Path.cwd())
    check.add_argument("--head-sha")
    check.add_argument("--base-sha")
    check.add_argument("--attempt", choices=("both", "head", "base"), default="both")
    check.add_argument("--output-dir", type=Path, required=True)
    check.add_argument("--work-dir", type=Path, default=Path(tempfile.gettempdir()))
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args)
        return 0
    for revision in ("head", "base"):
        sha = getattr(args, f"{revision}_sha")
        if sha is None:
            if args.attempt in ("both", revision):
                check.error(f"--{revision}-sha is required for --attempt {args.attempt}")
        elif not SHA_PATTERN.fullmatch(sha):
            check.error(f"--{revision}-sha must be a full commit SHA")
    projects = load_projects(args.config)
    project = next(p for p in projects if p.name == args.project)
    result = compare(
        project,
        output_dir=args.output_dir.resolve(),
        work_dir=args.work_dir.resolve(),
        mypy_source=args.mypy_source.resolve(),
        head_sha=args.head_sha,
        base_sha=args.base_sha,
        attempt=args.attempt,
    )
    for key in ("head", "base"):
        if run_result := result[key]:
            print(f"{key} result: ", run_result["status"])
    return int(any(result[key] and result[key]["status"] == "error" for key in ("head", "base")))


if __name__ == "__main__":
    sys.exit(main())
