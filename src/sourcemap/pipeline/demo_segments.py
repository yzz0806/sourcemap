"""Segment-level marketing org-chart benchmark: one reference type per segment, a panel of companies
per segment, sources scored per segment (docs/domain.md §2 "segment", §6 R1).

  kr_listed — DART annual report (tier 1): every executive with responsibilities
  us_listed — SEC 10-K "executive officers" (tier 1): top officers only
  eu_listed — the company's own governance page (tier 2): no single EU regulator
References are built by pipeline/demo_refs.py into data/seg/refs.json.
"""

SEGMENTS = {
    "kr_listed": {"name": "Korean listed", "country": "South Korea", "reference": "DART annual report (official filing)"},
    "us_listed": {"name": "US listed", "country": "United States", "reference": "SEC 10-K executive officers (official filing)"},
    "eu_listed": {"name": "European listed", "country": "Europe", "reference": "company's own governance page"},
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

MARKETING_WORDS = ("marketing", "마케팅", "brand", "cmo", "chief marketing")


def is_marketing(title: str) -> bool:
    t = (title or "").casefold()
    return any(w in t for w in MARKETING_WORDS)
