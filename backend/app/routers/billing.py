import os
import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.models import User
from app.routers.auth import get_current_user

router = APIRouter(prefix="/billing", tags=["billing"])

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY or os.getenv("STRIPE_SECRET_KEY", "")


def _frontend_url(path: str) -> str:
    base_url = settings.FRONTEND_URL.rstrip("/")
    return f"{base_url}{path}"


# ─── Schemas ───────────────────────────────────────────────────────────────────

class SubscriptionStatus(BaseModel):
    subscription_tier: str
    stripe_customer_id: str | None = None
    is_pro: bool


class CheckoutSessionResponse(BaseModel):
    checkout_url: str


class PortalSessionResponse(BaseModel):
    portal_url: str


# ─── Helper ───────────────────────────────────────────────────────────────────

def get_or_create_stripe_customer(user: User, db: Session) -> str:
    """Get existing Stripe customer ID or create a new one."""
    if user.stripe_customer_id:
        return user.stripe_customer_id

    # Create Stripe customer
    customer = stripe.Customer.create(
        email=user.email,
        name=user.name or "",
        metadata={"user_id": str(user.id)},
    )

    user.stripe_customer_id = customer.id
    db.commit()
    db.refresh(user)

    return customer.id


# ─── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/status", response_model=SubscriptionStatus)
def get_billing_status(
    current_user: User = Depends(get_current_user),
):
    """Get current user's subscription status."""
    return SubscriptionStatus(
        subscription_tier=current_user.subscription_tier,
        stripe_customer_id=current_user.stripe_customer_id,
        is_pro=current_user.subscription_tier == "pro",
    )


@router.post("/create-checkout-session", response_model=CheckoutSessionResponse)
def create_checkout_session(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a Stripe Checkout session for PRO upgrade."""
    if not settings.STRIPE_SECRET_KEY or settings.STRIPE_SECRET_KEY == "sk_test_placeholder":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe is not configured",
        )
    if not settings.STRIPE_PRICE_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe price is not configured",
        )

    try:
        customer_id = get_or_create_stripe_customer(current_user, db)

        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[
                {
                    "price": settings.STRIPE_PRICE_ID,
                    "quantity": 1,
                }
            ],
            mode="subscription",
            success_url=_frontend_url("/pricing?upgrade=success"),
            cancel_url=_frontend_url("/pricing?upgrade=cancelled"),
            metadata={
                "user_id": str(current_user.id),
            },
        )

        return CheckoutSessionResponse(checkout_url=session.url)

    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e.user_message if hasattr(e, "user_message") else str(e)),
        )


@router.post("/create-portal-session", response_model=PortalSessionResponse)
def create_portal_session(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a Stripe Customer Portal session."""
    if not settings.STRIPE_SECRET_KEY or settings.STRIPE_SECRET_KEY == "sk_test_placeholder":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe is not configured",
        )

    if not current_user.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Stripe customer found. Please upgrade first.",
        )

    try:
        session = stripe.billing_portal.Session.create(
            customer=current_user.stripe_customer_id,
            return_url=_frontend_url("/pricing"),
        )

        return PortalSessionResponse(portal_url=session.url)

    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e.user_message if hasattr(e, "user_message") else str(e)),
        )


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle Stripe webhook events."""
    if not settings.STRIPE_WEBHOOK_SECRET or settings.STRIPE_WEBHOOK_SECRET == "whsec_placeholder":
        return JSONResponse(content={"received": True}, status_code=200)

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payload",
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signature",
        )

    # Handle subscription events
    if event["type"] in ("checkout.session.completed", "customer.subscription.updated", "customer.subscription.deleted"):
        session_data = event["data"]["object"]

        customer_id = session_data.get("customer")
        if not customer_id:
            customer_id = session_data.get("id")

        # Find user by stripe customer id
        user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
        if not user:
            # Try to find by metadata
            user_id = session_data.get("metadata", {}).get("user_id")
            if user_id:
                user = db.query(User).filter(User.id == int(user_id)).first()

        if user:
            if event["type"] == "checkout.session.completed":
                # Subscription created via checkout
                user.subscription_tier = "pro"
            elif event["type"] == "customer.subscription.updated":
                # Check if still active
                subscription_status = session_data.get("status")
                if subscription_status == "active":
                    user.subscription_tier = "pro"
                else:
                    user.subscription_tier = "free"
            elif event["type"] == "customer.subscription.deleted":
                user.subscription_tier = "free"

            db.commit()

    return JSONResponse(content={"received": True}, status_code=200)
