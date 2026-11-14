"""The two hand-written data type specs (docs/domain.md §3, ADR 0001).

Segments, panels and sources are seed content and arrive in stage 2.
"""

from sourcemap.domain.model import ClaimTypeSpec, DataTypeSpec
from sourcemap.domain.vocab import CompareMode, ValueKind

# Expiry days: ADR 0012.
ORG_CHART = DataTypeSpec(
    slug="org_chart",
    name="Org chart",
    spec_version=1,
    claim_types=(
        ClaimTypeSpec("employment", ValueKind.BOOL, 60, CompareMode.EXACT, field=None),
        ClaimTypeSpec("title", ValueKind.TEXT, 30, CompareMode.JUDGE, field="title"),
        ClaimTypeSpec("reports_to", ValueKind.ENTITY, 30, CompareMode.EXACT, field="manager_ref"),
    ),
)

ACADEMIC_IDENTITY = DataTypeSpec(
    slug="academic_identity",
    name="Academic identity",
    spec_version=1,
    claim_types=(
        ClaimTypeSpec("exists", ValueKind.BOOL, 180, CompareMode.EXACT, field=None),
        ClaimTypeSpec("role", ValueKind.TEXT, 90, CompareMode.JUDGE, field="role"),
        ClaimTypeSpec("affiliation", ValueKind.TEXT, 60, CompareMode.NORMALISED, field="affiliation"),
        ClaimTypeSpec("email", ValueKind.EMAIL, 180, CompareMode.NORMALISED, field="email"),
        ClaimTypeSpec("profile_link", ValueKind.URL, 180, CompareMode.NORMALISED, field="profile_link"),
    ),
)

ALL_SPECS = (ORG_CHART, ACADEMIC_IDENTITY)
