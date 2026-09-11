"""Filing discovery and validation service.

Discovers authoritative PDF URLs for DRHPs, RHPs, and Prospectuses,
and validates them strictly by downloading and inspecting the content
to ensure an issuer match and correct document type.
"""
from __future__ import annotations

import io
import logging
import re
from typing import Optional

import fitz  # PyMuPDF
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Allowed domains for authoritative filings
AUTHORITATIVE_DOMAINS = [
    "sebi.gov.in",
    "bseindia.com",
    "nseindia.com",
]

class DiscoveryError(Exception):
    pass


class FilingCandidate:
    def __init__(self, url: str, source_domain: str):
        self.url = url
        self.source_domain = source_domain
        self.pdf_bytes: Optional[bytes] = None
        self.doc_type: Optional[str] = None  # "DRHP", "RHP", "Prospectus"


def find_candidate_pdf_urls(company_name: str) -> list[str]:
    """Discover potential filing PDF URLs for a given company.
    
    This uses a basic heuristic search across known IPO repositories.
    In a fully productionized system, this would integrate with BSE/NSE
    APIs or a search engine.
    """
    candidates = []
    
    # 1. Search IPO Central's dedicated page (heuristic)
    slug = re.sub(r'[^a-z0-9]+', '-', company_name.lower().strip()).strip('-')
    ipo_central_url = f"https://ipocentral.in/{slug}-ipo/"
    
    try:
        res = requests.get(ipo_central_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"].lower()
                text = a.text.lower()
                if "drhp" in text or "rhp" in text or "prospectus" in text or href.endswith(".pdf"):
                    # Only accept links that look like PDFs or point to authoritative domains
                    if href.endswith(".pdf") or any(d in href for d in AUTHORITATIVE_DOMAINS):
                        candidates.append(a["href"])
    except requests.RequestException as e:
        logger.warning("Failed to discover on IPO Central for %s: %s", company_name, e)

    # Clean and dedup IPO Central candidates while preserving order
    candidates = list(dict.fromkeys(c.strip() for c in candidates if c.startswith("http")))
    
    # 2. Fallback to SEBI Public Issues if IPO Central yields no PDFs
    if not candidates:
        logger.info("No candidates from IPO Central for %s. Falling back to SEBI.", company_name)
        sebi_candidates = _search_sebi(company_name)
        candidates.extend(sebi_candidates)

    # Clean and dedup again while preserving priority order (Prospectus > RHP > DRHP)
    candidates = list(dict.fromkeys(c.strip() for c in candidates if c.startswith("http")))
    return candidates

def _search_sebi(company_name: str) -> list[str]:
    """Search SEBI Public Issues for the given company name."""
    candidates = []
    
    # smid=12 (Prospectus), smid=11 (RHP), smid=10 (DRHP)
    # The order implies preference, but workers.py takes the first valid one.
    search_categories = [12, 11, 10]
    
    # Normalize company name for exact matching
    def normalize(name):
        return re.sub(r'[^a-z0-9]', '', name.lower().replace('limited', '').replace('ltd', ''))
    
    target_norm = normalize(company_name)
    
    with requests.Session() as session:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
            "Accept": "text/html, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://www.sebi.gov.in",
            "Referer": "https://www.sebi.gov.in/filings/public-issues.html"
        }
        
        for smid in search_categories:
            url = "https://www.sebi.gov.in/sebiweb/ajax/home/getnewslistinfo.jsp"
            data = {
                "nextValue": "1",
                "next": "1",
                "search": company_name,
                "deptId": "-1",
                "sid": "3",
                "ssid": "15",
                "smid": str(smid)
            }
            try:
                res = session.post(url, data=data, headers=headers, timeout=15)
                if res.status_code == 200:
                    soup = BeautifulSoup(res.text, "html.parser")
                    for a in soup.find_all("a", href=True):
                        link_text = a.text.strip()
                        href = a["href"].strip()
                        
                        # Hard Issuer Validation
                        if target_norm in normalize(link_text):
                            if href.endswith(".pdf"):
                                candidates.append(href)
                            elif href.endswith(".html"):
                                # Fetch the detail page to extract iframe PDF
                                detail_res = session.get(href, headers=headers, timeout=15)
                                if detail_res.status_code == 200:
                                    detail_soup = BeautifulSoup(detail_res.text, "html.parser")
                                    iframe = detail_soup.find("iframe")
                                    if iframe and "file=" in iframe.get("src", ""):
                                        pdf_url = iframe["src"].split("file=")[-1].strip()
                                        candidates.append(pdf_url)
                                        
                                    # Also capture any direct PDF links in the detail page
                                    for sub_a in detail_soup.find_all("a", href=True):
                                        if sub_a["href"].endswith(".pdf"):
                                            candidates.append(sub_a["href"].strip())
            except requests.RequestException as e:
                logger.warning("Failed to search SEBI for %s (smid=%d): %s", company_name, smid, e)
                
    return candidates


