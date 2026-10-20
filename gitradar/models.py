"""V4 的 JSON 契约；字段采用 snake_case，旧候选字段保持原义。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, TypedDict, Union

SCHEMA_VERSION = '4.0'
RULES_VERSION = 'v3.3'
RECOMMENDATION_VERSION = 'v4.0'
History = dict[str, dict[str, int]]


class RepositoryRef(TypedDict, total=False):
    full_name: str
    node_id: str
    history_key: str
    created_at: str


class Observation(RepositoryRef, total=False):
    observed_at: str
    stargazers_count: int
    status: str
    error: str
    http_status: int
    archived: bool
    fork: bool
    html_url: str
    description: str
    pushed_at: Optional[str]
    language: Optional[str]
    topics: list[str]


@dataclass(frozen=True)
class Budget:
    search_requests: int = 20
    rest_requests: int = 100
    content_requests: int = 60
    path_requests: int = 20
    identity_requests: int = 20
    graphql_points: int = 600
    graphql_batches: int = 100
    minimum_remaining: int = 200
    max_retries: int = 2


@dataclass
class Usage:
    search_requests: int = 0
    rest_requests: int = 0
    content_requests: int = 0
    path_requests: int = 0
    identity_requests: int = 0
    graphql_points: int = 0
    graphql_batches: int = 0
    graphql_unmeasured_requests: int = 0
    retries: int = 0
    not_modified: int = 0
    rest_remaining: Optional[int] = None
    search_remaining: Optional[int] = None
    graphql_remaining: Optional[int] = None
    reset_at: Optional[int] = None
    retry_after: Optional[int] = None
    rate_limited: bool = False


class ObservationBatch(TypedDict):
    observations: list[Observation]
    observed_at: str
    errors: list[str]
    usage: dict[str, object]


class PathCheck(TypedDict, total=False):
    status: Union[str, int]
    checked_at: str
    last_attempt_at: str


class EvidenceRef(TypedDict, total=False):
    id: str
    url: str
    section: str
    content_hash: str
    source_version: str
    asset_id: str
    license_spdx_id: str
    checked_at: str
    status: Union[str, int]
    published_at: str
    source_hash: str
    previous_source_hash: str
    context_changed: bool
    path_checks: dict[str, PathCheck]
    path_required_urls: list[str]
    path_status: Union[str, int]
    path_checked_at: str
    source_kind: str
    text: str


class FactClaim(TypedDict, total=False):
    value: object
    complete: bool
    ref_ids: list[str]


class EvidenceBundle(TypedDict, total=False):
    full_name: str
    node_id: str
    refs: list[EvidenceRef]
    facts: dict[str, FactClaim]
    official_urls: list[str]
    critical_unknowns: list[str]
    status: str
    errors: list[str]
    cache: dict[str, object]


class ProjectFacts(TypedDict, total=False):
    full_name: str
    node_id: str
    evidence_refs: list[EvidenceRef]
    official_urls: list[str]
    claims: dict[str, list[str]]
    critical_unknowns: list[str]
    purpose: str
    audience: str
    platforms: list[str]
    form: str
    prerequisites: list[str]
    license: str
    cost: str
    usage_paths: list[dict[str, object]]
    scenes: list[str]
    primary_scene: str
    generation_method: str


class Eligibility(TypedDict, total=False):
    eligible: bool
    reasons: list[str]


class ContentRecord(ProjectFacts, total=False):
    status: str
    recommendation_reason: str
    review_kind: str
    effective_status: str
    invalidation_reasons: list[str]
    evidence_hashes: dict[str, str]
    evidence_context_hashes: dict[str, str]
    eligibility: Eligibility
    identity_conflict: bool
    family: str
    ordinary_user: bool
    checked_at: str


class ProjectRecord(Observation, total=False):
    history_aliases: list[str]
    delta_1d: Optional[int]
    delta_7d: Optional[int]
    discovery_score: float
    category_zh: str
    summary_zh: Optional[str]
    difficulty_zh: str
    platforms_zh: list[str]
    readme_checked_at: Optional[str]
    first_seen_date: str
    last_observed_date: str
    observation_status: str
    observation_error: str
    last_observed_at: str
    content: ContentRecord
    schema_version: str
    first_recommended_at: str
    discovery_source: str
    family: str


class RecommendationFeed(TypedDict, total=False):
    schema_version: str
    recommendation_version: str
    batch_id: str
    generated_at: str
    recommendations: list[dict[str, object]]
    items: list[dict[str, object]]
    first_recommended_at: dict[str, str]
    first_qualified_at: dict[str, str]
    eligibility: dict[str, Eligibility]
    discovery_counts: dict[str, int]
    eligible_count: int
    selected_count: int
    shortfall_reasons: list[str]
    rotation: list[dict[str, object]]
    reasons: list[str]
    stats: dict[str, object]


class Snapshot(TypedDict, total=False):
    projects: list[ProjectRecord]
    history: History
    saved_aliases: dict[str, str]
    schema_version: str
    rules_version: str
    recommendation_version: str
    batch_id: str
    generated_at: str
    source_commit: str
    recommendations: RecommendationFeed
    evidence: dict[str, EvidenceBundle]
    curation: dict[str, ContentRecord]


class BuildManifest(TypedDict, total=False):
    schema_version: str
    batch_id: str
    generated_at: str
    source_commit: str
    inputs: dict[str, str]
    artifacts: dict[str, str]


class ValidationReport(TypedDict, total=False):
    allowed: bool
    errors: list[str]
    warnings: list[str]
    checks: dict[str, bool]
