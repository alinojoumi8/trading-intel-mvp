from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import Base, engine
from app.routers import content, instruments, tags, pipeline, news, signals, trade_outcomes, cot_history, regime, multi_timeframe, alerts, correlation, economic_calendar, auth, billing

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Trading Intel API",
    description="AI-powered trading intelligence platform - content management and discovery",
    version="1.0.0",
    debug=settings.DEBUG,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(content.router)
app.include_router(instruments.router)
app.include_router(tags.router)
app.include_router(pipeline.router)
app.include_router(news.router)
app.include_router(signals.router)
app.include_router(trade_outcomes.router)
app.include_router(cot_history.router)
app.include_router(regime.router)
app.include_router(multi_timeframe.router)
app.include_router(alerts.router)
app.include_router(correlation.router)
app.include_router(economic_calendar.router)
app.include_router(auth.router, prefix="/api")
app.include_router(billing.router, prefix="/api")


@app.get("/")
def root():
    return {
        "message": "Trading Intel API",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health")
def health_check():
    return {"status": "healthy", "environment": settings.ENVIRONMENT}


@app.get("/health/detailed")
def detailed_health_check():
    """Detailed health check with database and service status."""
    from app.core.database import engine
    from sqlalchemy import text

    # Check database connection
    db_status = "disconnected"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"

    # Check service configurations
    services = {
        "alpha_vantage": "configured" if settings.ALPHA_VANTAGE_API_KEY else "not configured",
        "minimax": "configured" if settings.MINIMAX_API_KEY else "not configured",
        "finnhub": "configured" if settings.FINNHUB_API_KEY else "not configured",
        "newsapi": "configured" if settings.NEWSAPI_KEY else "not configured",
    }

    # Add billing status note for MiniMax if configured
    if settings.MINIMAX_API_KEY:
        services["minimax"] = "configured"

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "database": db_status,
        "services": services,
    }
