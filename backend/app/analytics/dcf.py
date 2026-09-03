from typing import List

def run_dcf(
    base_revenue: float,
    revenue_growth_rate: float,
    ebitda_margin: float,
    tax_rate: float,
    d_and_a_pct: float,
    capex_pct: float,
    nwc_pct: float,
    wacc: float,
    terminal_growth_rate: float,
    years: int
) -> dict:
    """
    Runs a deterministic DCF projection and valuation using standard year-end discounting.
    FCFF = EBIT * (1 - tax) + D&A - CapEx - Change_in_NWC
    """
    projections = []
    current_revenue = base_revenue
    
    for year in range(1, years + 1):
        current_revenue = current_revenue * (1 + revenue_growth_rate)
        
        ebitda = current_revenue * ebitda_margin
        d_and_a = current_revenue * d_and_a_pct
        ebit = ebitda - d_and_a
        taxes = ebit * tax_rate
        capex = current_revenue * capex_pct
        change_in_nwc = current_revenue * nwc_pct
        
        fcff = ebit * (1 - tax_rate) + d_and_a - capex - change_in_nwc
        
        projections.append({
            "year": year,
            "revenue": round(current_revenue, 2),
            "ebitda": round(ebitda, 2),
            "ebitda_margin": ebitda_margin,
            "d_and_a": round(d_and_a, 2),
            "ebit": round(ebit, 2),
            "taxes": round(taxes, 2),
            "capex": round(capex, 2),
            "change_in_nwc": round(change_in_nwc, 2),
            "fcff": round(fcff, 2),
            "present_value": round(fcff / ((1 + wacc) ** year), 2)
        })
        
    # Terminal Value
    terminal_fcff = projections[-1]["fcff"] * (1 + terminal_growth_rate)
    terminal_value = terminal_fcff / (wacc - terminal_growth_rate)
    terminal_pv = terminal_value / ((1 + wacc) ** years)
    
    enterprise_value = sum(p["present_value"] for p in projections) + terminal_pv
    
    return {
        "projections": projections,
        "enterprise_value": round(enterprise_value, 2),
        "terminal_value": round(terminal_value, 2),
        "terminal_value_pv": round(terminal_pv, 2)
    }

def calculate_sensitivity_matrix(
    base_revenue: float,
    revenue_growth_rate: float,
    ebitda_margin: float,
    tax_rate: float,
    d_and_a_pct: float,
    capex_pct: float,
    nwc_pct: float,
    base_wacc: float,
    base_terminal_growth: float,
    years: int,
    debt: float | None,
    cash: float | None,
    post_issue_shares: int | None
) -> dict:
    wacc_steps = [base_wacc - 0.02, base_wacc - 0.01, base_wacc, base_wacc + 0.01, base_wacc + 0.02]
    tg_steps = [base_terminal_growth - 0.01, base_terminal_growth - 0.005, base_terminal_growth, base_terminal_growth + 0.005, base_terminal_growth + 0.01]
    
    matrix = {
        "wacc_values": [round(w * 100, 1) for w in wacc_steps],
        "terminal_growth_values": [round(t * 100, 1) for t in tg_steps],
        "grid": []
    }
    
    for wacc in wacc_steps:
        row = []
        for tg in tg_steps:
            if wacc <= tg:
                row.append(None)
                continue
                
            res = run_dcf(
                base_revenue=base_revenue,
                revenue_growth_rate=revenue_growth_rate,
                ebitda_margin=ebitda_margin,
                tax_rate=tax_rate,
                d_and_a_pct=d_and_a_pct,
                capex_pct=capex_pct,
                nwc_pct=nwc_pct,
                wacc=wacc,
                terminal_growth_rate=tg,
                years=years
            )
            ev = res["enterprise_value"]
            if debt is not None and cash is not None and post_issue_shares:
                eq = ev + cash - debt
                row.append(round((eq * 10000000.0) / post_issue_shares, 2))
            else:
                # Fall back to EV if intrinsic value/share can't be computed
                row.append(round(ev, 2))
        matrix["grid"].append(row)
        
    return matrix
