"""Deduplication: attach an observation to an existing listing or start a new one.

Spec §3 order, conservative at every step:
1. stable source ID (same-source external_id; cross-source for globally
   unique ID namespaces like Greenhouse job IDs / Lever UUIDs),
2. canonical URL equality,
3. company + title + location similarity — strong matches merge, uncertain
   ones become a separate listing flagged `needs_review` (never auto-merged).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.discovery.adapters.base import ObservedJob
from app.discovery.models import DiscoverySource, JobListing, ListingSource
from app.discovery.normalize import (
    canonicalize_url,
    company_domain,
    locations_compatible,
    normalize_company,
    title_similarity,
)

#: Adapters whose external IDs are globally unique across the platform,
#: so the same ID under two sources of that adapter is the same job.
STABLE_ID_ADAPTERS = frozenset({"greenhouse", "lever"})

#: Fuzzy thresholds (kept high; below these we simply start a new listing).
AUTO_MERGE_TITLE_SIM = 0.92
REVIEW_TITLE_SIM = 0.80


@dataclass
class Match:
    """Where an observation attaches."""

    listing: JobListing | None  # None => create a new listing
    method: str  # external_id | canonical_url | fuzzy | new
    score: float | None = None
    needs_review: bool = False
    review_candidate: JobListing | None = None


def _companies_equivalent(
    observed_company: str | None,
    observed_url: str | None,
    listing: JobListing,
    source_config: dict,
) -> bool:
    n_obs = normalize_company(observed_company)
    n_list = normalize_company(listing.company_name)
    if n_obs and n_list and n_obs == n_list:
        return True
    # Domain bridge: careers-page domain vs configured source domain.
    obs_domain = source_config.get("domain") or company_domain(observed_url)
    list_domain = company_domain(listing.canonical_url)
    # Also allow config domains carried on either side via company fields.
    if obs_domain and list_domain and obs_domain == list_domain:
        return True
    cfg_domain = (source_config.get("domain") or "").lower()
    if cfg_domain and list_domain and cfg_domain == list_domain:
        return True
    return False


def find_match(
    db: Session,
    owner_id: str,
    source: DiscoverySource,
    job: ObservedJob,
) -> Match:
    """Locate the listing this observation belongs to (or why it doesn't)."""
    observed_url = canonicalize_url(job.source_url)
    external_id = (job.external_id or "").strip() or None

    # 1a. Same source + stable external ID.
    if external_id:
        link = db.execute(
            select(ListingSource).where(
                ListingSource.source_id == source.id,
                ListingSource.external_id == external_id,
            )
        ).scalar_one_or_none()
        if link is not None:
            return Match(listing=link.listing, method="external_id")

    # 1b. Same adapter platform, globally unique ID under another source.
    if external_id and source.adapter in STABLE_ID_ADAPTERS:
        rows = db.execute(
            select(ListingSource)
            .join(DiscoverySource, DiscoverySource.id == ListingSource.source_id)
            .where(
                DiscoverySource.owner_id == owner_id,
                DiscoverySource.adapter == source.adapter,
                ListingSource.external_id == external_id,
            )
        ).scalars()
        for link in rows:
            if link.listing is not None and link.listing.owner_id == owner_id:
                return Match(listing=link.listing, method="external_id")

    # 2. Canonical URL equality (listing-level or any source observation).
    if observed_url:
        listing = db.execute(
            select(JobListing).where(
                JobListing.owner_id == owner_id,
                JobListing.canonical_url == observed_url,
            )
        ).scalars().first()
        if listing is not None:
            return Match(listing=listing, method="canonical_url")
        rows = db.execute(
            select(ListingSource)
            .join(JobListing, JobListing.id == ListingSource.listing_id)
            .where(
                JobListing.owner_id == owner_id,
                ListingSource.source_url == observed_url,
            )
        ).scalars()
        for link in rows:
            if link.listing is not None:
                return Match(listing=link.listing, method="canonical_url")

    # 3. Conservative company + title + location similarity.
    candidates = db.execute(
        select(JobListing).where(
            JobListing.owner_id == owner_id,
            JobListing.status == "active",
        )
    ).scalars()
    best_fuzzy: tuple[JobListing, float] | None = None
    best_uncertain: tuple[JobListing, float] | None = None
    for listing in candidates:
        if not _companies_equivalent(
            job.company_name, job.source_url, listing, source.config or {}
        ):
            continue
        sim = title_similarity(job.title, listing.title)
        if sim < REVIEW_TITLE_SIM:
            continue
        if sim >= AUTO_MERGE_TITLE_SIM and locations_compatible(job.location, listing.location):
            if best_fuzzy is None or sim > best_fuzzy[1]:
                best_fuzzy = (listing, sim)
        elif sim >= REVIEW_TITLE_SIM:
            if best_uncertain is None or sim > best_uncertain[1]:
                best_uncertain = (listing, sim)
    if best_fuzzy is not None:
        return Match(listing=best_fuzzy[0], method="fuzzy", score=best_fuzzy[1])
    if best_uncertain is not None:
        # Strong-ish title but conflicting location: goes to review, no merge.
        return Match(
            listing=None,
            method="new",
            needs_review=True,
            review_candidate=best_uncertain[0],
        )
    return Match(listing=None, method="new")
