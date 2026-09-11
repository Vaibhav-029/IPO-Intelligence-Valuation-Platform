"""Diagnose Data Flow across Swiggy, Waaree Energies, Pranav Constructions, Rentomojo."""
import httpx
import json

TARGETS = [
    ("Swiggy", 3),
    ("Waaree Energies", 4),
    ("Pranav Constructions", 40),
    ("Rentomojo", 35),
]

ENDPOINTS = [
    ("IPO Metadata", "/api/v1/ipos/{id}"),
    ("Financials", "/api/v1/ipos/{id}/financials"),
    ("Valuation", "/api/v1/ipos/{id}/valuation"),
    ("Peers", "/api/v1/ipos/{id}/peers"),
    ("Risks", "/api/v1/ipos/{id}/risks"),
    ("Score", "/api/v1/ipos/{id}/score"),
]

DCF_PAYLOAD = {
    "revenue_growth_rate": 0.15,
    "ebitda_margin": 0.15,
    "tax_rate": 0.25,
    "d_and_a_pct_of_revenue": 0.05,
    "capex_pct_of_revenue": 0.06,
    "change_in_nwc_pct_of_revenue": 0.10,
    "discount_rate": 0.12,
    "terminal_growth_rate": 0.05,
    "years": 5,
}

for name, ipo_id in TARGETS:
    print(f"\n{'='*70}\nTarget: {name} (IPO ID: {ipo_id})\n{'='*70}")
    
    # 1. Metadata
    r = httpx.get(f"http://127.0.0.1:8000/api/v1/ipos/{ipo_id}")
    print(f"\n[Metadata] HTTP {r.status_code}")
    if r.status_code == 200:
        meta = r.json()
        print("  name:", meta.get("name"))
        print("  status:", meta.get("status"))
        print("  listing_segment:", meta.get("listing_segment"))
        print("  sector:", meta.get("sector"))
        print("  price_band:", meta.get("price_band"))
        print("  issue_size_crore:", meta.get("issue_size_crore"))
        print("  lot_size:", meta.get("lot_size"))
        print("  min_investment:", meta.get("min_investment"))
        print("  fresh_issue_crore:", meta.get("fresh_issue_crore"))
        print("  ofs_crore:", meta.get("ofs_crore"))
        print("  open_date:", meta.get("open_date"))
        print("  close_date:", meta.get("close_date"))
        print("  listing_date:", meta.get("listing_date"))
    else:
        print("  Failed:", r.text)

    # 2. Financials
    r = httpx.get(f"http://127.0.0.1:8000/api/v1/ipos/{ipo_id}/financials")
    print(f"\n[Financials] HTTP {r.status_code}")
    if r.status_code == 200:
        fin = r.json()
        items = fin.get("items", [])
        print(f"  Periods count: {len(items)}, 2y CAGR: {fin.get('revenue_cagr_2y')}")
        if items:
            latest = items[-1]
            print(f"  Latest period ({latest.get('fiscal_year')}):")
            print("    Revenue:", latest.get("revenue"))
            print("    EBITDA:", latest.get("ebitda"), f"(margin: {latest.get('ebitda_margin')}%)")
            print("    EBIT:", latest.get("ebit"), f"(margin: {latest.get('ebit_margin')}%)")
            print("    PAT:", latest.get("pat"), f"(margin: {latest.get('pat_margin')}%)")
            print("    ROE:", latest.get("roe"))
            print("    ROCE:", latest.get("roce"))
            print("    Net Debt:", latest.get("net_debt"))
            print("    YoY Growth:", latest.get("yoy_revenue_growth"))

    # 3. Valuation
    r = httpx.get(f"http://127.0.0.1:8000/api/v1/ipos/{ipo_id}/valuation")
    print(f"\n[Valuation] HTTP {r.status_code}")
    if r.status_code == 200:
        val = r.json()
        cm = val.get("CURRENT_MARKET")
        ai = val.get("IPO_AT_ISSUE")
        if cm:
            print("  CURRENT_MARKET:")
            print("    Market Cap:", cm.get("market_cap"), "EV:", cm.get("enterprise_value"))
            print("    P/E:", cm.get("pe"), "P/S:", cm.get("ps"), "EV/EBITDA:", cm.get("ev_ebitda"), "EV/Sales:", cm.get("ev_sales"))
        else:
            print("  CURRENT_MARKET: None")
        if ai:
            upper = ai.get("upper_band", {})
            print("  IPO_AT_ISSUE (Upper Band):")
            print("    Implied Market Cap:", upper.get("implied_market_cap"), "EV:", upper.get("enterprise_value"))
            print("    P/E:", upper.get("pe"), "P/S:", upper.get("ps"), "EV/EBITDA:", upper.get("ev_ebitda"), "EV/Sales:", upper.get("ev_sales"))

    # 4. Peers
    r = httpx.get(f"http://127.0.0.1:8000/api/v1/ipos/{ipo_id}/peers")
    print(f"\n[Peers] HTTP {r.status_code}")
    if r.status_code == 200:
        peers_json = r.json()
        plist = peers_json.get("peers", [])
        print(f"  Peers count: {len(plist)}")
        pstats = peers_json.get("peer_statistics", {})
        print("  Peer statistics:", pstats)
        pcomp = peers_json.get("comparison", {})
        print("  Comparison:", pcomp)

    # 5. Risks
    r = httpx.get(f"http://127.0.0.1:8000/api/v1/ipos/{ipo_id}/risks")
    print(f"\n[Risks] HTTP {r.status_code}")
    if r.status_code == 200:
        rlist = r.json()
        print(f"  Risks count: {len(rlist)}")
        for rk in rlist[:2]:
            print(f"    - [{rk.get('severity')}] {rk.get('category')}: {rk.get('summary')[:60]}... (p. {rk.get('source_page')})")

    # 6. Score
    r = httpx.get(f"http://127.0.0.1:8000/api/v1/ipos/{ipo_id}/score")
    print(f"\n[Score] HTTP {r.status_code}")
    if r.status_code == 200:
        sdata = r.json()
        print(f"  Overall Score: {sdata.get('overall_score')}")
        print("  Dimensions:", sdata.get("dimensions"))
        print("  Coverage:", sdata.get("coverage"))
    else:
        print("  Score response:", r.text)

    # 7. DCF
    r = httpx.post(f"http://127.0.0.1:8000/api/v1/ipos/{ipo_id}/dcf", json=DCF_PAYLOAD)
    print(f"\n[DCF] HTTP {r.status_code}")
    if r.status_code == 200:
        dcf_data = r.json()
        val = dcf_data.get("valuation", {})
        print("  Enterprise Value:", val.get("enterprise_value"))
        print("  Equity Value:", val.get("equity_value"))
        print("  Intrinsic Value / Share:", val.get("intrinsic_value_per_share"))
        print("  Projections count:", len(dcf_data.get("projections", [])))
        print("  Sensitivity matrix WACCs:", list(dcf_data.get("sensitivity", {}).get("matrix", {}).keys()))
    else:
        print("  DCF error:", r.text)
