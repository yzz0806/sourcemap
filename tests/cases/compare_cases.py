"""Value comparison case table — the specification of measure.compare (docs/domain.md §6, ADR 0004).

Each row: plain-language name, data type, claim type, two values, expected comparison.
JUDGE-mode claim types (title, role) never say DIFFERENT by rule: only the judge can.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CompareCase:
    name: str
    data_type: str
    claim_type: str
    a: object
    b: object
    expected: str  # "same" / "different" / "ask_judge"


COMPARE_CASES = [
    CompareCase("identical titles are the same", "org_chart", "title", "VP Sales", "VP Sales", "same"),
    CompareCase("titles differing only in case and spaces are the same",
                "org_chart", "title", "  vp   SALES ", "VP Sales", "same"),
    CompareCase("trailing punctuation does not matter", "org_chart", "title", "CEO.", "CEO", "same"),
    CompareCase("VP Sales vs Vice President of Sales goes to the judge",
                "org_chart", "title", "VP Sales", "Vice President of Sales", "ask_judge"),
    CompareCase("CEO vs CFO goes to the judge, never different by rule",
                "org_chart", "title", "CEO", "CFO", "ask_judge"),
    CompareCase("Korean title vs English title goes to the judge",
                "org_chart", "title", "대표이사", "CEO", "ask_judge"),
    CompareCase("employment true vs true is the same", "org_chart", "employment", True, True, "same"),
    CompareCase("employment true vs false is different", "org_chart", "employment", True, False, "different"),
    CompareCase("same manager ref is the same", "org_chart", "reports_to", 12, 12, "same"),
    CompareCase("different manager is different", "org_chart", "reports_to", 12, 13, "different"),
    CompareCase("emails differing in case are the same",
                "academic_identity", "email", "Jane.Smith@Purdue.EDU ", "jane.smith@purdue.edu", "same"),
    CompareCase("different emails are different",
                "academic_identity", "email", "jsmith@purdue.edu", "jane@purdue.edu", "different"),
    CompareCase("profile links differing in scheme, www and slash are the same",
                "academic_identity", "profile_link",
                "https://www.orcid.org/0000-0002-1825-0097/", "http://orcid.org/0000-0002-1825-0097", "same"),
    CompareCase("profile links differing in query string are the same",
                "academic_identity", "profile_link",
                "https://orcid.org/0000-0002-1825-0097?lang=en", "orcid.org/0000-0002-1825-0097", "same"),
    CompareCase("different profile links are different",
                "academic_identity", "profile_link",
                "https://orcid.org/0000-0002-1825-0097", "https://orcid.org/0000-0001-5109-3700", "different"),
    CompareCase("affiliation differing in case is the same",
                "academic_identity", "affiliation", "Purdue University", "purdue university", "same"),
    CompareCase("different affiliations are different",
                "academic_identity", "affiliation", "Purdue University", "MIT", "different"),
    CompareCase("role is compared by the judge", "academic_identity", "role",
                "PhD student", "Doctoral candidate", "ask_judge"),
]
