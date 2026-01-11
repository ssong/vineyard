"""SQLite persistence for research reports and opportunities.

Provides persistent storage so reports survive server restarts.
"""

import json
import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Database path - Use /app/data in Docker, fallback to ~/.vineyard locally
# Set VINEYARD_DATA_DIR env var to override
DEFAULT_DATA_DIR = "/app/data" if os.path.exists("/app") else os.path.expanduser("~/.vineyard/research-agent")
DATA_DIR = Path(os.getenv("VINEYARD_DATA_DIR", DEFAULT_DATA_DIR))
DB_PATH = DATA_DIR / "vineyard.db"


def _ensure_data_dir():
    """Create data directory with secure permissions."""
    if not DATA_DIR.exists():
        DATA_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
        logger.info(f"Created data directory: {DATA_DIR}")


@contextmanager
def _get_db():
    """Get database connection with context management."""
    _ensure_data_dir()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Initialize database with schema."""
    _ensure_data_dir()
    
    with _get_db() as conn:
        cursor = conn.cursor()
        
        # Reports table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id TEXT PRIMARY KEY,
                query TEXT,
                executive_summary TEXT,
                data JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Opportunities table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS opportunities (
                id TEXT PRIMARY KEY,
                report_id TEXT REFERENCES reports(id),
                name TEXT NOT NULL,
                one_liner TEXT,
                score INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                selected_at TIMESTAMP,
                project_url TEXT,
                data JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Index for efficient queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_opportunities_status 
            ON opportunities(status)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_opportunities_report 
            ON opportunities(report_id)
        """)
        
        logger.info("Database initialized")