def validate_filing_url(url: str, company_name: str) -> Optional[FilingCandidate]:
    """Strictly validate a PDF URL by downloading it and inspecting content.
    
    Rules:
    1. HTTP 200 and Content-Type must be application/pdf.
    2. Document must be parseable as a PDF.
    3. The first 10 pages must contain the company name (fuzzy match).
    4. The first 10 pages must positively identify as DRHP, RHP, or Prospectus.
    """
    try:
        # Stream first to check headers
        res = requests.get(url, stream=True, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        if res.status_code != 200:
            logger.warning("Rejecting %s: HTTP %d", url, res.status_code)
            return None
            
        content_type = res.headers.get("Content-Type", "").lower()
        if "application/pdf" not in content_type:
            logger.warning("Rejecting %s: Content-Type %s is not PDF", url, content_type)
            return None

        # Download PDF (limit to 100MB to prevent memory explosion)
        content_length = int(res.headers.get("Content-Length", 0))
        if content_length > 100 * 1024 * 1024:
            logger.warning("Rejecting %s: File too large (%d bytes)", url, content_length)
            return None

        pdf_bytes = res.content
        
        # Parse PDF using PyMuPDF
        pdf = fitz.open(stream=pdf_bytes, filetype="pdf")
        if pdf.page_count < 50:
            logger.warning("Rejecting %s: PDF too short (%d pages). Not a valid DRHP/RHP.", url, pdf.page_count)
            return None
            
        # Extract text from first 10 pages for validation
        validation_text = ""
        pages_to_check = min(10, pdf.page_count)
        for i in range(pages_to_check):
            page = pdf[i]
            validation_text += page.get_text("text").lower() + " "
            
        pdf.close()
        
        # 1. Hard validation: Issuer Match
        # Normalize company name (remove "Limited", "Ltd", etc.)
        normalized_company = re.sub(r'\b(limited|ltd|inc|corporation|corp)\b', '', company_name.lower()).strip()
        normalized_company = re.sub(r'[^a-z0-9 ]+', '', normalized_company)
        
        # We need a robust match. Let's require all major words of the normalized company name to appear.
        words = [w for w in normalized_company.split() if len(w) > 2]
        if not words:
            words = [company_name.lower().strip()]
            
        matches = all(w in validation_text for w in words)
        if not matches:
            logger.warning("Rejecting %s: Issuer match failed for '%s'", url, company_name)
            return None
            
        # 2. Hard validation: Document Type Classification
        doc_type = None
        # Must check in specific order to avoid false positives 
        # (e.g. an RHP might mention "draft red herring prospectus" in its history)
        if "red herring prospectus" in validation_text and "draft" not in validation_text[:1000]:
             doc_type = "RHP"
        elif "draft red herring prospectus" in validation_text:
             doc_type = "DRHP"
        elif "prospectus" in validation_text and "red herring" not in validation_text:
             doc_type = "Prospectus"
             
        if not doc_type:
            # Fallback: check raw occurrences
            drhp_count = validation_text.count("draft red herring")
            rhp_count = validation_text.count("red herring") - drhp_count
            
            if rhp_count > drhp_count and rhp_count > 0:
                doc_type = "RHP"
            elif drhp_count > 0:
                doc_type = "DRHP"
            elif "prospectus" in validation_text:
                doc_type = "Prospectus"
            else:
                logger.warning("Rejecting %s: Could not classify document type (DRHP/RHP/Prospectus)", url)
                return None
                
        # Validated!
        domain = url.split("/")[2] if "//" in url else "unknown"
        candidate = FilingCandidate(url, domain)
        candidate.pdf_bytes = pdf_bytes
        candidate.doc_type = doc_type
        
        logger.info("Validated filing %s as %s for %s", url, doc_type, company_name)
        return candidate
        
    except Exception as e:
        logger.warning("Rejecting %s due to processing error: %s", url, e)
        return None
