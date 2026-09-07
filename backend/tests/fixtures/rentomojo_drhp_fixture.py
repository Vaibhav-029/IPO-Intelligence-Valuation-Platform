"""Rentomojo DRHP test fixture.

This fixture simulates the structure of a real DRHP financial-table text
that would appear in Source chunks after process_document() processes
a Rentomojo DRHP PDF.

NOTE: These are REPRESENTATIVE values based on typical DRHP structures.
The end-to-end test with the actual Rentomojo DRHP PDF remains pending
until the filing is uploaded to the platform.

This fixture is used ONLY for automated testing with mock LLM responses.
"""

# ── Simulated Source chunk texts ─────────────────────────────────────

FINANCIAL_STATEMENT_CHUNK = """RESTATED CONSOLIDATED STATEMENT OF PROFIT AND LOSS

(₹ in Crore except per share data)

Particulars                          FY2024          FY2023          FY2022
                                  (Year ended     (Year ended     (Year ended
                                   Mar 31, 2024)   Mar 31, 2023)   Mar 31, 2022)

Revenue from Operations              412.56          298.43          187.21
Other Income                           12.34            8.76            5.43
Total Income                          424.90          307.19          192.64

Expenses:
Cost of Materials                     123.45           89.53           56.17
Employee Benefits                      82.51           59.69           37.44
Depreciation and Amortization          45.23           32.67           20.49
Other Expenses                         98.76           71.43           44.82
Total Expenses                        349.95          253.32          158.92

EBITDA                                 120.18           86.54           54.21
EBIT                                    74.95           53.87           33.72

Profit Before Tax                       74.95           53.87           33.72
Tax Expense                             18.74           13.47            8.43
Profit After Tax (PAT)                  56.21           40.40           25.29

Earnings Per Share (₹)
  Basic EPS                             14.23           10.22            6.40
  Diluted EPS                           13.89            9.98            6.25
"""

BALANCE_SHEET_CHUNK = """RESTATED CONSOLIDATED BALANCE SHEET

(₹ in Crore)

Particulars                          As at           As at           As at
                                   Mar 31, 2024    Mar 31, 2023    Mar 31, 2022

EQUITY AND LIABILITIES:
Share Capital                          39.50           39.50           39.50
Reserves and Surplus                  285.67          229.46          189.06
Total Equity                          325.17          268.96          228.56

Non-Current Liabilities:
Long-term Borrowings                   85.43           65.32           45.21
Other Non-Current Liabilities          12.34            9.87            7.65
Total Non-Current Liabilities          97.77           75.19           52.86

Current Liabilities:
Short-term Borrowings                  45.67           34.56           23.45
Trade Payables                         34.56           25.43           16.78
Other Current Liabilities              23.45           17.89           12.34
Total Current Liabilities             103.68           77.88           52.57

TOTAL EQUITY AND LIABILITIES          526.62          422.03          333.99

ASSETS:
Non-Current Assets:
Property, Plant and Equipment         156.78          125.43           98.76
Intangible Assets                      34.56           27.89           21.34
Other Non-Current Assets               23.45           18.76           14.56
Total Non-Current Assets              214.79          172.08          134.66

Current Assets:
Cash and Cash Equivalents              67.89           54.32           42.56
Trade Receivables                      89.34           71.45           56.32
Inventories                            45.67           36.45           28.76
Other Current Assets                  108.93           87.73           71.69
Total Current Assets                  311.83          249.95          199.33

TOTAL ASSETS                          526.62          422.03          333.99

Total Borrowings (Total Debt)         131.10           99.88           68.66
"""

RISK_FACTORS_CHUNK = """RISK FACTORS

An investment in equity shares involves a high degree of risk. You should carefully
consider all the information in this Draft Red Herring Prospectus, including the risks
and uncertainties described below, before making an investment in our Equity Shares.

1. We derive a significant portion of our revenue from a limited number of cities.
   Any disruption in these markets could materially adversely affect our business,
   financial condition and results of operations. Our top 5 cities contribute
   approximately 78% of our total revenue.

2. We face intense competition from both organized and unorganized players in the
   furniture and appliance rental market. The entry of well-funded competitors
   could adversely affect our market share and pricing power.

3. Our business is subject to extensive government regulations including the
   Consumer Protection Act, GST regulations, and state-level rental regulations.
   Changes in applicable laws may adversely affect our operations and profitability.

4. We have a history of net losses in earlier periods and there can be no assurance
   that we will maintain profitability in the future. Our ability to sustain
   profitability depends on maintaining growth momentum while controlling costs.

5. Our technology platform is critical to our operations. Any significant disruption,
   including cybersecurity incidents, could materially impact our ability to serve
   customers and process transactions.

6. We depend on third-party logistics partners for delivery and installation of
   rental products. Any disruption in these relationships could affect our service
   quality and customer satisfaction.

7. Our inventory management requires significant working capital. Inability to
   manage inventory efficiently could result in increased costs and reduced margins.
"""

