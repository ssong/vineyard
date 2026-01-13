"""Opportunity history tracking for deduplication.

This module tracks previously suggested opportunities to prevent
repetitive suggestions across runs.
"""

import hashlib
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from src.models import Opportunity


class OpportunityHistory:
    """
    Tracks previously suggested opportunities to enable deduplication.

    Uses SQLite for persistence and provides similarity detection
    based on problem statements and keywords.
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the history tracker.

        Args:
            db_path: Path to SQLite database. Defaults to data/history.db
        """
        if db_path is None:
            db_path = Path(__file__).parent.parent.parent / "data" / "history.db"

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        """Initialize database tables."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS opportunities (
                id TEXT PRIMARY KEY,
                slug TEXT NOT NULL,
                name TEXT NOT NULL,
                category TEXT,
                target_segment TEXT,
                problem_statement TEXT,
                problem_hash TEXT,
                keywords TEXT,  -- JSON array of extracted keywords
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_slug ON opportunities(slug);
            CREATE INDEX IF NOT EXISTS idx_problem_hash ON opportunities(problem_hash);
            CREATE INDEX IF NOT EXISTS idx_created_at ON opportunities(created_at);
            CREATE INDEX IF NOT EXISTS idx_category ON opportunities(category);

            CREATE TABLE IF NOT EXISTS run_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                opportunity_ids TEXT,  -- JSON array
                query_set TEXT,  -- JSON array of queries used
                industries_sampled TEXT,  -- JSON array
                frameworks_used TEXT,  -- JSON array
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        self.conn.commit()

    def _extract_keywords(self, opportunity: Opportunity) -> list[str]:
        """Extract key terms from an opportunity for similarity matching."""
        text = " ".join([
            opportunity.name,
            opportunity.problem_statement,
            opportunity.detailed_description,
            opportunity.differentiation_angle,
            " ".join(opportunity.direct_competitors),
            " ".join(opportunity.current_solutions),
        ]).lower()

        # Simple keyword extraction - could be enhanced with NLP
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "must", "shall",
            "can", "need", "dare", "ought", "used", "to", "of", "in",
            "for", "on", "with", "at", "by", "from", "as", "into",
            "through", "during", "before", "after", "above", "below",
            "between", "under", "again", "further", "then", "once",
            "and", "but", "or", "nor", "so", "yet", "both", "either",
            "neither", "not", "only", "own", "same", "than", "too",
            "very", "just", "also", "now", "that", "this", "these",
            "those", "what", "which", "who", "whom", "whose", "where",
            "when", "why", "how", "all", "each", "every", "any", "some",
            "no", "more", "most", "other", "such", "software", "tool",
            "platform", "solution", "business", "small", "using", "use",
        }

        words = text.split()
        keywords = []
        for word in words:
            # Clean word
            word = "".join(c for c in word if c.isalnum())
            if len(word) > 3 and word not in stop_words:
                keywords.append(word)

        # Return unique keywords, limited to top 50
        return list(dict.fromkeys(keywords))[:50]

    def _hash_problem(self, problem_statement: str) -> str:
        """Create a hash of the problem statement for quick lookup."""
        normalized = " ".join(problem_statement.lower().split())
        return hashlib.md5(normalized.encode()).hexdigest()

    def record(self, opportunity: Opportunity) -> None:
        """
        Record an opportunity to prevent future duplicates.

        Args:
            opportunity: The opportunity to record
        """
        keywords = self._extract_keywords(opportunity)
        problem_hash = self._hash_problem(opportunity.problem_statement)

        self.conn.execute("""
            INSERT OR REPLACE INTO opportunities
            (id, slug, name, category, target_segment, problem_statement,
             problem_hash, keywords, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            opportunity.id,
            opportunity.slug,
            opportunity.name,
            opportunity.category.value if hasattr(opportunity.category, 'value') else str(opportunity.category),
            opportunity.target_segment.value if hasattr(opportunity.target_segment, 'value') else str(opportunity.target_segment),
            opportunity.problem_statement,
            problem_hash,
            json.dumps(keywords),
            datetime.now().isoformat(),
        ))
        self.conn.commit()

    def record_run(
        self,
        run_id: str,
        opportunity_ids: list[str],
        queries: list[str],
        industries: list[str],
        frameworks: list[str],
    ) -> None:
        """Record metadata about a discovery run."""
        self.conn.execute("""
            INSERT INTO run_history
            (run_id, opportunity_ids, query_set, industries_sampled, frameworks_used)
            VALUES (?, ?, ?, ?, ?)
        """, (
            run_id,
            json.dumps(opportunity_ids),
            json.dumps(queries),
            json.dumps(industries),
            json.dumps(frameworks),
        ))
        self.conn.commit()

    def is_duplicate(self, opportunity: Opportunity, days: int = 90) -> bool:
        """
        Check if this opportunity is a duplicate of a recent suggestion.

        Args:
            opportunity: The opportunity to check
            days: Look back period in days

        Returns:
            True if this appears to be a duplicate
        """
        # Check exact slug match
        if self.slug_exists(opportunity.slug, days):
            return True

        # Check problem hash match
        problem_hash = self._hash_problem(opportunity.problem_statement)
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        cursor = self.conn.execute("""
            SELECT 1 FROM opportunities
            WHERE problem_hash = ? AND created_at > ?
            LIMIT 1
        """, (problem_hash, cutoff))

        if cursor.fetchone():
            return True

        # Check keyword similarity
        return self.is_similar(opportunity, days, threshold=0.6)

    def is_similar(
        self,
        opportunity: Opportunity,
        days: int = 90,
        threshold: float = 0.6,
    ) -> bool:
        """
        Check if this opportunity is semantically similar to past suggestions.

        Uses Jaccard similarity on extracted keywords.

        Args:
            opportunity: The opportunity to check
            days: Look back period in days
            threshold: Similarity threshold (0-1)

        Returns:
            True if similarity exceeds threshold
        """
        new_keywords = set(self._extract_keywords(opportunity))
        if not new_keywords:
            return False

        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        cursor = self.conn.execute("""
            SELECT keywords FROM opportunities
            WHERE created_at > ?
        """, (cutoff,))

        for row in cursor:
            past_keywords = set(json.loads(row["keywords"]))
            if not past_keywords:
                continue

            # Jaccard similarity
            intersection = len(new_keywords & past_keywords)
            union = len(new_keywords | past_keywords)
            similarity = intersection / union if union > 0 else 0

            if similarity >= threshold:
                return True

        return False

    def slug_exists(self, slug: str, days: int = 90) -> bool:
        """Check if a slug was used recently."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        cursor = self.conn.execute("""
            SELECT 1 FROM opportunities
            WHERE slug = ? AND created_at > ?
            LIMIT 1
        """, (slug, cutoff))

        return cursor.fetchone() is not None

    def get_recent_slugs(self, days: int = 90) -> list[str]:
        """Get all slugs from recent opportunities."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        cursor = self.conn.execute("""
            SELECT slug FROM opportunities
            WHERE created_at > ?
            ORDER BY created_at DESC
        """, (cutoff,))

        return [row["slug"] for row in cursor]

    def get_recent_problems(self, days: int = 90) -> list[str]:
        """Get problem statements from recent opportunities."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        cursor = self.conn.execute("""
            SELECT problem_statement FROM opportunities
            WHERE created_at > ?
            ORDER BY created_at DESC
        """, (cutoff,))

        return [row["problem_statement"] for row in cursor]

    def get_category_distribution(self, days: int = 90) -> dict[str, int]:
        """Get distribution of categories in recent opportunities."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        cursor = self.conn.execute("""
            SELECT category, COUNT(*) as count
            FROM opportunities
            WHERE created_at > ?
            GROUP BY category
        """, (cutoff,))

        return {row["category"]: row["count"] for row in cursor}

    def get_underexplored_categories(self, days: int = 90) -> list[str]:
        """
        Identify categories that have been underexplored recently.

        Returns categories with below-average representation.
        """
        distribution = self.get_category_distribution(days)

        if not distribution:
            # No history, all categories are underexplored
            return [
                "unbundling", "productized_service", "integration",
                "boring_business", "developer_tools", "automation"
            ]

        avg_count = sum(distribution.values()) / len(distribution) if distribution else 0

        all_categories = [
            "unbundling", "productized_service", "integration",
            "boring_business", "developer_tools", "automation"
        ]

        underexplored = [
            cat for cat in all_categories
            if distribution.get(cat, 0) < avg_count
        ]

        return underexplored or all_categories

    def get_stats(self, days: int = 90) -> dict:
        """Get summary statistics about recorded opportunities."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        cursor = self.conn.execute("""
            SELECT
                COUNT(*) as total,
                COUNT(DISTINCT category) as unique_categories,
                COUNT(DISTINCT target_segment) as unique_segments
            FROM opportunities
            WHERE created_at > ?
        """, (cutoff,))

        row = cursor.fetchone()

        return {
            "total_opportunities": row["total"],
            "unique_categories": row["unique_categories"],
            "unique_segments": row["unique_segments"],
            "category_distribution": self.get_category_distribution(days),
            "underexplored_categories": self.get_underexplored_categories(days),
        }

    def clear_old(self, days: int = 180) -> int:
        """
        Clear opportunities older than specified days.

        Args:
            days: Age threshold in days

        Returns:
            Number of records deleted
        """
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        cursor = self.conn.execute("""
            DELETE FROM opportunities WHERE created_at < ?
        """, (cutoff,))

        self.conn.commit()
        return cursor.rowcount

    def close(self):
        """Close the database connection."""
        self.conn.close()


# Singleton instance for easy access
_history_instance: Optional[OpportunityHistory] = None


def get_history() -> OpportunityHistory:
    """Get the singleton history instance."""
    global _history_instance
    if _history_instance is None:
        _history_instance = OpportunityHistory()
    return _history_instance
