from app.analytics.financials import debt_to_equity, enterprise_value, margin, parse_indian_number, premium_discount, revenue_cagr, valuation_multiples, extract_2y_cagr, yoy_revenue_growth, net_debt, net_debt_to_ebitda, roe, roce, ipo_implied_market_cap, derive_post_issue_shares

def test_ipo_implied_market_cap():
    # 500 INR * 20 million shares = 10,000,000,000 INR = 1000 INR Crore
    assert ipo_implied_market_cap(500, 20000000) == 1000.0
    assert ipo_implied_market_cap(500, None) is None
    assert ipo_implied_market_cap(None, 20000000) is None

def test_derive_post_issue_shares():
    assert derive_post_issue_shares(10000, 5000) == 15000
    assert derive_post_issue_shares(10000, None) is None

def test_cagr_and_margins_are_deterministic():
    assert revenue_cagr(100, 144, 2) == 20.0
    assert margin(25, 100) == 25.0
    assert margin(1, 0) is None

def test_yoy_growth():
    assert yoy_revenue_growth(100, 120) == 20.0
    assert yoy_revenue_growth(100, 80) == -20.0
    assert yoy_revenue_growth(None, 100) is None
    assert yoy_revenue_growth(0, 100) is None

def test_extract_2y_cagr():
    periods_valid = [
        {"period_type": "Annual", "period_end": "2022-03-31", "revenue": 100},
        {"period_type": "Interim", "period_end": "2023-09-30", "revenue": 150},
        {"period_type": "Annual", "period_end": "2024-03-31", "revenue": 144}
    ]
    # Ignores interim, finds exactly 2 year gap from 2022 to 2024
    assert extract_2y_cagr(periods_valid) == 20.0

    periods_invalid = [
        {"period_type": "Annual", "period_end": "2022-03-31", "revenue": 100},
        {"period_type": "Annual", "period_end": "2023-03-31", "revenue": 120}
    ]
    assert extract_2y_cagr(periods_invalid) is None

def test_leverage_and_returns():
    assert net_debt(100, 20) == 80.0
    assert net_debt(100, None) is None
    assert net_debt_to_ebitda(100, 20, 40) == 2.0
    assert net_debt_to_ebitda(100, 20, 0) is None
    assert roe(20, 100) == 20.0
    assert roe(None, 100) is None
    # ROCE = EBIT / (total_debt + equity - cash)
    assert roce(30, 50, 100, 50) == 30.0
    assert roce(30, 50, 100, None) is None

def test_valuation_math():
    assert enterprise_value(1000, 150, 50) == 1100
    multiples = valuation_multiples(1000, 150, 50, 200, 100, 50)
    assert multiples["pe"] == 20
    assert multiples["ev_ebitda"] == 11
    assert multiples["ev_sales"] == 5.5
    assert multiples["ps"] == 5.0
    assert multiples["enterprise_value"] == 1100
    
    assert premium_discount(30, 25) == 20
    assert debt_to_equity(40, 100) == .4

def test_indian_number_normalization():
    assert parse_indian_number("2.5 crore") == 2.5
    assert parse_indian_number("250 lakh") == 2.5
    assert parse_indian_number("1,200 million") == 120
    assert parse_indian_number("(100.5)") == -100.5
    assert parse_indian_number("-50 Lakhs") == -0.5
    assert parse_indian_number("0") == 0.0
    assert parse_indian_number("Nil") is None
    assert parse_indian_number("NA") is None
    assert parse_indian_number("-") is None
    assert parse_indian_number(None) is None

def test_deterministic_analytics_with_missing_inputs():
    assert revenue_cagr(None, 144, 2) is None
    assert margin(None, 100) is None
    assert enterprise_value(1000, None, 50) is None
    multiples = valuation_multiples(1000, None, 50, 200, 100, 50)
    assert multiples["enterprise_value"] is None
    assert multiples["ev_ebitda"] is None
