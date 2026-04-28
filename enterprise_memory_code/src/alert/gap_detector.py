"""
Enterprise Memory — Knowledge Gap Detector

Identifies knowledge coverage gaps at the team level:
  - Domains with low coverage (few team members have relevant knowledge)
  - Single-point-of-failure knowledge (only one person掌握s it)
  - Uncovered domains (no team member has knowledge in an area)
  - Knowledge silos (team members with non-overlapping knowledge)

Direction D: Team Knowledge Health / Forgetting Alerts.

Strategy:
  1. Define core knowledge domains from chunk content analysis
  2. Evaluate per-member coverage for each domain
  3. Detect single-point-of-failure risk
  4. Build and update team_knowledge_map table
"""

import json
import logging
import re
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Default knowledge domains — extracted from common project areas
DEFAULT_DOMAINS = [
    {"name": "infrastructure", "keywords": ["deploy", "server", "docker", "kubernetes", "aws", "cloud", "ci", "cd", "pipeline", "infrastructure", "provisioning", "terraform", "ansible"]},
    {"name": "frontend", "keywords": ["react", "vue", "angular", "css", "html", "ui", "ux", "component", "page", "layout", "styling", "responsive", "design"]},
    {"name": "backend", "keywords": ["api", "endpoint", "database", "query", "server", "service", "middleware", "handler", "route", "controller", "model", "schema"]},
    {"name": "data", "keywords": ["data", "analytics", "etl", "pipeline", "warehouse", "sql", "bigquery", "spark", "kafka", "streaming", "batch", "report"]},
    {"name": "security", "keywords": ["auth", "authentication", "authorization", "security", "encrypt", "token", "oauth", "permission", "vulnerability", "audit"]},
    {"name": "testing", "keywords": ["test", "unit test", "integration test", "e2e", "mock", "fixture", "coverage", "jest", "pytest", "selenium", "qa"]},
    {"name": "devops", "keywords": ["ci", "cd", "pipeline", "github actions", "jenkins", "release", "versioning", "rollback", "monitoring", "logging", "alert"]},
    {"name": "architecture", "keywords": ["architecture", "design", "pattern", "system design", "microservice", "monolith", "event", "message queue", "cache"]},
    {"name": "documentation", "keywords": ["readme", "doc", "documentation", "wiki", "guide", "tutorial", "onboarding", "setup", "install"]},
    {"name": "product", "keywords": ["product", "feature", "requirement", "user story", "specification", "roadmap", "backlog", "sprint", "planning"]},
]


