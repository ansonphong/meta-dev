"""Offline argv contract: readonly removes executable tools, not just approvals."""
import json
import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/claude-headless-exec"


@pytest.fixture
def stub_runner(tmp_path):
    binary = tmp_path / "bin"
    binary.mkdir()
    stub = binary / "claude"
    stub.write_text("""#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
Path(os.environ['READONLY_TEST_ARGV']).write_text(json.dumps(sys.argv[1:]))
print(json.dumps({'type':'result','subtype':'success','is_error':False,
                  'result':'Inspected supplied artifact.','num_turns':1,
                  'duration_ms':1,'session_id':'offline-stub'}))
""")
    stub.chmod(0o755)
    project = tmp_path / "project"
    project.mkdir()
    argv_path = tmp_path / "argv.json"
    env = dict(os.environ, PATH=str(binary) + os.pathsep + os.environ["PATH"],
               META_DEV_PLUGIN_ROOT=str(ROOT), META_DEV_PROJECT_ROOT=str(project),
               READONLY_TEST_ARGV=str(argv_path), STALL_SECS="0")
    env.pop("META_DEV_REPOS_FILE", None)

    def run(*flags, backend="opus"):
        # The stub never authenticates or invokes an API, including this fake key.
        env["DEEPSEEK_API_KEY"] = "offline-test-not-a-credential"
        result = subprocess.run(
            ["bash", str(RUNNER), "--backend", backend, "--output", "json",
             "--output-file", str(tmp_path / "result.json"), *flags, "--",
             "Inspect the supplied artifact without edits."],
            env=env, capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert json.loads((tmp_path / "result.json").read_text())["is_error"] is False
        return json.loads(argv_path.read_text())
    return run


def option(argv, name):
    assert argv.count(name) == 1, (name, argv)
    return argv[argv.index(name) + 1]


@pytest.mark.parametrize("flags", [
    ["--readonly"],
    ["--tools", "Bash,Write,Edit,Agent", "--readonly"],
    ["--readonly", "--tools", "Bash,Write,Edit,Agent"],
])
@pytest.mark.parametrize("backend", ["opus", "sonnet", "deep", "fable"])
def test_readonly_is_exact_available_tool_set(stub_runner, flags, backend):
    argv = stub_runner(*flags, backend=backend)
    available = set(option(argv, "--tools").split(","))
    assert available == {"Read", "Glob", "Grep"}
    # A requested Bash redirection, interpreter, file edit, or nested worker has
    # no callable tool; this assertion tests launch confinement without an LLM.
    for requested in ["Bash", "PowerShell", "Write", "Edit", "Agent", "Task", "Skill"]:
        assert requested not in available
    assert option(argv, "--allowedTools") == "Read,Glob,Grep"
    assert option(argv, "--permission-mode") == "dontAsk"
    assert "bypassPermissions" not in argv
    assert "--strict-mcp-config" in argv
    assert json.loads(option(argv, "--mcp-config")) == {"mcpServers": {}}
    assert "--disable-slash-commands" in argv
    assert option(argv, "--setting-sources") == ""
    assert "--no-chrome" in argv
    assert "Only Read, Glob, and Grep are available" in option(argv, "-p")


@pytest.mark.parametrize("flags,expected", [
    ([], "Read,Write,Edit,Bash,Grep,Glob"),
    (["--tools", "Read,Bash"], "Read,Bash"),
])
def test_write_mode_keeps_existing_behavior(stub_runner, flags, expected):
    argv = stub_runner(*flags)
    assert option(argv, "--allowedTools") == expected
    assert option(argv, "--permission-mode") == "bypassPermissions"
    for readonly_flag in ["--tools", "--strict-mcp-config", "--disable-slash-commands",
                          "--setting-sources", "--no-chrome"]:
        assert readonly_flag not in argv
