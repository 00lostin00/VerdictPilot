from verdictpilot.evals import run_offline_evals


def test_offline_eval_suite(settings) -> None:
    result = run_offline_evals(settings)
    assert result["cases"] == 7
    assert result["retrieval_hit_at_3"] == 1.0
    assert result["execution_classification_accuracy"] == 1.0
