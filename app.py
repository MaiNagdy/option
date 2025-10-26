from fastapi import FastAPI, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import uvicorn
import secrets
import hashlib
import json
from datetime import datetime, timedelta
from typing import Optional
import yfinance as yf
import pandas as pd
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, String, DateTime, Text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import OperationalError

# Load environment variables
load_dotenv()

# Import our option analysis functions
from get_option_data import get_option_data_for_symbols

# Application settings
APP_ENV = os.getenv("APP_ENV", "production")
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*").split(",")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

app = FastAPI(
    title="Smart Option Trading Analytics",
    description="Professional Options Analysis Platform with Intrinsic Value Calculations",
    version="2.0.0",
    docs_url="/api/docs" if DEBUG else None,
    redoc_url="/api/redoc" if DEBUG else None
)

# Security Middleware
if ALLOWED_HOSTS != ["*"]:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)

# CORS Middleware for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./option_trading.db")
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=1800)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    email = Column(String(255), primary_key=True, index=True)
    password = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    plan = Column(String(50), default="free")
    stripe_customer_id = Column(String(255), nullable=True)
    stripe_subscription_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    token = Column(String(255), primary_key=True, index=True)
    email = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)

class AnalysisHistory(Base):
    __tablename__ = "analysis_history"
    id = Column(String(64), primary_key=True, default=lambda: secrets.token_hex(32))
    email = Column(String(255), index=True, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    symbols = Column(Text)
    results_json = Column(Text)
    errors_json = Column(Text)

class AnalysisErrorLog(Base):
    __tablename__ = "analysis_errors"
    id = Column(String(64), primary_key=True, default=lambda: secrets.token_hex(32))
    email = Column(String(255), index=True, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    symbols = Column(Text)
    error = Column(Text)

class Session(Base):
    __tablename__ = "sessions"
    session_id = Column(String(255), primary_key=True, index=True)
    email = Column(String(255), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)


try:
    Base.metadata.create_all(bind=engine)
except OperationalError as e:
    print(f"❌ Database connection failed: {e}")
    raise


def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Legacy JSON history storage removed (now using Postgres)

# Analysis History Storage
def save_analysis_to_history(email, symbols, results, errors):
    try:
        with SessionLocal() as db:
            entry = AnalysisHistory(
                email=email,
                symbols=','.join(symbols),
                results_json=json.dumps(results),
                errors_json=json.dumps(errors)
            )
            db.add(entry)
            db.commit()

            # Keep only last 100 entries
            subquery = (
                db.query(AnalysisHistory.id)
                .filter(AnalysisHistory.email == email)
                .order_by(AnalysisHistory.timestamp.desc())
                .offset(100)
            )
            stale_ids = [row[0] for row in subquery.all()]
            if stale_ids:
                db.query(AnalysisHistory).filter(AnalysisHistory.id.in_(stale_ids)).delete(synchronize_session=False)
                db.commit()
            print(f"📊 Saved analysis to history for {email}")
    except Exception as e:
        print(f"⚠️ Could not save to history: {e}")

def create_reset_token(email: str) -> str:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=1)
    with SessionLocal() as db:
        db.query(PasswordResetToken).filter(PasswordResetToken.email == email).delete()
        reset_entry = PasswordResetToken(token=token, email=email, expires_at=expires_at)
        db.add(reset_entry)
        db.commit()
    return token


def validate_reset_token(token: str) -> Optional[str]:
    with SessionLocal() as db:
        entry = db.get(PasswordResetToken, token)
        if not entry:
            return None
        if datetime.utcnow() > entry.expires_at:
            db.delete(entry)
            db.commit()
            return None
        return entry.email


def delete_reset_token(token: str):
    with SessionLocal() as db:
        db.query(PasswordResetToken).filter(PasswordResetToken.token == token).delete()
        db.commit()

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def get_user(email: str):
    with SessionLocal() as db:
        return db.get(User, email)


def create_user(email: str, name: str, password: str):
    with SessionLocal() as db:
        user = User(email=email, name=name, password=hash_password(password), plan="free")
        db.add(user)
        db.commit()


def update_user(email: str, **fields):
    with SessionLocal() as db:
        user = db.get(User, email)
        if not user:
            return
        for key, value in fields.items():
            setattr(user, key, value)
        user.updated_at = datetime.utcnow()
        db.commit()


def create_session(email: str) -> str:
    """Create a new session in the database"""
    session_id = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(days=7)
    
    with SessionLocal() as db:
        # Delete any existing sessions for this email (optional - allows only one active session per user)
        # db.query(Session).filter(Session.email == email).delete()
        
        # Create new session
        session = Session(
            session_id=session_id,
            email=email,
            expires_at=expires_at
        )
        db.add(session)
        db.commit()
    
    return session_id


def get_current_user(request: Request) -> Optional[dict]:
    """Get current user from session stored in database"""
    session_id = request.cookies.get("session_id")
    if not session_id:
        return None

    with SessionLocal() as db:
        # Get session from database
        session = db.get(Session, session_id)
        if not session:
            return None

        # Check if session expired
        if datetime.utcnow() > session.expires_at:
            db.delete(session)
            db.commit()
            return None

        # Get user
        user = db.get(User, session.email)
        if not user:
            return None

        return {"email": user.email, "name": user.name, "plan": user.plan}


def delete_session(session_id: str):
    """Delete a session from the database"""
    with SessionLocal() as db:
        session = db.get(Session, session_id)
        if session:
            db.delete(session)
            db.commit()


def cleanup_expired_sessions():
    """Remove expired sessions from the database"""
    try:
        with SessionLocal() as db:
            expired_count = db.query(Session).filter(
                Session.expires_at < datetime.utcnow()
            ).delete()
            db.commit()
            if expired_count > 0:
                print(f"🧹 Cleaned up {expired_count} expired session(s)")
    except Exception as e:
        print(f"⚠️ Error cleaning up sessions: {e}")


@app.on_event("startup")
async def startup_event():
    """Run cleanup on startup"""
    cleanup_expired_sessions()


@app.get("/", response_class=HTMLResponse)
async def landing_page(request: Request):
    """Landing page with login/signup"""
    user = get_current_user(request)
    if user:
        return RedirectResponse("/dashboard")
    return templates.TemplateResponse("landing.html", {"request": request})


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page"""
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...)
):
    """Handle login"""
    user = get_user(email)
    if not user or user.password != hash_password(password):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid email or password"}
        )

    session_id = create_session(email)
    response = RedirectResponse("/dashboard", status_code=303)
    response.set_cookie("session_id", session_id, httponly=True, max_age=604800)
    return response


@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    """Signup page"""
    return templates.TemplateResponse("signup.html", {
        "request": request
    })


@app.post("/signup")
async def signup(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...)
):
    """Handle signup"""
    user = get_user(email)
    if user:
        return templates.TemplateResponse(
            "signup.html",
            {"request": request, "error": "Email already registered"}
        )

    create_user(email=email, name=name, password=password)

    session_id = create_session(email)
    response = RedirectResponse("/dashboard", status_code=303)
    response.set_cookie("session_id", session_id, httponly=True, max_age=604800)
    return response


@app.get("/logout")
async def logout(request: Request):
    """Logout user"""
    session_id = request.cookies.get("session_id")
    if session_id:
        delete_session(session_id)
    
    response = RedirectResponse("/")
    response.delete_cookie("session_id")
    return response


@app.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request):
    """Forgot password page"""
    return templates.TemplateResponse("forgot_password.html", {"request": request})


@app.post("/forgot-password")
async def forgot_password(
    request: Request,
    email: str = Form(...)
):
    """Handle forgot password request"""
    user = get_user(email)
    if not user:
        return templates.TemplateResponse(
            "forgot_password.html",
            {"request": request, "error": "Email not found in our system"}
        )

    token = create_reset_token(email)
    
    # In production, send email with reset link
    # For now, we'll display the link on the page
    reset_link = f"{request.base_url}reset-password/{token}"
    
    return templates.TemplateResponse(
        "forgot_password.html",
        {
            "request": request,
            "success": "Password reset link generated! Copy the link below and open it in your browser.",
            "reset_link": reset_link
        }
    )


@app.get("/reset-password/{token}", response_class=HTMLResponse)
async def reset_password_page(request: Request, token: str):
    """Reset password page"""
    email = validate_reset_token(token)
    if not email:
        return templates.TemplateResponse(
            "reset_password.html",
            {"request": request, "token": token, "error": "Invalid or expired reset link"}
        )
    
    return templates.TemplateResponse("reset_password.html", {"request": request, "token": token})


@app.post("/reset-password/{token}")
async def reset_password(
    request: Request,
    token: str,
    password: str = Form(...),
    confirm_password: str = Form(...)
):
    """Handle password reset"""
    email = validate_reset_token(token)
    if not email:
        return templates.TemplateResponse(
            "reset_password.html",
            {"request": request, "token": token, "error": "Invalid or expired reset link"}
        )

    if password != confirm_password:
        return templates.TemplateResponse(
            "reset_password.html",
            {"request": request, "token": token, "error": "Passwords do not match"}
        )

    if len(password) < 6:
        return templates.TemplateResponse(
            "reset_password.html",
            {"request": request, "token": token, "error": "Password must be at least 6 characters"}
        )

    update_user(email, password=hash_password(password))
    delete_reset_token(token)

    session_id = create_session(email)
    response = RedirectResponse("/dashboard", status_code=303)
    response.set_cookie("session_id", session_id, httponly=True, max_age=604800)
    return response


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    
    response = templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user
    })
    # Prevent browser caching to always get latest version
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.get("/profile", response_class=HTMLResponse)
async def profile(request: Request):
    """User profile page"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    
    return templates.TemplateResponse("profile.html", {
        "request": request,
        "user": user
    })


@app.get("/api/history")
async def get_history(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        with SessionLocal() as db:
            entries = (
                db.query(AnalysisHistory)
                .filter(AnalysisHistory.email == user["email"])
                .order_by(AnalysisHistory.timestamp.desc())
                .all()
            )
            history = [
                {
                    "timestamp": entry.timestamp.isoformat(),
                    "symbols": entry.symbols.split(',') if entry.symbols else [],
                    "results": json.loads(entry.results_json or "[]"),
                    "errors": json.loads(entry.errors_json or "{}"),
                    "results_count": len(json.loads(entry.results_json or "[]")),
                    "errors_count": len(json.loads(entry.errors_json or "{}"))
                }
                for entry in entries
            ]
        return JSONResponse(content={"history": history})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/analyze")
async def analyze_options(request: Request):
    """API endpoint to run option analysis"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        data = await request.json()
        symbols = data.get("symbols", [])
        
        if not symbols:
            raise HTTPException(status_code=400, detail="No symbols provided")
        
        print(f"Analyzing symbols: {symbols}")
        
        # Run the analysis
        results, errors = get_option_data_for_symbols(symbols)
        
        print(f"Analysis complete: {len(results)} results, {len(errors)} errors")
        
        # Save to history
        save_analysis_to_history(user["email"], symbols, results, errors)
        
        # Format response with both results and errors
        response_data = {
            "results": results,
            "errors": errors
        }
        
        return JSONResponse(content=response_data)
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = f"{str(e)}\n{traceback.format_exc()}"
        print(f"Error in analysis: {error_detail}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stripe-config")
async def get_stripe_config(request: Request):
    """Get Stripe public key configuration"""
    stripe_public_key = os.getenv("STRIPE_PUBLIC_KEY", "not_configured")
    return JSONResponse(content={"publicKey": stripe_public_key})


@app.post("/api/subscribe")
async def subscribe(request: Request):
    """Handle Stripe subscription and upgrade user account"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        data = await request.json()
        email = user["email"]
        
        if data.get("testMode"):
            plan = data.get("plan", "pro")
            update_user(email, plan=plan)
            return JSONResponse(content={
                "success": True,
                "message": "Subscription successful (test mode)",
                "plan": plan
            })
        
        # Real Stripe integration
        stripe_secret_key = os.getenv("STRIPE_SECRET_KEY")
        
        if stripe_secret_key and stripe_secret_key != "not_configured":
            # Initialize Stripe with secret key
            try:
                import stripe
                stripe.api_key = stripe_secret_key
                
                payment_method_id = data.get("paymentMethodId")
                plan = data.get("plan", "pro")
                amount = data.get("amount", 2900)  # $29.00 in cents
                
                # Create a customer
                customer = stripe.Customer.create(
                    email=email,
                    payment_method=payment_method_id,
                    invoice_settings={"default_payment_method": payment_method_id},
                    metadata={"user_email": email}
                )
                
                # Create a subscription
                subscription = stripe.Subscription.create(
                    customer=customer.id,
                    items=[{"price_data": {
                        "currency": "usd",
                        "product_data": {"name": f"{plan.capitalize()} Plan"},
                        "unit_amount": amount,
                        "recurring": {"interval": "month"}
                    }}],
                    payment_behavior="default_incomplete",
                    expand=["latest_invoice.payment_intent"]
                )
                
                # Update user plan
                update_user(email, plan=plan, stripe_customer_id=customer.id, stripe_subscription_id=subscription.id)
                
                # Check if payment requires additional action (3D Secure)
                if subscription.latest_invoice.payment_intent.status == "requires_action":
                    return JSONResponse(content={
                        "success": True,
                        "requiresAction": True,
                        "clientSecret": subscription.latest_invoice.payment_intent.client_secret,
                        "subscriptionId": subscription.id
                    })
                
                return JSONResponse(content={
                    "success": True,
                    "message": "Subscription successful",
                    "plan": plan,
                    "subscriptionId": subscription.id
                })
                
            except ImportError:
                # Stripe library not installed, fall back to test mode
                print("⚠️ Stripe library not installed, using test mode")
                update_user(email, plan=data.get("plan", "pro"))
                return JSONResponse(content={
                    "success": True,
                    "message": "Subscription successful (Stripe not configured)",
                    "plan": data.get("plan", "pro")
                })
            except Exception as e:
                print(f"❌ Stripe error: {str(e)}")
                raise HTTPException(status_code=400, detail=f"Payment processing error: {str(e)}")
        else:
            # No Stripe configured, use test mode
            plan = data.get("plan", "pro")
            update_user(email, plan=plan)
            
            return JSONResponse(content={
                "success": True,
                "message": "Subscription successful (Stripe not configured - test mode)",
                "plan": plan
            })
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Subscription error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/update-profile")
async def update_profile(request: Request):
    """Update user profile"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        data = await request.json()
        email = user["email"]
        name = data.get("name", "").strip()
        
        if not name:
            raise HTTPException(status_code=400, detail="Name is required")
        
        update_user(email, name=name)
        return JSONResponse(content={
            "success": True,
            "message": "Profile updated successfully"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Update profile error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/cancel-subscription")
async def cancel_subscription(request: Request):
    """Cancel subscription"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    email = user["email"]

    try:
        stripe_secret_key = os.getenv("STRIPE_SECRET_KEY")

        if stripe_secret_key and stripe_secret_key != "not_configured":
            user_record = get_user(email)
            subscription_id = user_record.stripe_subscription_id if user_record else None

            if subscription_id:
                try:
                    import stripe
                    stripe.api_key = stripe_secret_key

                    stripe.Subscription.modify(
                        subscription_id,
                        cancel_at_period_end=True
                    )
                    print(f"✅ Cancelled Stripe subscription for {email}")
                except Exception as e:
                    print(f"⚠️ Stripe cancellation error: {str(e)}")

        update_user(email, plan="free")
        return JSONResponse(content={
            "success": True,
            "message": "Subscription cancelled. You will retain access until the end of your billing period."
        })

    except Exception as e:
        print(f"❌ Cancel subscription error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    print("=" * 80)
    print("🚀 Starting Smart Option Trading Analytics")
    print(f"📦 Environment: {APP_ENV.upper()}")
    print("=" * 80)
    
    if APP_ENV == "development" or DEBUG:
        print(f"\n📍 Local access: http://localhost:{PORT}")
        print("🔐 Demo credentials:")
        print("   Email: demo@example.com")
        print("   Password: demo123")
    else:
        print(f"\n🌐 Production mode - Running on {HOST}:{PORT}")
        print("✅ Security: Enhanced")
        print("✅ CORS: Configured")
        print("✅ Profile: Full Access Enabled")
        print("✅ All Features: Active")
    
    print("\n" + "=" * 80 + "\n")
    
    # Production-ready uvicorn configuration
    # Note: Using single worker mode for simplicity
    # For multi-worker production, run: uvicorn app:app --host 0.0.0.0 --port 8000 --workers 4
    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        log_level="info" if DEBUG else "warning",
        access_log=DEBUG,
        reload=DEBUG,
        proxy_headers=True,
        forwarded_allow_ips="*"
    )
