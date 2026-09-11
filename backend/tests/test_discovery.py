import pytest
from app.services.discovery import _search_sebi
from unittest.mock import patch, MagicMock

@patch("app.services.discovery.requests.Session")
def test_sebi_discovery_parsing(mock_session_cls):
    mock_session = MagicMock()
    mock_session_cls.return_value.__enter__.return_value = mock_session
    
    # Mock for smid=12 (Prospectus) -> No results
    mock_res_12 = MagicMock()
    mock_res_12.status_code = 200
    mock_res_12.text = "<html><body></body></html>"
    
    # Mock for smid=11 (RHP) -> Finds a direct PDF and an HTML detail page
    mock_res_11 = MagicMock()
    mock_res_11.status_code = 200
    mock_res_11.text = """
    <html><body>
        <a href="https://www.sebi.gov.in/sebi_data/commondocs/RENTOMOJO_AP_p.pdf">Rentomojo Limited - Abridged Prospectus</a>
        <a href="https://www.sebi.gov.in/filings/public-issues/rentomojo-rhp.html">Rentomojo Limited - RHP</a>
    </body></html>
    """
    
    # Mock detail page for RHP
    mock_detail_rhp = MagicMock()
    mock_detail_rhp.status_code = 200
    mock_detail_rhp.text = """
    <html><body>
        <iframe src="../../../web/?file=https://www.sebi.gov.in/sebi_data/attachdocs/rhp.pdf"></iframe>
    </body></html>
    """
    
    # Mock for smid=10 (DRHP) -> Finds a DRHP
    mock_res_10 = MagicMock()
    mock_res_10.status_code = 200
    mock_res_10.text = """
    <html><body>
        <a href="https://www.sebi.gov.in/sebi_data/commondocs/drhp.pdf">Rentomojo Limited - DRHP</a>
    </body></html>
    """
    
    # Setup mock behavior based on URL
    def side_effect_post(url, *args, **kwargs):
        smid = kwargs.get('data', {}).get('smid')
        if smid == "12":
            return mock_res_12
        elif smid == "11":
            return mock_res_11
        elif smid == "10":
            return mock_res_10
        return MagicMock(status_code=404)
        
    def side_effect_get(url, *args, **kwargs):
        if "rentomojo-rhp.html" in url:
            return mock_detail_rhp
        return MagicMock(status_code=404)
        
    mock_session.post.side_effect = side_effect_post
    mock_session.get.side_effect = side_effect_get
    
    candidates = _search_sebi("Rentomojo")
    
    # The order must be exactly as discovered:
    # 11: Abridged PDF, Detail iframe PDF
    # 10: DRHP PDF
    assert len(candidates) == 3
    assert candidates[0] == "https://www.sebi.gov.in/sebi_data/commondocs/RENTOMOJO_AP_p.pdf"
    assert candidates[1] == "https://www.sebi.gov.in/sebi_data/attachdocs/rhp.pdf"
    assert candidates[2] == "https://www.sebi.gov.in/sebi_data/commondocs/drhp.pdf"
    
    # Also verify that the deduplication logic preserves this order
    from app.services.discovery import find_candidate_pdf_urls
    
    with patch("app.services.discovery.requests.get") as mock_get:
        # Mock IPO central to return nothing
        mock_get.return_value = MagicMock(status_code=404)
        
        urls = find_candidate_pdf_urls("Rentomojo")
        assert len(urls) == 3
        # Ensure order is preserved!
        assert urls[0] == "https://www.sebi.gov.in/sebi_data/commondocs/RENTOMOJO_AP_p.pdf"
        assert urls[1] == "https://www.sebi.gov.in/sebi_data/attachdocs/rhp.pdf"
        assert urls[2] == "https://www.sebi.gov.in/sebi_data/commondocs/drhp.pdf"
