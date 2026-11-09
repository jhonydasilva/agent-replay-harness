import json
import subprocess
import sys
from pathlib import Path

from src.cli import run_cli
from src.report import summarize_directory
from src.trace_schema import read_trace


ROOT = Path(__file__).resolve().parents[1]


def run_command(*args):
    return subprocess.run(
        [sys.executable, "-m", "src.cli", *map(str, args)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_cli_record_and_replay_end_to_end(tmp_path):
    recorded = tmp_path / "record.json"
    replayed = tmp_path / "replay.json"
    assert run_command("record", "--output", recorded).returncode == 0
    result = run_command("replay", recorded, "--output", replayed)
    assert result.returncode == 0, result.stderr
    assert read_trace(replayed)["comparison"]["identical"] is True


def test_cli_inject_retry_reports_divergence(tmp_path):
    output = tmp_path / "retry.json"
    result = run_command(
        "inject", "examples/traces/success.json", "--fault", "examples/faults/retry.json",
        "--output", output,
    )
    assert result.returncode == 0, result.stderr
    assert "decisions_identical=False" in result.stdout
    assert read_trace(output)["comparison"]["first_divergence"]["decision_index"] == 2


def test_cli_invalid_fault_exits_nonzero_and_does_not_write_trace(tmp_path):
    wrong = tmp_path / "wrong.json"
    wrong.write_text(json.dumps({
        "target_seq": 99,
        "event_type": "tool.call",
        "replacement_response": {"status": "ok", "data": {}},
    }), encoding="utf-8")
    output = tmp_path / "should_not_exist.json"
    result = run_command(
        "inject", "examples/traces/success.json", "--fault", wrong, "--output", output
    )
    assert result.returncode != 0
    assert "FaultTargetNotFound" in result.stderr
    assert not output.exists()


def test_cli_report_prints_success_failure_and_diff(tmp_path, capsys):
    assert run_cli(["record", "--output", str(tmp_path / "original.json")]) == 0
    assert run_cli([
        "inject", "examples/traces/success.json", "--fault", "examples/faults/fail_fast.json",
        "--output", str(tmp_path / "failure.json"),
    ]) == 0
    assert run_cli(["report", str(tmp_path)]) == 0
    text = capsys.readouterr().out
    assert "Success: 1; failure: 1" in text
    assert "first diff at decision 2" in text
    assert summarize_directory(tmp_path)["intentional_divergences"] == 1


def test_cli_refuses_invalid_trace(tmp_path):
    trace = tmp_path / "bad.json"
    trace.write_text("{}", encoding="utf-8")
    assert run_command("replay", trace).returncode == 2
