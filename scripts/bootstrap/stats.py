"""Stats tracker for the bootstrap library process."""

from __future__ import annotations

from backend.app.schemas import Passage


class StatsTracker:
    """Tracks statistics during library bootstrap."""

    def __init__(self) -> None:
        self.total_books: int = 0
        self.total_passages: int = 0
        self.passages_by_type: dict[str, int] = {}
        self.passages_by_category: dict[str, int] = {}
        self.reading_levels: list[float] = []
        self.errors: int = 0

    def record_passage(self, passage: Passage) -> None:
        """Update counters from a processed passage."""
        self.total_passages += 1
        ptype = passage.passage_type.value
        self.passages_by_type[ptype] = self.passages_by_type.get(ptype, 0) + 1
        pcat = passage.passage_category.value
        self.passages_by_category[pcat] = self.passages_by_category.get(pcat, 0) + 1
        self.reading_levels.append(passage.reading_level)

    def record_error(self) -> None:
        """Increment the error counter."""
        self.errors += 1

    def report(self) -> str:
        """Return a formatted summary string."""
        lines = [
            "═" * 50,
            "  Bootstrap Library — Stats Report",
            "═" * 50,
            f"  Total books processed : {self.total_books}",
            f"  Total passages        : {self.total_passages}",
            "",
            "  Breakdown by type:",
        ]
        for ptype in ("long", "short"):
            lines.append(f"    {ptype:<20} {self.passages_by_type.get(ptype, 0)}")
        lines.append("")
        lines.append("  Breakdown by category (top 5):")
        sorted_cats = sorted(
            self.passages_by_category.items(), key=lambda x: -x[1],
        )[:5]
        for cat, count in sorted_cats:
            lines.append(f"    {cat:<20} {count}")
        lines.append("")
        avg_rl = (
            sum(self.reading_levels) / len(self.reading_levels)
            if self.reading_levels
            else 0.0
        )
        lines.append(f"  Average reading level : {avg_rl:.1f}")
        lines.append(f"  Total errors          : {self.errors}")
        lines.append("═" * 50)
        return "\n".join(lines)