# Non-financial chunk (should NOT be identified as financial)
BOILERPLATE_CHUNK = """GENERAL INFORMATION

This Draft Red Herring Prospectus is dated September 1, 2026.

Our Company was originally incorporated as 'Rentomojo Private Limited' on
January 15, 2014, under the Companies Act, 2013. The registered office of
our Company is located at Bangalore, Karnataka.

Our Promoters are Mr. Geetansh Bamania and Mr. Ajay Nain.
"""

# ── Expected mock LLM responses ────────────────────────────────────

MOCK_FINANCIAL_LLM_RESPONSE = """{
  "periods": [
    {
      "fiscal_year": "FY2024",
      "period_end": "2024-03-31",
      "period_type": "Annual",
      "interim_period": null,
      "metrics": {
        "revenue": {"raw": "412.56", "unit": "crore", "value": 412.56, "confidence": "high"},
        "ebitda": {"raw": "120.18", "unit": "crore", "value": 120.18, "confidence": "high"},
        "ebit": {"raw": "74.95", "unit": "crore", "value": 74.95, "confidence": "high"},
        "pat": {"raw": "56.21", "unit": "crore", "value": 56.21, "confidence": "high"},
        "eps": {"raw": "14.23", "unit": "inr", "value": 14.23, "confidence": "high"},
        "total_debt": {"raw": "131.10", "unit": "crore", "value": 131.10, "confidence": "high"},
        "cash": {"raw": "67.89", "unit": "crore", "value": 67.89, "confidence": "high"},
        "equity": {"raw": "325.17", "unit": "crore", "value": 325.17, "confidence": "high"},
        "assets": {"raw": "526.62", "unit": "crore", "value": 526.62, "confidence": "high"}
      }
    },
    {
      "fiscal_year": "FY2023",
      "period_end": "2023-03-31",
      "period_type": "Annual",
      "interim_period": null,
      "metrics": {
        "revenue": {"raw": "298.43", "unit": "crore", "value": 298.43, "confidence": "high"},
        "ebitda": {"raw": "86.54", "unit": "crore", "value": 86.54, "confidence": "high"},
        "ebit": {"raw": "53.87", "unit": "crore", "value": 53.87, "confidence": "high"},
        "pat": {"raw": "40.40", "unit": "crore", "value": 40.40, "confidence": "high"},
        "eps": {"raw": "10.22", "unit": "inr", "value": 10.22, "confidence": "high"},
        "total_debt": {"raw": "99.88", "unit": "crore", "value": 99.88, "confidence": "high"},
        "cash": {"raw": "54.32", "unit": "crore", "value": 54.32, "confidence": "high"},
        "equity": {"raw": "268.96", "unit": "crore", "value": 268.96, "confidence": "high"},
        "assets": {"raw": "422.03", "unit": "crore", "value": 422.03, "confidence": "high"}
      }
    },
    {
      "fiscal_year": "FY2022",
      "period_end": "2022-03-31",
      "period_type": "Annual",
      "interim_period": null,
      "metrics": {
        "revenue": {"raw": "187.21", "unit": "crore", "value": 187.21, "confidence": "high"},
        "ebitda": {"raw": "54.21", "unit": "crore", "value": 54.21, "confidence": "high"},
        "ebit": {"raw": "33.72", "unit": "crore", "value": 33.72, "confidence": "high"},
        "pat": {"raw": "25.29", "unit": "crore", "value": 25.29, "confidence": "high"},
        "eps": {"raw": "6.40", "unit": "inr", "value": 6.40, "confidence": "high"},
        "total_debt": {"raw": "68.66", "unit": "crore", "value": 68.66, "confidence": "high"},
        "cash": {"raw": "42.56", "unit": "crore", "value": 42.56, "confidence": "high"},
        "equity": {"raw": "228.56", "unit": "crore", "value": 228.56, "confidence": "high"},
        "assets": {"raw": "333.99", "unit": "crore", "value": 333.99, "confidence": "high"}
      }
    }
  ],
  "extraction_notes": "Three annual periods extracted from restated consolidated financial statements."
}"""

