"""Tests for downstream compiler comparisons, without downloading dependencies."""

from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from misc import mypyc_primer as primer

PROJECT_CONFIG = """\
[[projects]]
name = "example"
repository = "https://github.com/example/project.git"
ref = "main"
python_version = "3.14"
compiled_modules = ["example"]
setup = ["setup-project"]
build = ["build-project"]
test = ["test-project"]
"""


@unittest.skipIf(sys.platform == "win32", "mypyc primer requires POSIX subprocess handling")
class MypycPrimerTests(unittest.TestCase):
    def test_output_streams_before_command_exits(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            release = root / "release"

            class Console(io.StringIO):
                def write(self, text: str) -> int:
                    result = super().write(text)
                    if "\nlive output" in self.getvalue():
                        release.touch()
                    return result

            console = Console()
            log = primer.Log()
            # Even output without a newline must reach the console before exit.
            script = (
                "from pathlib import Path\nimport os, sys, time\n"
                "print('live output', end='', flush=True)\n"
                "while not Path(sys.argv[1]).exists():\n    time.sleep(0.01)\n"
                "print('stderr output', file=sys.stderr, flush=True)\n"
                "os.write(1, b'x' * 8191 + '💚'.encode() + b'\\xff\\n')\n"
            )
            with patch("sys.stdout", console):
                primer.execute(
                    [sys.executable, "-c", script, str(release)],
                    cwd=root,
                    env=os.environ.copy(),
                    log=log,
                    deadline=time.monotonic() + 5,
                )
                self.assertTrue(release.exists())
                log.write("appended\n")
            self.assertEqual(log.tail(), console.getvalue().rstrip("\n"))
            self.assertIn("stderr output\n", console.getvalue())
            self.assertIn("x" * 8191 + "💚�\n", console.getvalue())

    def test_capture_keeps_stderr_out_of_result(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            console = io.StringIO()
            # Exceed pipe capacity on both streams to catch blocked readers.
            script = (
                "import sys\n"
                "sys.stderr.write('!' * 150000)\n"
                "sys.stdout.write('?' * 150000)\n"
            )
            with patch("sys.stdout", console):
                data = primer.execute(
                    [sys.executable, "-c", script],
                    cwd=Path(temporary),
                    env=os.environ.copy(),
                    log=primer.Log(),
                    deadline=time.monotonic() + 5,
                    capture=True,
                )
            self.assertEqual(data.count("?"), 150000)
            self.assertEqual(len(data), 150000)
            # Each character also occurs once in the echoed command. Pipe chunks
            # may interleave, but neither stream should lose any output.
            self.assertEqual(console.getvalue().count("!"), 150001)
            self.assertEqual(console.getvalue().count("?"), 150001)

    def test_attempts_can_run_in_separate_steps(self) -> None:
        for saved_base_sha in (None, "c" * 40):
            with self.subTest(base=saved_base_sha), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                with (
                    patch.object(
                        primer, "prepare_project_source", return_value="a" * 40
                    ) as resolve,
                    patch.object(
                        primer,
                        "run_attempt",
                        side_effect=[
                            primer.Attempt("failed", "test"),
                            primer.Attempt("passed", "test"),
                        ],
                    ) as run,
                    patch.object(primer, "outputs") as outputs,
                ):
                    first = primer.compare(
                        self.project(),
                        output_dir=root / "logs",
                        work_dir=root,
                        mypy_source=root,
                        head_sha="b" * 40,
                        base_sha=saved_base_sha,
                        attempt="head",
                    )
                    self.assertEqual(run.call_count, 1)
                    self.assertIsNone(first["base"])
                    self.assertEqual(first["base_sha"], saved_base_sha)
                    self.assertEqual(outputs.call_args.args[0]["compare_base"], "true")
                    constraints = run.call_args.kwargs["constraints"]
                    constraints.write_text("dependency==1.0\n")
                    # A baseline step cannot silently compare different revisions.
                    mismatches = [("d" * 40, "c" * 40)]
                    if saved_base_sha is not None:
                        mismatches.append(("b" * 40, "d" * 40))
                    for head_sha, base_sha in mismatches:
                        with (
                            self.subTest(head=head_sha, base=base_sha),
                            self.assertRaisesRegex(ValueError, "saved PR result"),
                        ):
                            primer.compare(
                                self.project(),
                                output_dir=root / "logs",
                                work_dir=root,
                                mypy_source=root,
                                head_sha=head_sha,
                                base_sha=base_sha,
                                attempt="base",
                            )
                    second = primer.compare(
                        self.project(),
                        output_dir=root / "logs",
                        work_dir=root,
                        mypy_source=root,
                        base_sha="c" * 40,
                        attempt="base",
                    )
                    self.assertEqual(resolve.call_count, 1)
                    self.assertEqual(second["head"], first["head"])
                    self.assertEqual(second["head_sha"], "b" * 40)
                    self.assertEqual(second["base_sha"], "c" * 40)
                    self.assertEqual(second["base"]["status"], "passed")
                    self.assertEqual(run.call_args.kwargs["project_sha"], "a" * 40)
                    self.assertEqual(run.call_args.kwargs["compiler_repository"], str(root))
                    self.assertEqual(run.call_args.kwargs["compiler_sha"], "c" * 40)
                    self.assertEqual(
                        run.call_args.kwargs["constraints"].read_text(), "dependency==1.0\n"
                    )
                    self.assertNotEqual(
                        run.call_args_list[0].kwargs["directory"],
                        run.call_args.kwargs["directory"],
                    )

    def test_prepare_snapshot_and_docs_skip(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            event = root / "event.json"
            event.write_text(
                json.dumps(
                    {
                        "pull_request": {
                            "number": 42,
                            "head": {"sha": "a" * 40},
                            "base": {
                                "sha": "b" * 40,
                                "ref": "release/test-target",
                                "repo": {"full_name": "example/mypy-fork"},
                            },
                        }
                    }
                )
            )
            config = root / "projects.toml"
            config.write_text(PROJECT_CONFIG)
            args = argparse.Namespace(config=config, mypy_source=root, output_dir=root)
            with (
                patch.dict(
                    os.environ,
                    {
                        "GITHUB_EVENT_PATH": str(event),
                        "GITHUB_RUN_ID": "123",
                        "GITHUB_RUN_ATTEMPT": "1",
                    },
                ),
                patch.object(primer, "changed_paths", return_value=["mypyc/doc/conf.py"]) as paths,
                patch.object(subprocess, "check_output") as git,
                patch.object(primer, "outputs") as outputs,
            ):
                primer.prepare(args)
                git.assert_not_called()
                self.assertEqual(outputs.call_args.args[0]["eligible"], "false")
                paths.return_value = ["mypyc/doc/conf.py", "mypyc/build.py"]
                primer.prepare(args)
                manifest = json.loads((root / "manifest.json").read_text())
                self.assertEqual(manifest["head_sha"], "a" * 40)
                self.assertEqual(manifest["base_sha"], "b" * 40)
                self.assertEqual(manifest["base_ref"], "release/test-target")
                self.assertEqual(outputs.call_args.args[0]["base_sha"], "b" * 40)
                git.assert_not_called()
                self.assertEqual(
                    manifest["projects"], [{"name": "example", "python_version": "3.14"}]
                )
                self.assertEqual(outputs.call_args.args[0]["eligible"], "true")

    def project(self) -> primer.Project:
        return primer.Project(
            name="example",
            repository="https://github.com/example/project.git",
            ref="main",
            python_version="3.14",
            compiled_modules=["example"],
            setup=["setup-project"],
            build=["build-project"],
            test=["test-project"],
        )

    def test_path_eligibility(self) -> None:
        for path in (
            "mypyc/irbuild/main.py",
            "mypyc/lib-rt/CPy.h",
            "mypyc/lib-rt/strings/librt_strings.c",
            ".github/mypyc_primer.toml",
            "misc/mypyc_primer.py",
            ".github/scripts/mypyc_primer_comment.cjs",
        ):
            with self.subTest(path=path):
                self.assertTrue(primer.eligible_path(path))
        for path in (
            "mypyc/doc/conf.py",
            "mypyc/doc/Makefile",
            "mypyc/README.md",
            "mypyc/test/test_run.py",
            "mypyc/test-data/fixtures/testutil.py",
            "mypyc/lib-rt/test_capi.cc",
            "mypyc/external/googletest/src/gtest.cc",
            "mypy/checker.py",
            "test-data/unit/check.test",
        ):
            with self.subTest(path=path):
                self.assertFalse(primer.eligible_path(path))

    def test_entire_diff_and_rename(self) -> None:
        root = Path("repository")
        # Put both sides of a rename beyond GitHub's 300-file path-filter limit.
        expected = [f"unrelated-{index}.py" for index in range(350)]
        expected += ["mypyc/test/renamed.py", "mypyc/renamed.py", "README.md"]
        diff = b"\0".join(os.fsencode(path) for path in expected) + b"\0"
        with patch.object(subprocess, "check_output", return_value=diff):
            paths = primer.changed_paths(root, "base", "head")
        self.assertEqual(paths, expected)
        self.assertTrue(any(primer.eligible_path(path) for path in paths))

    def test_catalog_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "projects.toml"
            path.write_text(PROJECT_CONFIG)
            self.assertEqual(primer.load_projects(path), [self.project()])
            # A duplicate entry cannot overwrite another project's artifacts.
            path.write_text(PROJECT_CONFIG * 2)
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                primer.load_projects(path)
            path.write_text(PROJECT_CONFIG.replace('name = "example"', 'name = "../example"'))
            with self.assertRaisesRegex(ValueError, "artifact-safe"):
                primer.load_projects(path)
            path.write_text(PROJECT_CONFIG + '\n[projects.env]\nPYTHONPATH = "src"\n')
            with self.assertRaisesRegex(ValueError, "reserved"):
                primer.load_projects(path)
            for shared_env in (
                'env = "invalid"\n',
                '[env]\nPYTHONPATH = "src"\n',
                "[env]\nMYPYC_OPT_LEVEL = 0\n",
                '[env]\n"invalid-name" = "value"\n',
            ):
                with self.subTest(env=shared_env):
                    path.write_text(shared_env + PROJECT_CONFIG)
                    with self.assertRaisesRegex(ValueError, "invalid or reserved"):
                        primer.load_projects(path)

    def test_shared_project_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "projects.toml"
            path.write_text(
                '[env]\nCC = "clang"\nMYPYC_OPT_LEVEL = "0"\n'
                + PROJECT_CONFIG
                + '\n[projects.env]\nMYPYC_OPT_LEVEL = "1"\nPROJECT_ONLY = "yes"\n'
                + PROJECT_CONFIG.replace('name = "example"', 'name = "other"')
            )
            first, second = primer.load_projects(path)
            self.assertEqual(
                first.env, {"CC": "clang", "MYPYC_OPT_LEVEL": "1", "PROJECT_ONLY": "yes"}
            )
            self.assertEqual(second.env, {"CC": "clang", "MYPYC_OPT_LEVEL": "0"})
            env = primer.environment(first, Path("/fresh/venv"))
            for name, value in first.env.items():
                self.assertEqual(env[name], value)

    def test_environment_and_dependency_snapshot(self) -> None:
        with patch.dict(
            os.environ, {"PYTHONPATH": "/wrong", "MYPY_USE_MYPYC": "1", "NO_COLOR": "1"}
        ):
            env = primer.environment(self.project(), Path("/fresh/venv"))
        self.assertNotIn("PYTHONPATH", env)
        self.assertNotIn("NO_COLOR", env)
        self.assertEqual(env["MYPY_USE_MYPYC"], "0")
        self.assertTrue(env["PATH"].startswith("/fresh/venv/bin" + os.pathsep))
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "constraints.txt"
            primer.snapshot_dependencies(
                "mypy==1.0\nlibrt==0.16\nexample==2.0\npytest==9.0\n"
                "black @ file:///old/tree\ntyping_extensions==4.16\n",
                path,
                self.project(),
            )
            self.assertEqual(path.read_text(), "pytest==9.0\ntyping_extensions==4.16\n")

    def test_command_pipefail_and_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            log = primer.Log()
            with patch("sys.stdout", io.StringIO()):
                kwargs: primer.CommandOptions = {
                    "env": os.environ.copy(),
                    "log": log,
                    "deadline": time.monotonic() + 5,
                }
                with self.assertRaises(primer.CommandError) as failure:
                    primer.execute(
                        ["bash", "-euo", "pipefail", "-c", "false | cat"], cwd=root, **kwargs
                    )
                self.assertEqual(failure.exception.returncode, 1)
                for script in (
                    "import time; time.sleep(30)",
                    # Closing the pipes must not bypass the process deadline.
                    "import os, time; os.close(1); os.close(2); time.sleep(30)",
                    # Kill children that still hold the output pipe open.
                    "import subprocess, sys, time; "
                    "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)']); "
                    "time.sleep(30)",
                    # A continuously readable pipe must still respect the deadline.
                    "import os\nwhile True: os.write(1, b'x' * 8192)",
                ):
                    kwargs["deadline"] = time.monotonic() + 0.1
                    with (
                        self.subTest(script=script),
                        self.assertRaises(primer.CommandError) as failure,
                    ):
                        primer.execute([sys.executable, "-c", script], cwd=root, **kwargs)
                    self.assertEqual(failure.exception.returncode, 124)
                    self.assertIn("time limit", log.tail())

    def test_infrastructure_failure_keeps_excerpt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)

            def fail(
                project: primer.Project,
                directory: Path,
                source: Path,
                timeout: float,
                log: primer.Log,
            ) -> str:
                log.write("Source checkout failed\n")
                raise primer.CommandError(1, "Cannot fetch project")

            with (
                patch.object(primer, "prepare_project_source", side_effect=fail),
                patch("sys.stdout", io.StringIO()) as console,
            ):
                result = primer.compare(
                    self.project(),
                    output_dir=root / "results",
                    work_dir=root,
                    mypy_source=root,
                    head_sha="b" * 40,
                    base_sha="c" * 40,
                )
            self.assertEqual(result["head"]["status"], "error")
            self.assertEqual(result["head"]["tail"], console.getvalue().rstrip("\n"))
            self.assertEqual(list((root / "results").iterdir()), [root / "results/example.json"])

    def test_failures_run_base_in_fresh_directory(self) -> None:
        for pr_status, base_status in (
            ("passed", None),
            ("failed", "passed"),
            ("failed", "failed"),
            ("failed", "error"),
            ("error", None),
        ):
            with self.subTest(pr=pr_status, base=base_status):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    attempts = [primer.Attempt(pr_status, "build")]
                    if base_status:
                        attempts.append(primer.Attempt(base_status, "test"))
                    with (
                        patch.object(primer, "execute", return_value="a" * 40),
                        patch.object(primer, "run_attempt", side_effect=attempts) as run,
                        patch.object(primer, "outputs"),
                    ):
                        result = primer.compare(
                            self.project(),
                            output_dir=root / "logs",
                            work_dir=root,
                            mypy_source=root,
                            head_sha="b" * 40,
                            base_sha="c" * 40,
                        )
                    self.assertEqual(run.call_count, 2 if base_status else 1)
                    self.assertEqual(result["head"]["status"], pr_status)
                    if base_status:
                        self.assertNotEqual(
                            run.call_args_list[0].kwargs["directory"],
                            run.call_args_list[1].kwargs["directory"],
                        )
                        self.assertEqual(
                            run.call_args_list[0].kwargs["project_sha"],
                            run.call_args_list[1].kwargs["project_sha"],
                        )
                        self.assertEqual(run.call_args_list[1].kwargs["compiler_sha"], "c" * 40)
                        self.assertEqual(
                            run.call_args_list[1].kwargs["compiler_repository"], str(root)
                        )
                        self.assertTrue(run.call_args_list[1].kwargs["baseline"])
                    saved = json.loads((root / "logs/example.json").read_text())
                    self.assertEqual(saved, result)

    def test_attempt_failure_stages(self) -> None:
        for stage in ("setup", "compiler", "build", "compiled-import", "test"):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)

                def execute(command: list[str], **kwargs: object) -> str:
                    match = {
                        "setup": command[-1] == "setup-project",
                        "compiler": "--force-reinstall" in command,
                        "build": command[-1] == "build-project",
                        "compiled-import": command[:2] == ["python", "-c"]
                        and "Compiled imports:" in command[2],
                        "test": command[-1] == "test-project",
                    }
                    if match[stage]:
                        raise primer.CommandError(124, "Timed out")
                    return ""

                with patch.object(primer, "execute", side_effect=execute):
                    result = primer.run_attempt(
                        self.project(),
                        project_source=root,
                        project_sha="a" * 40,
                        compiler_repository=str(root),
                        compiler_sha="b" * 40,
                        directory=root / "attempt",
                        log=primer.Log(),
                        constraints=root / "constraints.txt",
                        baseline=False,
                    )
                self.assertEqual(result.stage, stage)
                self.assertEqual(result.status, "error" if stage == "setup" else "failed")
                self.assertEqual(result.returncode, 124)

    def test_log_keeps_last_20_lines(self) -> None:
        log = primer.Log()
        console = io.StringIO()
        data = "".join(f"line {index}\n" for index in range(100)) + "last line"
        with patch("sys.stdout", console):
            for offset in range(0, len(data), 7):
                log.write(data[offset : offset + 7])
        self.assertEqual(
            log.tail().splitlines(), [f"line {i}" for i in range(81, 100)] + ["last line"]
        )
        self.assertEqual(console.getvalue(), data)

        with patch("sys.stdout", console):
            for _ in range(100):
                log.write("x" * 10000)
            self.assertEqual(log.tail(), "[excerpt truncated]\n" + "x" * 20000)
            # Once a long line falls out of the excerpt, truncation is unnecessary.
            log.write("\n" + data)
        self.assertEqual(
            log.tail().splitlines(), [f"line {i}" for i in range(81, 100)] + ["last line"]
        )
