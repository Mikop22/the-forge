"""Reference image retrieval and ranking helpers for Architect."""

from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass
from typing import Iterable, Optional

_STYLE_PRIORITY = (
    ("pixel art", 30.0),
    ("sprite", 24.0),
    ("illustration", 18.0),
    ("concept art", 16.0),
    ("artstation", 10.0),
    ("photo", 4.0),
)

_SINGLE_SUBJECT_HINTS = (
    "character",
    "portrait",
    "full body",
    "single",
    "solo",
    "sprite",
)

_CLUTTER_HINTS = (
    "collage",
    "poster",
    "wallpaper",
    "sheet",
    "sprite sheet",
    "meme",
    "ui",
    "screenshot",
    "card",
    "gacha",
    "tier list",
    "cursor",
    "cursor pack",
    "icon pack",
    "mobile game",
    "tier ranking",
    "top 10",
)

_PLAIN_BACKGROUND_HINTS = (
    "transparent background",
    "white background",
    "plain background",
    "isolated",
    "cutout",
    "no background",
)

_BUSY_BACKGROUND_HINTS = (
    "battle scene",
    "background scene",
    "landscape",
    "cityscape",
    "wallpaper",
    "poster",
    "group shot",
    "multiple characters",
)

_BLOCKED_SOURCE_HINTS = (
    "cults3d",
    "thingiverse",
    "myminifactory",
    "cgtrader",
    "turbosquid",
    "etsy",
    "amazon",
    "ebay",
    "propswords",
    "pinterest",
    "wish.com",
    "aliexpress",
    "redbubble",
    "teepublic",
)

_REAL_OBJECT_HINTS = (
    "photo",
    "real life",
    "real-life",
    "replica",
    "for sale",
    "product shot",
    "cosplay",
    "unboxing",
    "review",
)


@dataclass(frozen=True)
class ReferenceCandidate:
    url: str
    title: str
    source: str
    score: float
    rationale: str


