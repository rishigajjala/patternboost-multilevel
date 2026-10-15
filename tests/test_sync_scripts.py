"""Exercise deployment targeting with local stubs; never contact an HPC host."""

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ("sync_to_hpc.sh", "sync_git_commit_to_hpc.sh")


@pytest.fixture
def run_sync(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "commands.jsonl"
    stub = f"#!{sys.executable}\n" + '''
import json, os, pathlib, sys
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
body = sys.stdin.read() if name == "ssh" else ""
with open(os.environ["SYNC_TEST_LOG"], "a") as log:
    log.write(json.dumps({"command": name, "args": args, "body": body}) + "\\n")
if name == "git" and args[0] == "rev-parse":
    print("0123456789abcdef0123456789abcdef01234567")
elif name == "ssh" and "ls -td" in body:
    print(args[args.index("--") + 1] + ".tmp.stub")
'''
    for tool in ("git", "ssh", "rsync"):
        path = bin_dir / tool
        path.write_text(stub)
        path.chmod(0o755)
    for name in ("REMOTE", "REMOTE_DIR", "DRY_RUN", "SSH_CONTROL_PATH"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("SYNC_TEST_LOG", str(log))
    monkeypatch.setenv("SSH_CONTROL_PATH", str(tmp_path / "absent.sock"))

    def run(script, **overrides):
        result = subprocess.run(
            ["bash", str(ROOT / "scripts" / script)],
            env={**os.environ, **overrides}, capture_output=True, text=True,
        )
        calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
        return result, calls

    return run


@pytest.mark.parametrize("script", SCRIPTS)
def test_sync_requires_explicit_remote_before_deployment_commands(run_sync, script):
    result, calls = run_sync(script)
    assert result.returncode != 0
    assert "Set REMOTE" in result.stderr
    assert calls == []


@pytest.mark.parametrize("script", SCRIPTS)
@pytest.mark.parametrize("remote_dir", (None, "/scratch/example/project", "~/custom/project"))
def test_sync_targets_selected_account_and_remote_directory(run_sync, script, remote_dir):
    overrides = {"REMOTE": "example@jubail.abudhabi.nyu.edu"}
    if remote_dir is not None:
        overrides["REMOTE_DIR"] = remote_dir
    result, calls = run_sync(script, **overrides)
    assert result.returncode == 0, result.stderr
    expected = remote_dir.removeprefix("~/") if remote_dir else "patternboost/multi-level"
    if remote_dir is None and script == "sync_git_commit_to_hpc.sh":
        expected += "-0123456789ab"
    remote_calls = [call for call in calls if call["command"] in ("ssh", "rsync")]
    assert remote_calls
    assert all("~/" not in arg for call in remote_calls for arg in call["args"])
    if script == "sync_to_hpc.sh":
        assert remote_calls[0]["args"] == [overrides["REMOTE"], f"mkdir -p '{expected}'"]
        assert remote_calls[1]["args"][-1] == f"{overrides['REMOTE']}:{expected}/"
    else:
        for call in (remote_calls[0], remote_calls[-1]):
            assert call["args"][0] == overrides["REMOTE"]
            assert call["args"][call["args"].index("--") + 1] == expected


def test_commit_sync_preserves_control_socket_override(run_sync):
    # macOS pytest temporary paths can exceed the Unix socket path limit.
    with tempfile.TemporaryDirectory(prefix="pbsync-", dir="/tmp") as directory, socket.socket(socket.AF_UNIX) as control:
        control_path = str(Path(directory) / "ssh.sock")
        control.bind(control_path)
        result, calls = run_sync(
            "sync_git_commit_to_hpc.sh", REMOTE="example@jubail.abudhabi.nyu.edu",
            SSH_CONTROL_PATH=control_path,
        )
    assert result.returncode == 0, result.stderr
    assert all(call["args"][:2] == ["-S", control_path] for call in calls if call["command"] == "ssh")
