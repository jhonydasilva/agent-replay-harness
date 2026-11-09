from benchmarks.run_benchmarks import benchmark, render_markdown


def test_benchmark_counts_strict_and_injected_runs():
    metrics = benchmark(6)
    assert metrics["strict_matching_runs"] == 6
    assert metrics["strict_matching_decisions"] == metrics["total_decisions"]
    assert sum(row["count"] for row in metrics["scenarios"]) == 6
    assert all(row["divergence"] == row["count"] for row in metrics["scenarios"])


def test_benchmark_renders_measured_metrics_without_manual_file_edits():
    markdown = render_markdown(benchmark(3))
    assert "3/3 (100.00%)" in markdown
    assert "Direct fake-agent recording" in markdown
    assert "Strict trace replay" in markdown
    assert "fail_fast" in markdown
