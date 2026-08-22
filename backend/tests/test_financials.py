from app.analytics.financials import debt_to_equity, enterprise_value, margin, parse_indian_number, premium_discount, revenue_cagr, valuation_multiples


def test_cagr_and_margins_are_deterministic():
    assert revenue_cagr(100, 144, 2) == 20.0
    assert margin(25, 100) == 25.0
    assert margin(1, 0) is None


def test_valuation_math():
    assert enterprise_value(1000, 150, 50) == 1100
    multiples = valuation_multiples(1000, 150, 50, 200, 100, 50)
    assert multiples["pe"] == 20
    assert multiples["ev_ebitda"] == 11
    assert premium_discount(30, 25) == 20
    assert debt_to_equity(40, 100) == .4


def test_indian_number_normalization():
    assert parse_indian_number("2.5 crore") == 2.5
    assert parse_indian_number("250 lakh") == 2.5
    assert parse_indian_number("1,200 million") == 120
