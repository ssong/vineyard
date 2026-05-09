"""cost_for_usage — Anthropic list pricing for the live cost ticker."""

from vineyard.llm.gateway import cost_for_usage


def test_opus_input_output():
    # 10k in @ $15/M + 5k out @ $75/M = 0.15 + 0.375 = 0.525
    assert cost_for_usage("plan", input_tokens=10_000, output_tokens=5_000) == 0.525
    assert cost_for_usage("judge", input_tokens=10_000, output_tokens=5_000) == 0.525


def test_sonnet_input_output():
    # 10k in @ $3/M + 5k out @ $15/M = 0.030 + 0.075 = 0.105
    assert cost_for_usage("code", input_tokens=10_000, output_tokens=5_000) == 0.105


def test_haiku_input_output():
    # 10k in @ $0.80/M + 5k out @ $4/M = 0.008 + 0.020 = 0.028
    assert cost_for_usage("fast", input_tokens=10_000, output_tokens=5_000) == 0.028


def test_cache_read_is_ten_percent_of_input():
    # 10k cache reads on opus: 10k * 15 * 0.10 / 1M = 0.015
    cost = cost_for_usage("plan", cache_read_tokens=10_000)
    assert abs(cost - 0.015) < 1e-9


def test_cache_write_is_125_percent_of_input():
    # 10k cache writes on opus: 10k * 15 * 1.25 / 1M = 0.1875
    cost = cost_for_usage("plan", cache_write_tokens=10_000)
    assert abs(cost - 0.1875) < 1e-9


def test_zero_tokens_is_zero_cost():
    assert cost_for_usage("plan") == 0.0
    assert cost_for_usage("code", input_tokens=0, output_tokens=0) == 0.0


def test_combined_breakdown():
    # All four token kinds at once
    cost = cost_for_usage(
        "plan",
        input_tokens=1_000,
        output_tokens=200,
        cache_read_tokens=9_000,
        cache_write_tokens=500,
    )
    expected = (1_000 * 15 + 500 * 15 * 1.25 + 9_000 * 15 * 0.10 + 200 * 75) / 1_000_000
    assert abs(cost - expected) < 1e-9