class GapDetector:
    """Detects knowledge coverage gaps at the team level."""

    def __init__(self, store: Any):
        """
        Args:
            store: SqliteStore instance with v2 schema tables.
        """
        self._store = store

    # ------------------------------------------------------------------
    # Main API
    # ------------------------------------------------------------------

    def detect_gaps(
        self,
        team_id: str,
        domain_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run full gap detection for a team.

        Args:
            team_id: Team identifier.
            domain_filter: Optional domain to focus on.

        Returns:
            Gap analysis summary.
        """
        # Step 1: Get all shared knowledge for this team
        team_chunks = self._get_team_chunks(team_id)
        if not team_chunks:
            logger.info(f"gap_detector: no shared chunks found for team {team_id}")
            return {"team_id": team_id, "domains": [], "gaps": []}

        # Step 2: Get team members
        team_members = self._get_team_members(team_id)
        if not team_members:
            logger.info(f"gap_detector: no team members found for {team_id}")
            return {"team_id": team_id, "domains": [], "gaps": []}

        # Step 3: Analyze domain coverage
        domains = self._analyze_domain_coverage(
            team_chunks, team_members, domain_filter,
        )

        # Step 4: Detect single-point-of-failures
        spof = self._detect_single_points(team_chunks, team_members)

        # Step 5: Build / update team knowledge map
        self._update_team_map(team_id, domains)

        # Step 6: Identify gaps
        gaps = self._identify_gaps(domains, team_members)

        summary = {
            "team_id": team_id,
            "total_members": len(team_members),
            "total_chunks": len(team_chunks),
            "domains": domains,
            "single_points_of_failure": spof,
            "gaps": gaps,
            "analyzed_at": int(time.time() * 1000),
        }

        logger.info(
            f"gap_detector: team {team_id} — "
            f"{len(domains)} domains, {len(spof)} SPOFs, {len(gaps)} gaps"
        )
        return summary

    def build_team_knowledge_map(self, team_id: str) -> None:
        """Build or refresh the team knowledge map.

        This is a convenience method that calls detect_gaps and stores
        the results in the team_knowledge_map table.
        """
        self.detect_gaps(team_id)

    def get_relevant_gaps(
        self,
        query: str,
        team_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Find knowledge gaps relevant to a search query.

        Args:
            query: The search query.
            team_id: Optional team filter.

        Returns:
            List of relevant gap entries.
        """
        if not team_id:
            return []

        query_lower = query.lower()
        query_keywords = set(re.findall(r'\b[a-zA-Z]{3,}\b', query_lower))

        if not query_keywords:
            return []

        # Find matching domains
        matching_domains = []
        for domain_info in DEFAULT_DOMAINS:
            domain_name = domain_info["name"]
            domain_keywords = set(domain_info["keywords"])
            overlap = query_keywords & domain_keywords
            if overlap:
                matching_domains.append(domain_name)

        if not matching_domains:
            return []

        # Look up gaps for matching domains
        all_gaps = self._store.list_knowledge_gaps(team_id=team_id)
        relevant = [
            gap for gap in all_gaps
            if gap.get("domain") in matching_domains
        ]

        return relevant[:10]

    # ------------------------------------------------------------------
    # Internal: Team data gathering
    # ------------------------------------------------------------------

    def _get_team_chunks(self, team_id: str) -> List[Dict[str, Any]]:
        """Get all shared/public chunks visible to this team."""
        cursor = self._store.conn.cursor()
        cursor.execute("""
            SELECT c.* FROM chunks c
            WHERE c.visibility IN ('shared', 'public')
            ORDER BY c.createdAt DESC
            LIMIT 2000
        """)
        return [dict(row) for row in cursor.fetchall()]

    def _get_team_members(self, team_id: str) -> List[str]:
        """Get unique agent IDs in the team (from shared chunks)."""
        cursor = self._store.conn.cursor()
        cursor.execute("""
            SELECT DISTINCT owner FROM chunks
            WHERE visibility IN ('shared', 'public')
            AND owner IS NOT NULL
        """)
        return [row[0] for row in cursor.fetchall() if row[0]]

    # ------------------------------------------------------------------
    # Internal: Domain coverage analysis
    # ------------------------------------------------------------------

    def _analyze_domain_coverage(
        self,
        chunks: List[Dict[str, Any]],
        members: List[str],
        domain_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Analyze knowledge coverage per domain."""
        domains_to_check = DEFAULT_DOMAINS
        if domain_filter:
            domains_to_check = [
                d for d in DEFAULT_DOMAINS if d["name"] == domain_filter
            ]

        results: List[Dict[str, Any]] = []

        for domain_info in domains_to_check:
            domain_name = domain_info["name"]
            keywords = domain_info["keywords"]

            # Find chunks relevant to this domain
            relevant_chunks = []
            member_coverage: Dict[str, int] = defaultdict(int)

            for chunk in chunks:
                content = (chunk.get("content", "") + " " + (chunk.get("summary") or "")).lower()
                keyword_hits = sum(1 for kw in keywords if kw in content)

                if keyword_hits >= 2:  # Need at least 2 keyword matches
                    relevant_chunks.append(chunk.get("id", ""))
                    owner = chunk.get("owner", "")
                    if owner:
                        member_coverage[owner] += 1

            if not relevant_chunks:
                # No coverage at all
                coverage_score = 0.0
                members_with_coverage = []
            else:
                members_with_coverage = list(member_coverage.keys())
                # Coverage = fraction of team members who have knowledge
                coverage_score = len(members_with_coverage) / max(len(members), 1)

            results.append({
                "domain": domain_name,
                "description": f"Knowledge domain: {domain_name}",
                "total_chunks": len(relevant_chunks),
                "member_coverage": dict(member_coverage),
                "members_with_knowledge": members_with_coverage,
                "overall_coverage": round(coverage_score, 3),
                "coverage_percentage": round(coverage_score * 100, 1),
            })

        # Sort by coverage (lowest first = biggest gaps)
        results.sort(key=lambda d: d["overall_coverage"])
        return results

    # ------------------------------------------------------------------
    # Internal: Single-point-of-failure detection
    # ------------------------------------------------------------------

    def _detect_single_points(
        self,
        chunks: List[Dict[str, Any]],
        members: List[str],
    ) -> List[Dict[str, Any]]:
        """Detect knowledge that is held by only one team member."""
        if len(members) < 2:
            return []

        # Group chunks by owner
        owner_chunks: Dict[str, List[Dict]] = defaultdict(list)
        for chunk in chunks:
            owner = chunk.get("owner", "")
            if owner:
                owner_chunks[owner].append(chunk)

        spof_list: List[Dict[str, Any]] = []

        for domain_info in DEFAULT_DOMAINS:
            domain_name = domain_info["name"]
            keywords = domain_info["keywords"]

            # For each member, check which chunks are domain-relevant
            member_domain_chunks: Dict[str, List[str]] = defaultdict(list)

            for owner, owner_chunk_list in owner_chunks.items():
                for chunk in owner_chunk_list:
                    content = (chunk.get("content", "") + " " + (chunk.get("summary") or "")).lower()
                    keyword_hits = sum(1 for kw in keywords if kw in content)
                    if keyword_hits >= 2:
                        member_domain_chunks[owner].append(chunk.get("id", ""))

            # Find domains where only 1 member has knowledge
            members_with_knowledge = {
                m: chunks_list
                for m, chunks_list in member_domain_chunks.items()
                if chunks_list
            }

            if len(members_with_knowledge) == 1:
                sole_holder = list(members_with_knowledge.keys())[0]
                chunk_count = len(list(members_with_knowledge.values())[0])

                risk_level = "high" if chunk_count > 3 else "medium"
                if chunk_count > 10:
                    risk_level = "critical"

                spof_list.append({
                    "domain": domain_name,
                    "sole_holder": sole_holder,
                    "knowledge_chunks": chunk_count,
                    "risk_level": risk_level,
                    "recommendation": (
                        f"Only {sole_holder} has knowledge in {domain_name}. "
                        f"Consider knowledge sharing sessions or documentation."
                    ),
                })

        # Sort by risk (most critical first)
        risk_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        spof_list.sort(key=lambda s: risk_order.get(s["risk_level"], 3))
        return spof_list

    # ------------------------------------------------------------------
    # Internal: Gap identification
    # ------------------------------------------------------------------

    def _identify_gaps(
        self,
        domains: List[Dict[str, Any]],
        members: List[str],
    ) -> List[Dict[str, Any]]:
        """Identify knowledge gaps from domain coverage data."""
        gaps: List[Dict[str, Any]] = []

        for domain in domains:
            coverage = domain.get("overall_coverage", 1.0)
            domain_name = domain.get("domain", "unknown")

            if coverage < 0.2:
                severity = "critical"
            elif coverage < 0.4:
                severity = "high"
            elif coverage < 0.6:
                severity = "medium"
            else:
                continue  # Adequate coverage

            # Build gap details
            all_members = set(members)
            covered_members = set(domain.get("members_with_knowledge", []))
            uncovered = all_members - covered_members

            if severity in ("critical", "high"):
                recommendation = (
                    f"Critical gap in {domain_name}: "
                    f"Only {len(covered_members)}/{len(members)} team members have knowledge. "
                )
                if uncovered:
                    recommendation += (
                        f"Members without coverage: {', '.join(sorted(uncovered))}. "
                    )
                recommendation += "Schedule knowledge transfer sessions."
            else:
                recommendation = (
                    f"Moderate gap in {domain_name}: "
                    f"{len(covered_members)}/{len(members)} coverage. "
                    f"Encourage knowledge documentation."
                )

            gaps.append({
                "domain": domain_name,
                "severity": severity,
                "coverage": coverage,
                "coverage_percentage": domain.get("coverage_percentage", 0),
                "total_chunks": domain.get("total_chunks", 0),
                "members_with_knowledge": domain.get("members_with_knowledge", []),
                "uncovered_members": sorted(uncovered),
                "recommendation": recommendation,
            })

        # Sort by severity
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        gaps.sort(key=lambda g: severity_order.get(g["severity"], 3))
        return gaps

    # ------------------------------------------------------------------
    # Internal: Team map update
    # ------------------------------------------------------------------

    def _update_team_map(
        self,
        team_id: str,
        domains: List[Dict[str, Any]],
    ) -> None:
        """Update the team_knowledge_map table with current analysis."""
        for domain in domains:
            domain_name = domain.get("domain", "unknown")

            # Determine gap areas
            gap_areas = []
            coverage = domain.get("overall_coverage", 1.0)
            if coverage < 0.5:
                uncovered = domain.get("members_with_knowledge", [])
                gap_areas.append({
                    "issue": "low_coverage",
                    "coverage": coverage,
                    "members_with_knowledge": uncovered,
                })

            self._store.upsert_team_knowledge_map(
                team_id=team_id,
                domain=domain_name,
                description=domain.get("description", ""),
                member_coverage=domain.get("member_coverage", {}),
                overall_coverage=domain.get("overall_coverage", 0),
                gap_areas=gap_areas if gap_areas else None,
            )