class BrowserReferenceFinder:
    """Find reference candidates by scraping Bing Images with Playwright."""

    def __init__(
        self,
        *,
        fetch_count: int = 10,
        review_count: int = 10,
    ) -> None:
        self._fetch_count = fetch_count
        self._review_count = review_count
        self._timeout = 15

    def find_candidates(
        self,
        subject: str,
        prompt: str,
        *,
        attempt: int = 0,
        item_type: str = "",
        sub_type: str = "",
    ) -> list[ReferenceCandidate]:
        if not subject.strip():
            return []

        items: list[dict] = []
        for query in self._build_queries(subject, prompt, attempt, item_type=item_type, sub_type=sub_type):
            results = self._search(query)
            items.extend(results)

        if not items:
            return []

        ranked = self._rank(items)
        return ranked[: self._review_count]

    @staticmethod
    def _shorten_subject(subject: str) -> str:
        """Strip parentheticals and cap length so search queries stay effective."""
        short = re.sub(r"\s*\([^)]*\)", "", subject).strip()
        if not short:
            short = subject
        if len(short) > 60:
            short = short[:60].rsplit(" ", 1)[0]
        return short

    def _build_queries(
        self,
        subject: str,
        prompt: str,
        attempt: int,
        *,
        item_type: str = "",
        sub_type: str = "",
    ) -> list[str]:
        queries: list[str] = []

        short = self._shorten_subject(subject)

        queries.append(prompt.strip())
        queries.append(f"{short} clipart")

        if attempt > 0:
            queries.append(f"{short} fan art")

        seen: set[str] = set()
        deduped: list[str] = []
        for q in queries:
            q_clean = q.strip()
            if q_clean and q_clean not in seen:
                seen.add(q_clean)
                deduped.append(q_clean)
        return deduped

    def _search(self, query: str) -> list[dict]:
        from playwright.sync_api import sync_playwright

        encoded = urllib.parse.quote_plus(query)
        url = f"https://www.bing.com/images/search?q={encoded}&form=HDRSC2&first=1"

        results = []
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)
                page = browser.new_page(
                    user_agent=(
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/131.0.0.0 Safari/537.36"
                    )
                )
                page.goto(url, wait_until="domcontentloaded", timeout=15000)
                page.wait_for_timeout(2000)

                items = page.evaluate("""(maxCount) => {
                    const results = [];
                    const seen = new Set();
                    const cards = document.querySelectorAll('a.iusc');

                    for (const card of cards) {
                        if (results.length >= maxCount) break;
                        try {
                            const m = JSON.parse(card.getAttribute('m') || '{}');
                            const original = m.murl || '';
                            if (!original || seen.has(original)) continue;
                            seen.add(original);

                            const title = m.t || card.getAttribute('aria-label') || '';
                            const source = m.purl || '';
                            const width = m.mw || 0;
                            const height = m.mh || 0;

                            results.push({
                                original: original,
                                thumbnail: m.turl || '',
                                title: title,
                                source: source,
                                width: width,
                                height: height,
                            });
                        } catch {}
                    }
                    return results;
                }""", self._fetch_count)

                results = items or []
                browser.close()
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("Browser search failed: %s", exc)
            return []

        return results

    def _rank(self, items: Iterable[dict]) -> list[ReferenceCandidate]:
        candidates: list[ReferenceCandidate] = []
        seen_urls = set()

        for entry in items:
            url = str(entry.get("original") or entry.get("thumbnail") or "").strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            title = str(entry.get("title") or "").strip()
            source = str(entry.get("source") or entry.get("link") or "").strip()
            haystack = f"{title} {source} {url}".lower()
            rejection_reason = _rejection_reason(haystack)
            if rejection_reason:
                continue

            score = 0.0
            reasons = []

            style_score, style_reason = _style_score(haystack)
            score += style_score
            if style_reason:
                reasons.append(style_reason)

            if any(token in haystack for token in _SINGLE_SUBJECT_HINTS):
                score += 10.0
                reasons.append("single_subject")

            plain_hits = sum(1 for token in _PLAIN_BACKGROUND_HINTS if token in haystack)
            if plain_hits:
                score += 14.0 + max(0, plain_hits - 1) * 4.0
                reasons.append("plain_background")

            clutter_hits = sum(1 for token in _CLUTTER_HINTS if token in haystack)
            if clutter_hits:
                score -= 8.0 * clutter_hits
                reasons.append("clutter_penalty")

            busy_hits = sum(1 for token in _BUSY_BACKGROUND_HINTS if token in haystack)
            if busy_hits:
                score -= 6.0 * busy_hits
                reasons.append("busy_background_penalty")

            if ".png" in haystack:
                score += 3.0

            if re.search(r"\b(official|art|render)\b", haystack):
                score += 6.0

            width = entry.get("original_width") or entry.get("width") or 0
            height = entry.get("original_height") or entry.get("height") or 0
            if width and height:
                aspect = max(width, height) / max(min(width, height), 1)
                if aspect > 3.0:
                    score -= 12.0
                    reasons.append("extreme_aspect_ratio")
                elif aspect <= 1.5:
                    score += 5.0
                    reasons.append("square_aspect")
                if max(width, height) > 2000:
                    score -= 6.0
                    reasons.append("oversized")

            candidates.append(
                ReferenceCandidate(
                    url=url,
                    title=title,
                    source=source,
                    score=score,
                    rationale=", ".join(reasons) or "neutral",
                )
            )

        candidates.sort(key=lambda item: item.score, reverse=True)
        return candidates


def _style_score(text: str) -> tuple[float, str]:
    for token, score in _STYLE_PRIORITY:
        if token in text:
            return score, f"style:{token}"
    return 0.0, ""


def _rejection_reason(text: str) -> str | None:
    if any(token in text for token in _BLOCKED_SOURCE_HINTS):
        return "blocked_source"
    if any(token in text for token in _REAL_OBJECT_HINTS):
        return "photo_or_real_object"
    return None
