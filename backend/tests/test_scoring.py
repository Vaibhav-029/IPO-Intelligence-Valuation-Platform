import pytest
import itertools
from app.analytics.scoring import (
    normalize, avg_valid, score_financial_quality, score_growth,
    score_valuation, score_balance_sheet, score_business_quality,
    score_risk, calculate_overall_score, WEIGHTS
)

def test_monotonicity():
    # EBITDA margin (higher is better)
    assert score_financial_quality(15, 10, 10, 10)["score"] < score_financial_quality(20, 10, 10, 10)["score"]
    
    # PAT margin (higher is better)
    assert score_financial_quality(10, 10, 10, 10)["score"] < score_financial_quality(10, 15, 10, 10)["score"]
    
    # ROE (higher is better)
    assert score_financial_quality(10, 10, 10, 10)["score"] < score_financial_quality(10, 10, 15, 10)["score"]
    
    # ROCE (higher is better)
    assert score_financial_quality(10, 10, 10, 10)["score"] < score_financial_quality(10, 10, 10, 15)["score"]
    
    # Revenue CAGR (higher is better)
    assert score_growth(20, 20)["score"] < score_growth(30, 20)["score"]
    
    # YoY growth (higher is better)
    assert score_growth(20, 20)["score"] < score_growth(20, 30)["score"]
    
    # Debt/Equity (lower is better)
    assert score_balance_sheet(1.5)["score"] < score_balance_sheet(1.0)["score"]
    
    # P/E premium (lower is better, e.g., -20 is better than 0)
    assert score_valuation(0)["score"] < score_valuation(-20)["score"]

def test_clamping():
    # Normal bounds (e.g. 0 to 30)
    assert normalize(-5, 0, 30) == 0.0
    assert normalize(0, 0, 30) == 0.0
    assert normalize(15, 0, 30) == 50.0
    assert normalize(30, 0, 30) == 100.0
    assert normalize(35, 0, 30) == 100.0
    
    # Inverse bounds (e.g. 2.0 to 0.0)
    assert normalize(2.5, 2.0, 0.0) == 0.0
    assert normalize(2.0, 2.0, 0.0) == 0.0
    assert normalize(1.0, 2.0, 0.0) == 50.0
    assert normalize(0.0, 2.0, 0.0) == 100.0
    assert normalize(-0.5, 2.0, 0.0) == 100.0
    
    # P/E premium/discount (+50 to -50)
    assert normalize(60, 50, -50) == 0.0
    assert normalize(50, 50, -50) == 0.0
    assert normalize(0, 50, -50) == 50.0
    assert normalize(-50, 50, -50) == 100.0
    assert normalize(-60, 50, -50) == 100.0

def test_missing_data_behavior():
    # Missing sub-metric
    res = score_growth(None, 20)
    assert res["sub_metrics"]["revenue_cagr"] is None
    assert res["sub_metrics"]["yoy_growth"] == 50.0
    assert res["score"] == 50.0 # Dimension is not 0, it's avg of valid siblings
    
    # Missing dimension
    dim_res = score_growth(None, None)
    assert dim_res["score"] is None
    
    # Calculate overall score missing behavior
    dims = {
        "financial_quality": {"score": 50.0, "sub_metrics": {"a": 50}},
        "growth": dim_res, # None
        "valuation": {"score": 50.0, "sub_metrics": {"a": 50}},
        "balance_sheet": {"score": 50.0, "sub_metrics": {"a": 50}},
        "business_quality": {"score": 50.0, "sub_metrics": {"a": 50}},
        "risk": {"score": 50.0, "sub_metrics": {"a": 50}},
    }
    res_overall = calculate_overall_score(dims)
    assert res_overall["overall_score"] == 50.0
    assert res_overall["coverage"]["overall_effective_weight"] == 80.0
    assert res_overall["coverage"]["growth"]["available"] is False

def test_redistribution_property():
    base_dims = {
        "financial_quality": {"score": 100.0, "sub_metrics": {"a": 100}},
        "growth": {"score": 100.0, "sub_metrics": {"a": 100}},
        "valuation": {"score": 100.0, "sub_metrics": {"a": 100}},
        "balance_sheet": {"score": 100.0, "sub_metrics": {"a": 100}},
        "business_quality": {"score": 100.0, "sub_metrics": {"a": 100}},
        "risk": {"score": 100.0, "sub_metrics": {"a": 100}},
    }
    keys = list(base_dims.keys())
    
    # Test all possible subsets of available dimensions
    for i in range(1, len(keys) + 1):
        for subset in itertools.combinations(keys, i):
            test_dims = {}
            expected_weight = 0.0
            for k in keys:
                if k in subset:
                    test_dims[k] = base_dims[k]
                    expected_weight += WEIGHTS[k]
                else:
                    test_dims[k] = {"score": None, "sub_metrics": {"a": None}}
            
            res = calculate_overall_score(test_dims)
            # Score must remain 100.0 because all available dimensions are 100.0
            assert res["overall_score"] == 100.0, f"Failed on subset {subset}"
            assert res["coverage"]["overall_effective_weight"] == round(expected_weight * 100, 2)
            
            # Exact one dimension available
            if i == 1:
                assert res["overall_score"] == test_dims[subset[0]]["score"]