MOCK_RISK_LLM_RESPONSE = """{
  "risks": [
    {
      "category": "Concentration",
      "summary": "The company derives approximately 78% of revenue from top 5 cities, creating significant geographic concentration risk.",
      "severity": "High",
      "severity_justification": "Filing states disruption could 'materially adversely affect' business with 78% revenue concentration.",
      "page": 45
    },
    {
      "category": "Competition",
      "summary": "The company faces intense competition from organized and unorganized players in the furniture and appliance rental market.",
      "severity": "Medium",
      "severity_justification": "Standard competitive risk with 'could adversely affect market share' language.",
      "page": 45
    },
    {
      "category": "Regulatory",
      "summary": "The business is subject to extensive government regulations including Consumer Protection Act, GST, and state-level rental regulations.",
      "severity": "Medium",
      "severity_justification": "Standard regulatory compliance risk, 'may adversely affect' language used.",
      "page": 46
    },
    {
      "category": "Financial",
      "summary": "The company has a history of net losses in earlier periods with no assurance of maintaining future profitability.",
      "severity": "High",
      "severity_justification": "Profitability sustainability is a material concern with 'no assurance' language.",
      "page": 46
    },
    {
      "category": "Technology",
      "summary": "The technology platform is critical to operations, and significant disruptions including cybersecurity incidents could materially impact service delivery.",
      "severity": "Medium",
      "severity_justification": "Technology dependency risk with 'materially impact' language but manageable with standard practices.",
      "page": 47
    },
    {
      "category": "Operational",
      "summary": "Dependence on third-party logistics partners for delivery and installation of rental products.",
      "severity": "Low",
      "severity_justification": "Standard operational dependency, multiple logistics partners typically available.",
      "page": 47
    },
    {
      "category": "Operational",
      "summary": "Inventory management requires significant working capital, and inefficiency could increase costs.",
      "severity": "Low",
      "severity_justification": "Standard working capital management risk without critical language.",
      "page": 48
    }
  ]
}"""

# ── Mock LLM response with partial / missing data ───────────────────
MOCK_PARTIAL_FINANCIAL_LLM_RESPONSE = """{
  "periods": [
    {
      "fiscal_year": "FY2024",
      "period_end": "2024-03-31",
      "period_type": "Annual",
      "interim_period": null,
      "metrics": {
        "revenue": {"raw": "412.56", "unit": "crore", "value": 412.56, "confidence": "high"},
        "pat": {"raw": "56.21", "unit": "crore", "value": 56.21, "confidence": "high"}
      }
    }
  ],
  "extraction_notes": "Only revenue and PAT could be identified from the available text."
}"""

# ── Mock LLM response with malformed data ───────────────────────────
MOCK_MALFORMED_LLM_RESPONSE = """This is not valid JSON at all.
The financial data shows revenue of approximately 412 crore."""

# ── Mock LLM response with ambiguous risk severity ──────────────────
MOCK_RISK_AMBIGUOUS_SEVERITY = """{
  "risks": [
    {
      "category": "Regulatory",
      "summary": "Some regulatory risk exists.",
      "severity": "ambiguous",
      "severity_justification": "Cannot determine severity from available text.",
      "page": 50
    },
    {
      "category": "Financial",
      "summary": "Material adverse effect on financial condition possible.",
      "severity": "High",
      "severity_justification": "Filing uses 'material adverse effect' language.",
      "page": 51
    },
    {
      "category": "Market",
      "summary": "Some market risk.",
      "severity": "unclear",
      "severity_justification": "Insufficient context.",
      "page": 52
    }
  ]
}"""

# ── Mock response with unit variations (lakhs, millions) ────────────
MOCK_UNIT_VARIATION_RESPONSE = """{
  "periods": [
    {
      "fiscal_year": "FY2024",
      "period_end": "2024-03-31",
      "period_type": "Annual",
      "interim_period": null,
      "metrics": {
        "revenue": {"raw": "41256", "unit": "lakhs", "value": 41256, "confidence": "high"},
        "ebitda": {"raw": "120.18", "unit": "million", "value": 120.18, "confidence": "medium"},
        "pat": {"raw": "562.1", "unit": "crore", "value": 562.1, "confidence": "high"}
      }
    }
  ],
  "extraction_notes": "Mixed units in source document."
}"""

# ── Empty extraction response ───────────────────────────────────────
MOCK_EMPTY_RESPONSE = """{
  "periods": [],
  "extraction_notes": "No financial data found in the provided text."
}"""