def save_report(report_id: str, report) -> bool:
    """
    Save a research report and its opportunities to the database.
    
    Args:
        report_id: Unique report ID
        report: ResearchReport object
        
    Returns:
        True if successful
    """
    try:
        init_db()  # Ensure tables exist
        
        with _get_db() as conn:
            cursor = conn.cursor()
            
            # Get query from executive summary or default
            query = getattr(report, 'executive_summary', '')[:200] if report else ''
            
            # Insert report
            cursor.execute("""
                INSERT OR REPLACE INTO reports (id, query, executive_summary, data, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                report_id,
                query,
                getattr(report, 'executive_summary', ''),
                json.dumps(report.to_dict()) if hasattr(report, 'to_dict') else '{}',
                datetime.utcnow().isoformat(),
            ))
            
            # Insert opportunities
            for opp_report in getattr(report, 'opportunities', []):
                opp = opp_report.opportunity
                cursor.execute("""
                    INSERT OR REPLACE INTO opportunities 
                    (id, report_id, name, one_liner, score, status, data, created_at)
                    VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
                """, (
                    opp.id,
                    report_id,
                    opp.name,
                    opp.one_liner,
                    opp.overall_score,
                    json.dumps(opp.to_dict()) if hasattr(opp, 'to_dict') else '{}',
                    datetime.utcnow().isoformat(),
                ))
            
            logger.info(f"Saved report {report_id} with {len(report.opportunities)} opportunities")
            return True
            
    except Exception as e:
        logger.exception(f"Failed to save report: {e}")
        return False


def load_report(report_id: str):
    """
    Load a research report from the database.
    
    Args:
        report_id: Report ID to load
        
    Returns:
        ResearchReport object or None if not found
    """
    try:
        init_db()
        
        with _get_db() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM reports WHERE id = ?", (report_id,))
            row = cursor.fetchone()
            
            if not row:
                logger.debug(f"Report {report_id} not found in database")
                return None
            
            # Reconstruct report from stored data
            from src.models import (
                ResearchReport, OpportunityReport, Recommendation, RevenueForecast,
                Opportunity, OpportunityCategory, TargetSegment, BusinessModel,
                ValidationResult, ValidationConfidence, FourUResult, GraveyardCheck,
                PlatformRiskAssessment,
            )
            
            # Load opportunities for this report
            cursor.execute("""
                SELECT * FROM opportunities WHERE report_id = ? ORDER BY score DESC
            """, (report_id,))
            opp_rows = cursor.fetchall()
            
            opportunities = []
            for opp_row in opp_rows:
                opp_data = json.loads(opp_row['data']) if opp_row['data'] else {}
                
                # Reconstruct Opportunity object
                try:
                    opp = Opportunity(
                        id=opp_data.get('id', opp_row['id']),
                        name=opp_data.get('name', opp_row['name']),
                        slug=opp_data.get('slug', ''),
                        one_liner=opp_data.get('one_liner', opp_row['one_liner'] or ''),
                        detailed_description=opp_data.get('detailed_description', ''),
                        category=OpportunityCategory(opp_data.get('category', 'unbundling')),
                        target_segment=TargetSegment(opp_data.get('target_segment', 'smb')),
                        business_model=BusinessModel(opp_data.get('business_model', 'subscription_monthly')),
                        problem_statement=opp_data.get('problem_statement', ''),
                        current_solutions=opp_data.get('current_solutions', []),
                        pain_intensity=opp_data.get('pain_intensity', 5),
                        frequency=opp_data.get('frequency', 'weekly'),
                        target_market_description=opp_data.get('target_market_description', ''),
                        estimated_tam_businesses=opp_data.get('estimated_tam_businesses', 0),
                        geographic_focus=opp_data.get('geographic_focus', []),
                        direct_competitors=opp_data.get('direct_competitors', []),
                        competitor_weaknesses=opp_data.get('competitor_weaknesses', []),
                        differentiation_angle=opp_data.get('differentiation_angle', ''),
                        build_complexity=opp_data.get('build_complexity', 'medium'),
                        estimated_build_weeks=opp_data.get('estimated_build_weeks', 4),
                        key_technical_components=opp_data.get('key_technical_components', []),
                        platform_dependencies=opp_data.get('platform_dependencies', []),
                        suggested_price_low=opp_data.get('suggested_price_low', 0),
                        suggested_price_mid=opp_data.get('suggested_price_mid', 0),
                        suggested_price_high=opp_data.get('suggested_price_high', 0),
                        four_u_score=opp_data.get('four_u_score', 0),
                        solo_viability_score=opp_data.get('solo_viability_score', 0),
                        acquirability_score=opp_data.get('acquirability_score', 0),
                        overall_score=opp_data.get('overall_score', opp_row['score']),
                    )
                    
                    # Create minimal OpportunityReport
                    validation = ValidationResult(
                        opportunity_id=opp.id,
                        four_u_result=FourUResult(
                            unworkable_score=20,
                            unworkable_evidence="Loaded from DB",
                            unavoidable_score=20,
                            unavoidable_evidence="Loaded from DB",
                            urgent_score=20,
                            urgent_evidence="Loaded from DB",
                            underserved_score=20,
                            underserved_evidence="Loaded from DB",
                        ),
                        graveyard_check=GraveyardCheck(
                            is_graveyard=False,
                            graveyard_signals=[],
                            failed_competitors=[],
                            failure_reasons=[],
                            market_viability="viable",
                        ),
                        platform_risk=PlatformRiskAssessment(
                            platform_dependencies=[],
                            risk_level="low",
                            specific_risks=[],
                            mitigation_strategies=[],
                        ),
                        community_pain_signals=[],
                        confidence=ValidationConfidence.MEDIUM,
                        proceed_recommendation=True,
                        key_risks=[],
                        key_opportunities=[],
                    )
                    
                    forecast = RevenueForecast(
                        opportunity_id=opp.id,
                        assumed_arpu=opp.suggested_price_mid,
                        mrr_month_12_conservative=0,
                        mrr_month_12_moderate=0,
                        mrr_month_12_optimistic=0,
                        mrr_month_24_conservative=0,
                        mrr_month_24_moderate=0,
                        mrr_month_24_optimistic=0,
                        estimated_build_cost=0,
                        break_even_month_moderate=None,
                        exit_value_moderate=0,
                    )
                    
                    opp_report = OpportunityReport(
                        opportunity=opp,
                        validation=validation,
                        forecast=forecast,
                        recommendation=Recommendation.GO,
                        recommendation_rationale="",
                        next_steps=[],
                        risks_to_monitor=[],
                    )
                    opportunities.append(opp_report)
                    
                except Exception as e:
                    logger.warning(f"Failed to reconstruct opportunity: {e}")
                    continue
            
            # Create ResearchReport
            report = ResearchReport(
                report_id=report_id,
                generated_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else datetime.utcnow(),
                executive_summary=row['executive_summary'] or '',
                opportunities=opportunities,
            )
            
            if opportunities:
                report.top_recommendation = opportunities[0]
            
            logger.info(f"Loaded report {report_id} with {len(opportunities)} opportunities")
            return report
            
    except Exception as e:
        logger.exception(f"Failed to load report: {e}")
        return None


def mark_opportunity_selected(opportunity_id: str, project_url: str = "") -> bool:
    """Mark an opportunity as selected and reject siblings from the same report."""
    try:
        init_db()

        with _get_db() as conn:
            cursor = conn.cursor()

            # First, get the report_id for this opportunity
            cursor.execute("SELECT report_id FROM opportunities WHERE id = ?", (opportunity_id,))
            row = cursor.fetchone()
            report_id = row["report_id"] if row else None

            # Mark the selected opportunity
            cursor.execute("""
                UPDATE opportunities
                SET status = 'selected', selected_at = ?, project_url = ?
                WHERE id = ?
            """, (datetime.utcnow().isoformat(), project_url, opportunity_id))

            # Mark sibling opportunities from the same report as rejected
            if report_id:
                cursor.execute("""
                    UPDATE opportunities
                    SET status = 'rejected'
                    WHERE report_id = ? AND id != ? AND status = 'pending'
                """, (report_id, opportunity_id))

                rejected_count = cursor.rowcount
                if rejected_count > 0:
                    logger.info(f"Marked {rejected_count} sibling opportunities as rejected")

            return True

    except Exception as e:
        logger.exception(f"Failed to mark opportunity selected: {e}")
        return False


def reject_all_opportunities(report_id: str) -> int:
    """
    Reject all pending opportunities from a report.

    Args:
        report_id: The report ID whose opportunities should be rejected

    Returns:
        Number of opportunities rejected
    """
    try:
        init_db()

        with _get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE opportunities
                SET status = 'rejected'
                WHERE report_id = ? AND status = 'pending'
            """, (report_id,))

            rejected_count = cursor.rowcount
            if rejected_count > 0:
                logger.info(f"Rejected {rejected_count} opportunities from report {report_id}")

            return rejected_count

    except Exception as e:
        logger.exception(f"Failed to reject opportunities: {e}")
        return 0


def list_opportunities(limit: int = 20, status: Optional[str] = None) -> list[dict]:
    """
    List recent opportunities.

    Args:
        limit: Maximum number to return
        status: Filter by status ('pending', 'selected', 'rejected', or None for all)
        
    Returns:
        List of opportunity dicts with id, name, score, status, created_at
    """
    try:
        init_db()
        
        with _get_db() as conn:
            cursor = conn.cursor()
            
            if status:
                cursor.execute("""
                    SELECT o.id, o.name, o.one_liner, o.score, o.status, 
                           o.created_at, o.project_url, r.query
                    FROM opportunities o
                    LEFT JOIN reports r ON o.report_id = r.id
                    WHERE o.status = ?
                    ORDER BY o.created_at DESC
                    LIMIT ?
                """, (status, limit))
            else:
                cursor.execute("""
                    SELECT o.id, o.name, o.one_liner, o.score, o.status, 
                           o.created_at, o.project_url, r.query
                    FROM opportunities o
                    LEFT JOIN reports r ON o.report_id = r.id
                    ORDER BY o.created_at DESC
                    LIMIT ?
                """, (limit,))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
            
    except Exception as e:
        logger.exception(f"Failed to list opportunities: {e}")
        return []
