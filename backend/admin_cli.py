#!/usr/bin/env python3
"""
Admin CLI for Trading Intel MVP
Manually trigger content generation pipeline steps.

Usage:
    python admin_cli.py generate briefing [instrument]
    python admin_cli.py generate setup <instrument>
    python admin_cli.py generate roundup
    python admin_cli.py generate contrarian [instrument]
    python admin_cli.py generate full
    python admin_cli.py list content [--type setup] [--limit 10]
    python admin_cli.py list instruments
    python admin_cli.py news seed <csv_path>
    python admin_cli.py news fetch [--category CATEGORY]
    python admin_cli.py news sources [--category CATEGORY]
    python admin_cli.py status
"""
import argparse
import asyncio
import sys
from datetime import datetime

sys.path.insert(0, ".")

from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.models.models import ContentItem, Instrument, Tag, ContentType
from app.services.content_pipeline import (
    run_morning_briefing_pipeline,
    run_setup_pipeline,
    run_macro_roundup_pipeline,
    run_contrarian_check_pipeline,
    run_full_daily_pipeline,
)
from app.services import rss_news_service as news_service
from app.services.signals_service import generate_signal_sync


def run_async(coro):
    """Run an async coroutine and return the result."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def cmd_generate_briefing(instrument=None):
    """Generate morning briefing(s)."""
    print(f"\n{'='*50}")
    print(f"GENERATING MORNING BRIEFING{' for ' + instrument if instrument else ''}")
    print(f"{'='*50}")
    items = run_async(run_morning_briefing_pipeline(instrument=instrument))
    for item in items:
        print(f"\n  [BRIEFING] {item.title}")
        print(f"  Direction: {item.direction.value if item.direction else 'N/A'}")
        print(f"  Confidence: {item.confidence.value if item.confidence else 'N/A'}")
        print(f"  Published: {item.published_at.isoformat()}")
    print(f"\n  -> {len(items)} briefing(s) generated")
    return items


def cmd_generate_setup(instrument):
    """Generate trade setup for an instrument."""
    print(f"\n{'='*50}")
    print(f"GENERATING TRADE SETUP for {instrument}")
    print(f"{'='*50}")
    item = run_async(run_setup_pipeline(instrument))
    if item:
        print(f"\n  [SETUP] {item.title}")
        print(f"  Direction: {item.direction.value if item.direction else 'N/A'}")
        print(f"  Entry: {item.entry_zone}")
        print(f"  SL: {item.stop_loss} | TP: {item.take_profit}")
        print(f"  R:R: {item.risk_reward_ratio:.1f}")
        print(f"  Timeframe: {item.timeframe.value if item.timeframe else 'N/A'}")
        print(f"  Confidence: {item.confidence.value if item.confidence else 'N/A'}")
        print(f"  -> Setup generated successfully")
        return item
    else:
        print(f"\n  -> No valid setup generated (R:R < 1.5 or parsing failed)")
        return None


def cmd_generate_roundup():
    """Generate weekly macro roundup."""
    print(f"\n{'='*50}")
    print(f"GENERATING MACRO ROUNDUP")
    print(f"{'='*50}")
    item = run_async(run_macro_roundup_pipeline())
    print(f"\n  [MACRO ROUNDUP] {item.title}")
    print(f"  Published: {item.published_at.isoformat()}")
    print(f"  -> Macro roundup generated successfully")
    return item


def cmd_generate_contrarian(instrument):
    """Generate contrarian alert for an instrument."""
    print(f"\n{'='*50}")
    print(f"GENERATING CONTRARIAN ALERT for {instrument}")
    print(f"{'='*50}")
    item = run_async(run_contrarian_check_pipeline(instrument))
    if item:
        print(f"\n  [CONTRARIAN ALERT] {item.title}")
        print(f"  Direction: {item.direction.value if item.direction else 'N/A'}")
        print(f"  Published: {item.published_at.isoformat()}")
        print(f"  -> Contrarian alert generated successfully")
        return item
    else:
        print(f"\n  -> No contrarian alert generated (positioning not extreme)")
        return None


def cmd_generate_full():
    """Run full daily pipeline."""
    print(f"\n{'='*50}")
    print(f"RUNNING FULL DAILY PIPELINE")
    print(f"{'='*50}")
    results = run_async(run_full_daily_pipeline())
    total = (
        len(results["briefings"])
        + len(results["setups"])
        + (1 if results["roundup"] else 0)
        + len(results["contrarian"])
    )
    print(f"\n  Briefings: {len(results['briefings'])}")
    print(f"  Setups: {len(results['setups'])}")
    print(f"  Roundup: {'Yes' if results['roundup'] else 'No'}")
    print(f"  Contrarian: {len(results['contrarian'])}")
    print(f"\n  -> Total: {total} content items generated")
    return results


def cmd_list_content(content_type=None, limit=10):
    """List recent content items."""
    db = SessionLocal()
    try:
        query = db.query(ContentItem)
        if content_type:
            query = query.filter(ContentItem.content_type == ContentType(content_type))
        items = query.order_by(ContentItem.published_at.desc()).limit(limit).all()

        print(f"\n{'='*50}")
        print(f"RECENT CONTENT ({len(items)} items){f' [type: {content_type}]' if content_type else ''}")
        print(f"{'='*50}")
        for item in items:
            inst = item.instrument.symbol if item.instrument else "N/A"
            print(f"\n  [{item.content_type.value.upper()}] {item.title[:60]}")
            print(f"  Instrument: {inst} | Direction: {item.direction.value if item.direction else 'N/A'} | Published: {item.published_at.strftime('%Y-%m-%d %H:%M')}")
    finally:
        db.close()


def cmd_list_instruments():
    """List all instruments."""
    db = SessionLocal()
    try:
        instruments = db.query(Instrument).order_by(Instrument.asset_class, Instrument.symbol).all()
        print(f"\n{'='*50}")
        print(f"INSTRUMENTS ({len(instruments)} total)")
        print(f"{'='*50}")
        current_class = None
        for inst in instruments:
            if inst.asset_class != current_class:
                current_class = inst.asset_class
                print(f"\n  [{current_class.value.upper()}]")
            print(f"    {inst.symbol:10} - {inst.name}")
    finally:
        db.close()


def cmd_news_seed(csv_path: str):
    """Seed news sources from a CSV file."""
    print(f"Seeding news sources from {csv_path}...")
    db = SessionLocal()
    try:
        inserted, skipped = news_service.seed_sources_from_csv(csv_path, db)
        print(f"  Inserted: {inserted}")
        print(f"  Skipped (already exist): {skipped}")
    finally:
        db.close()


def cmd_news_fetch(category: str = None):
    """Fetch news from all (or one category of) RSS sources."""
    print(f"Fetching news...{' (category: ' + category + ')' if category else ''}")
    sources_updated, new_items, errors = news_service.fetch_all_sources_sync(category=category)
    print(f"  Sources updated: {sources_updated}")
    print(f"  New items stored: {new_items}")
    print(f"  Errors: {errors}")


def cmd_news_sources(category: str = None):
    """List configured RSS news sources."""
    db = SessionLocal()
    try:
        sources = news_service.get_sources(db, category=category)
        print(f"\nRSS Sources{(' (' + category + ')') if category else ''}:")
        print(f"{'='*60}")
        current_cat = None
        for s in sources:
            if s.category != current_cat:
                current_cat = s.category
                print(f"\n  [{current_cat}]")
            status = "enabled" if s.enabled else "DISABLED"
            last = s.last_fetched_at.strftime("%Y-%m-%d %H:%M") if s.last_fetched_at else "never"
            print(f"    {s.name}: {status} | last fetched: {last} | count: {s.fetch_count}")
    finally:
        db.close()


def cmd_signal(asset: str):
    """Generate a trading signal for an asset."""
    import app.services.signals_service as signals_svc
    print(f"Generating trading signal for {asset.upper()}...")
    print("(This runs 4 LLM stages — will take ~10-20 seconds)")
    result = signals_svc.generate_signal_sync(asset)
    s4 = result.get("stage4", {})
    s1 = result.get("stage1", {})
    print(f"\n  Signal: {s4.get('final_signal', 'N/A')}")
    print(f"  Direction: {s4.get('direction', 'N/A')}")
    print(f"  Confidence: {s4.get('signal_confidence', 'N/A')}%")
    print(f"  Regime: {s1.get('market_regime', 'N/A')} / {s1.get('volatility_regime', 'N/A')}")
    print(f"  Entry: {s4.get('entry_price', 'N/A')} | SL: {s4.get('stop_loss', 'N/A')} | TP: {s4.get('target_price', 'N/A')}")
    print(f"  R:R: {s4.get('risk_reward', 'N/A')}")
    print(f"  Position Size: {s4.get('recommended_position_size_pct', 'N/A')}%")
    print(f"\n  Summary: {s4.get('signal_summary', 'N/A')[:200]}")


def cmd_signals_list(asset: str = None, limit: int = 10):
    """List stored trading signals."""
    from app.services.signals_service import get_signals
    from app.models.models import TradingSignal
    db = SessionLocal()
    try:
        signals, total = get_signals(db, asset=asset, limit=limit)
        print(f"\nTrading Signals{(' (' + asset.upper() + ')') if asset else ''} — {total} total")
        print(f"{'='*70}")
        for sig in signals:
            conf = f"{sig.signal_confidence}%" if sig.signal_confidence is not None else "N/A"
            entry = f"{sig.entry_price:.5g}" if sig.entry_price else "N/A"
            print(f"  [{sig.id}] {sig.asset} | {sig.final_signal} | {sig.direction} | conf={conf}")
            print(f"       entry={entry} | SL={sig.stop_loss} | TP={sig.target_price} | R:R={sig.risk_reward_ratio}")
            print(f"       regime={sig.market_regime} | bias={sig.fundamental_bias} | gate={sig.gate_signal}")
            print(f"       generated={sig.generated_at.strftime('%Y-%m-%d %H:%M')} | outcome={sig.outcome}")
    finally:
        db.close()


def cmd_status():
    """Show system status."""
    from app.models.models import NewsSource, NewsItem, TradeOutcome, COTSnapshot, AlertRule, AlertLog

    print(f"SYSTEM STATUS")
    print(f"{'='*50}")

    # Database status
    db_status = "unknown"
    try:
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {e}"

    # Count items
    db = SessionLocal()
    try:
        content_count = db.query(ContentItem).count()
        instrument_count = db.query(Instrument).count()
        tag_count = db.query(Tag).count()
        source_count = db.query(NewsSource).count()
        news_count = db.query(NewsItem).count()
        outcome_count = db.query(TradeOutcome).count()
        cot_count = db.query(COTSnapshot).count()
        alert_rule_count = db.query(AlertRule).count()
        alert_log_count = db.query(AlertLog).count()
    finally:
        db.close()

    print(f"\n  Database: {db_status}")
    print(f"  Content items: {content_count}")
    print(f"  Instruments: {instrument_count}")
    print(f"  Tags: {tag_count}")
    print(f"  News sources: {source_count}")
    print(f"  News items: {news_count}")
    print(f"  Trade outcomes: {outcome_count}")
    print(f"  COT snapshots: {cot_count}")
    print(f"  Alert rules: {alert_rule_count}")
    print(f"  Alert logs: {alert_log_count}")

    print(f"\n  API Keys:")
    print(f"    Alpha Vantage: {'configured' if settings.ALPHA_VANTAGE_API_KEY else 'NOT SET'}")
    print(f"    MiniMax: {'configured' if settings.MINIMAX_API_KEY else 'NOT SET'}")
    print(f"    Finnhub: {'configured' if settings.FINNHUB_API_KEY else 'NOT SET'}")
    print(f"    NewsAPI: {'configured' if settings.NEWSAPI_KEY else 'NOT SET'}")

    print(f"\n  Environment: {settings.ENVIRONMENT}")
    print(f"  Debug: {settings.DEBUG}")


def cmd_backfill_mql5(force: bool = False, slug: str = None):
    """Download ISM/PMI series from MQL5 and save as Parquet."""
    from app.services.mql5_loader import backfill_mql5_series, backfill_all, MQL5_SERIES
    if slug:
        results = [backfill_mql5_series(slug, force=force)]
    else:
        results = backfill_all(force=force)
    print("\nMQL5 Backfill Results:")
    print(f"  {'Slug':<40} {'Status':<10} {'Rows'}")
    print(f"  {'-'*40} {'-'*10} {'-'*6}")
    for r in results:
        print(f"  {r['slug']:<40} {r['status']:<10} {r['rows']}")
    ok = sum(1 for r in results if r["status"] in ("ok", "skipped"))
    print(f"\n  {ok}/{len(results)} series ready.")


def main():
    parser = argparse.ArgumentParser(description="Trading Intel Admin CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # generate subcommand
    gen_parser = subparsers.add_parser("generate", help="Generate content")
    gen_subparsers = gen_parser.add_subparsers(dest="gen_command")

    briefing_parser = gen_subparsers.add_parser("briefing", help="Generate morning briefing")
    briefing_parser.add_argument("instrument", nargs="?", default=None, help="Optional instrument symbol")

    setup_parser = gen_subparsers.add_parser("setup", help="Generate trade setup")
    setup_parser.add_argument("instrument", help="Instrument symbol (e.g., EURUSD)")

    roundup_parser = gen_subparsers.add_parser("roundup", help="Generate macro roundup")

    contrarian_parser = gen_subparsers.add_parser("contrarian", help="Generate contrarian alert")
    contrarian_parser.add_argument("instrument", help="Instrument symbol")

    full_parser = gen_subparsers.add_parser("full", help="Run full daily pipeline")

    # list subcommand
    list_parser = subparsers.add_parser("list", help="List items")
    list_subparsers = list_parser.add_subparsers(dest="list_command")

    content_parser = list_subparsers.add_parser("content", help="List content items")
    content_parser.add_argument("--type", default=None, help="Filter by content type (briefing, setup, macro_roundup, contrarian_alert)")
    content_parser.add_argument("--limit", type=int, default=10, help="Number of items to show")

    instruments_parser = list_subparsers.add_parser("instruments", help="List instruments")

    # status subcommand
    subparsers.add_parser("status", help="Show system status")

    # news subcommand
    news_parser = subparsers.add_parser("news", help="Manage RSS news feeds")
    news_subparsers = news_parser.add_subparsers(dest="news_command")

    news_seed_parser = news_subparsers.add_parser("seed", help="Seed sources from CSV")
    news_seed_parser.add_argument("csv_path", help="Path to the CSV file")

    news_fetch_parser = news_subparsers.add_parser("fetch", help="Fetch news from RSS feeds")
    news_fetch_parser.add_argument("--category", default=None, help="Filter to a specific category")

    news_sources_parser = news_subparsers.add_parser("sources", help="List RSS sources")
    news_sources_parser.add_argument("--category", default=None, help="Filter to a specific category")

    # signal subcommand
    sig_parser = subparsers.add_parser("signal", help="Generate or list trading signals")
    sig_subparsers = sig_parser.add_subparsers(dest="sig_command")

    sig_gen_parser = sig_subparsers.add_parser("generate", help="Generate signal for an asset")
    sig_gen_parser.add_argument("asset", help="Asset ticker (e.g. EURUSD, BTCUSD, SPY)")

    sig_list_parser = sig_subparsers.add_parser("list", help="List stored signals")
    sig_list_parser.add_argument("--asset", default=None, help="Filter by asset")
    sig_list_parser.add_argument("--limit", type=int, default=10, help="Number to show")

    # backfill-mql5 subcommand
    mql5_parser = subparsers.add_parser("backfill-mql5", help="Download ISM/PMI data from MQL5")
    mql5_parser.add_argument("--force", action="store_true", help="Re-download even if Parquet already exists")
    mql5_parser.add_argument("--slug", default=None, help="Download a single slug only (e.g. ism-manufacturing-pmi)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == "generate":
        if args.gen_command == "briefing":
            cmd_generate_briefing(args.instrument)
        elif args.gen_command == "setup":
            cmd_generate_setup(args.instrument)
        elif args.gen_command == "roundup":
            cmd_generate_roundup()
        elif args.gen_command == "contrarian":
            cmd_generate_contrarian(args.instrument)
        elif args.gen_command == "full":
            cmd_generate_full()
        else:
            gen_parser.print_help()
    elif args.command == "list":
        if args.list_command == "content":
            cmd_list_content(args.type, args.limit)
        elif args.list_command == "instruments":
            cmd_list_instruments()
        else:
            list_parser.print_help()
    elif args.command == "status":
        cmd_status()
    elif args.command == "news":
        if args.news_command == "seed":
            cmd_news_seed(args.csv_path)
        elif args.news_command == "fetch":
            cmd_news_fetch(args.category)
        elif args.news_command == "sources":
            cmd_news_sources(args.category)
        else:
            news_parser.print_help()
    elif args.command == "signal":
        if args.sig_command == "generate":
            cmd_signal(args.asset)
        elif args.sig_command == "list":
            cmd_signals_list(asset=args.asset, limit=args.limit)
        else:
            sig_parser.print_help()
    elif args.command == "backfill-mql5":
        cmd_backfill_mql5(force=args.force, slug=args.slug)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