def test_all_dimensions_unavailable():
    empty_dims = {k: {"score": None, "sub_metrics": {"a": None}} for k in WEIGHTS.keys()}
    res = calculate_overall_score(empty_dims)
    assert res["overall_score"] is None
    assert res["coverage"]["overall_effective_weight"] == 0.0

def test_score_bounds():
    # Score bounding: Should never be < 0 or > 100
    res = score_financial_quality(-50, -50, -50, -50)
    assert res["score"] == 0.0
    
    res = score_financial_quality(100, 100, 100, 100)
    assert res["score"] == 100.0

    res = score_growth(-50, -50)
    assert res["score"] == 0.0
    
    res = score_valuation(1000)
    assert res["score"] == 0.0
    
    res = score_balance_sheet(100)
    assert res["score"] == 0.0

def test_risk_behavior():
    # No risk records
    assert score_risk([])["score"] is None
    assert score_risk(None)["score"] is None
    
    # High risk
    assert score_risk([{"severity": "High"}])["score"] == 80.0
    
    # Medium risk
    assert score_risk([{"severity": "Medium"}])["score"] == 90.0
    
    # Low risk
    assert score_risk([{"severity": "Low"}])["score"] == 95.0
    
    # Mixed risks
    res = score_risk([{"severity": "High"}, {"severity": "Low"}])
    assert res["score"] == 75.0
    
    # Penalties accumulate and floor at 0
    many_risks = [{"severity": "High"}] * 6
    assert score_risk(many_risks)["score"] == 0.0
    
    # More severe risk cannot improve score
    assert score_risk([{"severity": "High"}])["score"] < score_risk([{"severity": "Medium"}])["score"]

def test_business_quality():
    # manual score maps 0 -> 0, 10 -> 100
    assert score_business_quality(0)["score"] == 0.0
    assert score_business_quality(10)["score"] == 100.0
    assert score_business_quality(5)["score"] == 50.0
    
    # missing -> NULL
    res = score_business_quality(None)
    assert res["score"] is None
    assert res["sub_metrics"]["manual_business_quality"] is None

def test_valuation_behavior():
    # P/E mapping bounds
    assert score_valuation(50)["score"] == 0.0
    assert score_valuation(0)["score"] == 50.0
    assert score_valuation(-50)["score"] == 100.0
    
    # Beyond bounds
    assert score_valuation(100)["score"] == 0.0
    assert score_valuation(-100)["score"] == 100.0
    
    # missing peer median/target -> NULL
    assert score_valuation(None)["score"] is None

def test_cross_dimension_sensitivity():
    # Construct base synthetic scores
    base = {
        "financial_quality": {"score": 50.0, "sub_metrics": {"a": 50}},
        "growth": {"score": 50.0, "sub_metrics": {"a": 50}},
        "valuation": {"score": 50.0, "sub_metrics": {"a": 50}},
        "balance_sheet": {"score": 50.0, "sub_metrics": {"a": 50}},
        "business_quality": {"score": 50.0, "sub_metrics": {"a": 50}},
        "risk": {"score": 50.0, "sub_metrics": {"a": 50}},
    }
    base_res = calculate_overall_score(base)
    assert base_res["overall_score"] == 50.0
    
    # Improving one available dimension raises overall score
    better = base.copy()
    better["financial_quality"] = {"score": 100.0, "sub_metrics": {"a": 100}}
    better_res = calculate_overall_score(better)
    assert better_res["overall_score"] > 50.0
    
    # Worsening one available dimension lowers overall score
    worse = base.copy()
    worse["financial_quality"] = {"score": 0.0, "sub_metrics": {"a": 0}}
    worse_res = calculate_overall_score(worse)
    assert worse_res["overall_score"] < 50.0
    
    # Missing dimension redistributes, score stays 50 (since rest are 50)
    missing = base.copy()
    missing["financial_quality"] = {"score": None, "sub_metrics": {"a": None}}
    missing_res = calculate_overall_score(missing)
    assert missing_res["overall_score"] == 50.0
    assert missing_res["coverage"]["overall_effective_weight"] == 80.0
