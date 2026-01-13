"""CLI utilities for managing research diversity.

This module provides commands for:
- Viewing history statistics
- Clearing old history
- Running focused research
- Listing available industries and frameworks
"""

import argparse
import json
import sys
from typing import Optional

from src.config.diversity import (
    DiversityConfig,
    INDUSTRIES,
    FRAMEWORKS,
    UNBUNDLING_TARGETS,
    PRODUCTIZABLE_SERVICES,
)
from src.tools.history import OpportunityHistory, get_history


def cmd_stats(args):
    """Show statistics about recorded opportunities."""
    history = get_history()
    stats = history.get_stats(days=args.days)

    print(f"\n=== Opportunity History Stats (last {args.days} days) ===\n")
    print(f"Total opportunities: {stats['total_opportunities']}")
    print(f"Unique categories: {stats['unique_categories']}")
    print(f"Unique segments: {stats['unique_segments']}")

    print("\nCategory distribution:")
    for cat, count in sorted(stats['category_distribution'].items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")

    print("\nUnderexplored categories:")
    for cat in stats['underexplored_categories']:
        print(f"  - {cat}")

    print()


def cmd_clear(args):
    """Clear old history entries."""
    history = get_history()

    if args.all:
        # Clear everything
        history.conn.execute("DELETE FROM opportunities")
        history.conn.execute("DELETE FROM run_history")
        history.conn.commit()
        print("Cleared all history.")
    else:
        count = history.clear_old(days=args.days)
        print(f"Cleared {count} opportunities older than {args.days} days.")


def cmd_recent(args):
    """Show recently suggested opportunities."""
    history = get_history()
    slugs = history.get_recent_slugs(days=args.days)

    print(f"\n=== Recent Opportunities (last {args.days} days) ===\n")

    if not slugs:
        print("No opportunities in history.")
        return

    for i, slug in enumerate(slugs[:args.limit], 1):
        print(f"{i}. {slug}")

    if len(slugs) > args.limit:
        print(f"\n... and {len(slugs) - args.limit} more")

    print()


def cmd_industries(args):
    """List available industries."""
    print("\n=== Available Industries ===\n")

    # Group by rough category
    categories = {
        "Construction & Trades": [],
        "Professional Services": [],
        "Healthcare & Wellness": [],
        "Property & Real Estate": [],
        "Automotive & Transportation": [],
        "Hospitality & Events": [],
        "Education & Training": [],
        "Retail & Services": [],
        "Food & Beverage": [],
        "Manufacturing & Industrial": [],
        "Agriculture & Outdoor": [],
        "Fitness & Recreation": [],
        "Personal Services": [],
        "Professional B2B": [],
        "Specialty Niches": [],
    }

    # Simple keyword-based categorization
    for industry in INDUSTRIES:
        lower = industry.lower()
        if any(k in lower for k in ["hvac", "plumb", "electric", "roof", "floor", "paint", "contract", "landscap", "pest", "pool", "garage", "lock", "appliance", "septic"]):
            categories["Construction & Trades"].append(industry)
        elif any(k in lower for k in ["account", "book", "tax", "law", "legal", "notary", "architect", "engineer", "survey", "court", "translat"]):
            categories["Professional Services"].append(industry)
        elif any(k in lower for k in ["dental", "vet", "optom", "chiro", "therapy", "mental", "health", "pharm", "lab", "senior", "hospice", "medic"]):
            categories["Healthcare & Wellness"].append(industry)
        elif any(k in lower for k in ["property", "real estate", "inspect", "apprais", "title", "storage", "parking"]):
            categories["Property & Real Estate"].append(industry)
        elif any(k in lower for k in ["auto", "tire", "dealer", "fleet", "tow", "moving", "freight", "courier"]):
            categories["Automotive & Transportation"].append(industry)
        elif any(k in lower for k in ["event", "cater", "wedding", "party", "photo", "dj", "hotel", "bed and", "vacation"]):
            categories["Hospitality & Events"].append(industry)
        elif any(k in lower for k in ["tutor", "music school", "dance", "martial", "driving school", "trade school", "daycare", "after-school"]):
            categories["Education & Training"].append(industry)
        elif any(k in lower for k in ["dry clean", "laundro", "car wash", "print", "sign shop", "trophy", "pawn", "consign", "florist"]):
            categories["Retail & Services"].append(industry)
        elif any(k in lower for k in ["restaurant", "food truck", "baker", "coffee", "brew", "winer", "distill"]):
            categories["Food & Beverage"].append(industry)
        elif any(k in lower for k in ["machine", "fabric", "wood", "3d print", "electron", "packag", "warehous"]):
            categories["Manufacturing & Industrial"].append(industry)
        elif any(k in lower for k in ["farm", "nurser", "tree", "irrig", "agricult", "feed"]):
            categories["Agriculture & Outdoor"].append(industry)
        elif any(k in lower for k in ["gym", "yoga", "pilates", "crossfit", "personal train", "sport", "bowl", "golf", "marina"]):
            categories["Fitness & Recreation"].append(industry)
        elif any(k in lower for k in ["salon", "barber", "spa", "nail", "tattoo", "funeral", "pet groom", "pet board", "dog walk"]):
            categories["Personal Services"].append(industry)
        elif any(k in lower for k in ["staff", "recruit", "hr", "market", "pr firm", "web design", "it service", "managed", "security", "clean", "janitor", "office supply"]):
            categories["Professional B2B"].append(industry)
        else:
            categories["Specialty Niches"].append(industry)

    for cat_name, industries in categories.items():
        if industries:
            print(f"\n{cat_name}:")
            for ind in sorted(industries):
                print(f"  - {ind}")

    print(f"\nTotal: {len(INDUSTRIES)} industries")


def cmd_frameworks(args):
    """List available frameworks."""
    print("\n=== Available Frameworks ===\n")

    frameworks_info = [
        ("unbundling", "Unbundling", "Extract focused features from complex platforms like Salesforce, Notion, etc."),
        ("productized_service", "Productized Service", "Turn expensive freelancer/agency services into affordable software"),
        ("integration", "Integration Gap", "Connect tools that don't work well together natively"),
        ("boring_business", "Boring Business", "Modern software for unglamorous industries still using spreadsheets"),
        ("developer_tools", "Developer Tools", "Productivity tools for programmers to automate repetitive tasks"),
        ("automation", "Automation & Workflows", "Automate manual multi-step processes in specific verticals"),
    ]

    for id, name, desc in frameworks_info:
        print(f"ID: {id}")
        print(f"Name: {name}")
        print(f"Description: {desc}")
        print()


def cmd_targets(args):
    """List unbundling targets (platforms)."""
    print("\n=== Unbundling Targets ===\n")

    for platform, use_cases in UNBUNDLING_TARGETS:
        print(f"{platform}:")
        for uc in use_cases:
            print(f"  - {uc}")
        print()


def cmd_services(args):
    """List productizable services."""
    print("\n=== Productizable Services ===\n")

    # Group by rough category
    categories = {}
    for service in PRODUCTIZABLE_SERVICES:
        lower = service.lower()
        if any(k in lower for k in ["design", "graphic", "video", "photo", "thumbnail", "banner"]):
            cat = "Content & Creative"
        elif any(k in lower for k in ["writing", "copy", "resume", "press", "case stud", "technical", "grant", "proposal"]):
            cat = "Writing & Copy"
        elif any(k in lower for k in ["seo", "keyword", "competitor", "social media", "influencer", "pr ", "email campaign", "landing"]):
            cat = "Marketing"
        elif any(k in lower for k in ["website", "security", "performance", "data entry", "data clean", "spreadsheet", "api", "database", "code"]):
            cat = "Technical"
        elif any(k in lower for k in ["bookkeep", "invoice", "expense", "payroll", "tax", "financial", "business plan", "pitch"]):
            cat = "Business Operations"
        elif any(k in lower for k in ["research", "intelligence", "user research", "survey", "visualiz", "report"]):
            cat = "Research & Analysis"
        else:
            cat = "Administrative"

        if cat not in categories:
            categories[cat] = []
        categories[cat].append(service)

    for cat_name, services in sorted(categories.items()):
        print(f"\n{cat_name}:")
        for svc in sorted(services):
            print(f"  - {svc}")

    print(f"\nTotal: {len(PRODUCTIZABLE_SERVICES)} services")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Research diversity management utilities",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.cli.diversity stats              # View history stats
  python -m src.cli.diversity stats --days 30    # Stats for last 30 days
  python -m src.cli.diversity clear --days 60   # Clear history older than 60 days
  python -m src.cli.diversity clear --all       # Clear all history
  python -m src.cli.diversity recent            # Show recent suggestions
  python -m src.cli.diversity industries        # List all industries
  python -m src.cli.diversity frameworks        # List all frameworks
  python -m src.cli.diversity targets           # List unbundling targets
  python -m src.cli.diversity services          # List productizable services
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # stats command
    stats_parser = subparsers.add_parser("stats", help="Show history statistics")
    stats_parser.add_argument("--days", type=int, default=90, help="Lookback period in days")
    stats_parser.set_defaults(func=cmd_stats)

    # clear command
    clear_parser = subparsers.add_parser("clear", help="Clear old history")
    clear_parser.add_argument("--days", type=int, default=180, help="Clear entries older than N days")
    clear_parser.add_argument("--all", action="store_true", help="Clear all history")
    clear_parser.set_defaults(func=cmd_clear)

    # recent command
    recent_parser = subparsers.add_parser("recent", help="Show recent opportunities")
    recent_parser.add_argument("--days", type=int, default=90, help="Lookback period in days")
    recent_parser.add_argument("--limit", type=int, default=20, help="Max entries to show")
    recent_parser.set_defaults(func=cmd_recent)

    # industries command
    industries_parser = subparsers.add_parser("industries", help="List available industries")
    industries_parser.set_defaults(func=cmd_industries)

    # frameworks command
    frameworks_parser = subparsers.add_parser("frameworks", help="List available frameworks")
    frameworks_parser.set_defaults(func=cmd_frameworks)

    # targets command
    targets_parser = subparsers.add_parser("targets", help="List unbundling targets")
    targets_parser.set_defaults(func=cmd_targets)

    # services command
    services_parser = subparsers.add_parser("services", help="List productizable services")
    services_parser.set_defaults(func=cmd_services)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
