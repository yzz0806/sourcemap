"""Segment-level marketing org-chart benchmark: one reference type per segment, a panel of companies
per segment, sources scored per segment (docs/domain.md §2 "segment", §6 R1).

  kr_listed — DART annual report (tier 1): every executive with responsibilities
  us_listed — SEC 10-K "executive officers" (tier 1): top officers only
  eu_listed — the company's own governance page (tier 2): no single EU regulator
References are built by pipeline/demo_refs.py into data/seg/refs.json.
"""

SEGMENTS = {
    # A segment = country × company size: source quality changes with both. Size is given by index
    # membership (a checkable fact), not by a market cap or headcount that would go stale.
    "kr_listed": {"name": "Korean large-cap", "country": "South Korea", "size": "KOSPI 200 members",
                  "reference": "DART annual report (official filing)"},
    "us_listed": {"name": "US mega-cap", "country": "United States", "size": "the largest S&P 500 companies by market value",
                  "reference": "SEC 10-K executive officers (official filing)"},
    "eu_listed": {"name": "European large-cap", "country": "Europe", "size": "Euro Stoxx 50 members",
                  "reference": "company's own governance page"},
    # Mid-size companies, asked about PRODUCT leadership (scripts/demo_add_companies.py).
    "us_mid": {"name": "US mid-cap", "country": "United States", "size": "US-listed, outside the S&P 500",
               "reference": "SEC proxy statement, executive officers (official filing)"},
    "eu_mid": {"name": "European mid-size", "country": "Europe", "size": "private, a few hundred employees",
               "reference": "company's own leadership page"},
}

COMPANIES = {
    "samsung-electronics": {"name": "Samsung Electronics", "name_local": "삼성전자", "segment": "kr_listed",
                            "own_domains": ["samsung.com", "samsungsemiconductor.com"], "url_token": "samsung"},
    "sk-hynix": {"name": "SK hynix", "name_local": "SK하이닉스", "segment": "kr_listed",
                 "own_domains": ["skhynix.com"], "url_token": "hynix"},
    "naver": {"name": "NAVER", "name_local": "네이버", "segment": "kr_listed",
              "own_domains": ["navercorp.com", "naver.com"], "url_token": "naver"},
    "nvidia": {"name": "Nvidia", "name_local": "Nvidia", "segment": "us_listed", "own_domains": ["nvidia.com"],
               "url_token": "nvidia"},
    "apple": {"name": "Apple", "name_local": "Apple", "segment": "us_listed", "own_domains": ["apple.com"],
              "url_token": "apple"},
    "microsoft": {"name": "Microsoft", "name_local": "Microsoft", "segment": "us_listed",
                  "own_domains": ["microsoft.com"], "url_token": "microsoft"},
    "airbus": {"name": "Airbus", "name_local": "Airbus", "segment": "eu_listed", "own_domains": ["airbus.com"],
               "url_token": "airbus"},
    "sap": {"name": "SAP", "name_local": "SAP", "segment": "eu_listed", "own_domains": ["sap.com"], "url_token": "sap"},
    "siemens": {"name": "Siemens", "name_local": "Siemens", "segment": "eu_listed", "own_domains": ["siemens.com"],
                "url_token": "siemens"},
    "sprinklr": {"name": "Sprinklr", "name_local": "Sprinklr", "segment": "us_mid", "own_domains": ["sprinklr.com"],
                 "url_token": "sprinklr", "department": "product"},
    "typeform": {"name": "Typeform", "name_local": "Typeform", "segment": "eu_mid", "own_domains": ["typeform.com"],
                 "url_token": "typeform", "department": "product"},
}

PLAN_PROMPT = """You plan where to search for sources that publish the MARKETING department org chart of
companies in one segment (who leads marketing, brand, communications-with-marketing; their titles;
reporting lines). Plan categories of publishers that apply to every company in the segment
(official filings in that country, the companies' own pages, crowd-edited org-chart sites, news on
executive appointments, executive/business databases, encyclopedias…). For each category write 2
query TEMPLATES using the placeholders {company} (English name) and {company_local} (local-language
name, same as English when there is none). Use the language the publishers use. Do not name specific
websites. Skip paid or login-only sources and say why.
Answer one JSON object only:
{"categories": [{"name": "...", "lineage": "...", "queries": ["... {company} ...", "..."]}],
 "skipped": [{"name": "...", "why": "..."}]}"""

PLAN_PROMPT_PRODUCT = PLAN_PROMPT.replace(
    "MARKETING department org chart of\ncompanies in one segment (who leads marketing, brand, communications-with-marketing; their titles;\nreporting lines)",
    "PRODUCT department org chart of\ncompanies in one segment (who leads product management, product, design-with-product; their titles;\nreporting lines)")
assert PLAN_PROMPT_PRODUCT != PLAN_PROMPT

MARKETING_WORDS = ("marketing", "마케팅", "brand", "cmo", "chief marketing")


def is_marketing(title: str) -> bool:
    t = (title or "").casefold()
    return any(w in t for w in MARKETING_WORDS)
