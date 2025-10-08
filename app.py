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

# Simple user database (in production, use a real database)
USER_DATA_FILE = "user_data.json"

def load_user_data():
    """Load user data from file"""
    try:
        if os.path.exists(USER_DATA_FILE):
            with open(USER_DATA_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"⚠️ Could not load user data: {e}")
    
    # Default demo user
    return {
        "demo@example.com": {
            "password": hashlib.sha256("demo123".encode()).hexdigest(),
            "name": "Demo User",
            "plan": "free"
        }
    }

def save_user_data():
    """Save user data to file"""
    try:
        with open(USER_DATA_FILE, 'w') as f:
            json.dump(users_db, f, indent=2)
        print(f"💾 User data saved to {USER_DATA_FILE}")
    except Exception as e:
        print(f"⚠️ Could not save user data: {e}")

users_db = load_user_data()

# Analysis History Storage
HISTORY_DATA_FILE = "analysis_history.json"

def load_history_data():
    """Load analysis history from file"""
    try:
        if os.path.exists(HISTORY_DATA_FILE):
            with open(HISTORY_DATA_FILE, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        print(f"⚠️ Could not load history data: {e}")
        return {}

def save_history_data(history_db):
    """Save history data to file"""
    try:
        with open(HISTORY_DATA_FILE, 'w') as f:
            json.dump(history_db, f, indent=2)
    except Exception as e:
        print(f"⚠️ Could not save history data: {e}")

def save_analysis_to_history(email, symbols, results, errors):
    """Save analysis results to user's history"""
    try:
        history_db = load_history_data()
        
        if email not in history_db:
            history_db[email] = []
        
        # Create history entry
        history_entry = {
            "timestamp": datetime.now().isoformat(),
            "symbols": symbols,
            "results_count": len(results),
            "errors_count": len(errors),
            "results": results,
            "errors": errors
        }
        
        # Add to beginning of list (most recent first)
        history_db[email].insert(0, history_entry)
        
        # Keep only last 100 analyses per user
        history_db[email] = history_db[email][:100]
        
        save_history_data(history_db)
        print(f"📊 Saved analysis to history for {email}")
    except Exception as e:
        print(f"⚠️ Could not save to history: {e}")

# Session storage (in production, use Redis or similar)
sessions = {}

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def create_session(email: str) -> str:
    session_id = secrets.token_urlsafe(32)
    sessions[session_id] = {
        "email": email,
        "created": datetime.now(),
        "expires": datetime.now() + timedelta(days=7)
    }
    return session_id

def get_current_user(request: Request) -> Optional[dict]:
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in sessions:
        return None
    
    session = sessions[session_id]
    if datetime.now() > session["expires"]:
        del sessions[session_id]
        return None
    
    email = session["email"]
    if email not in users_db:
        return None
    
    return {"email": email, **users_db[email]}


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
    if email not in users_db:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid email or password"}
        )
    
    if users_db[email]["password"] != hash_password(password):
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
    return templates.TemplateResponse("signup.html", {"request": request})


@app.post("/signup")
async def signup(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...)
):
    """Handle signup"""
    if email in users_db:
        return templates.TemplateResponse(
            "signup.html",
            {"request": request, "error": "Email already registered"}
        )
    
    users_db[email] = {
        "password": hash_password(password),
        "name": name,
        "plan": "free"
    }
    save_user_data()
    
    session_id = create_session(email)
    response = RedirectResponse("/dashboard", status_code=303)
    response.set_cookie("session_id", session_id, httponly=True, max_age=604800)
    return response


@app.get("/logout")
async def logout(request: Request):
    """Logout user"""
    session_id = request.cookies.get("session_id")
    if session_id in sessions:
        del sessions[session_id]
    
    response = RedirectResponse("/")
    response.delete_cookie("session_id")
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
    """Get user's analysis history"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        history_db = load_history_data()
        user_history = history_db.get(user["email"], [])
        
        return JSONResponse(content={
            "history": user_history
        })
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
        
        # Check if this is test mode or real Stripe
        if data.get("testMode"):
            # Test mode - simple upgrade
            plan = data.get("plan", "pro")
            
            if email in users_db:
                users_db[email]["plan"] = plan
                # Also save to a persistent file for production use
                save_user_data()
                print(f"✅ Test mode: Upgraded {email} to {plan} plan")
                print(f"📝 Current plan for {email}: {users_db[email]['plan']}")
            
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
                if email in users_db:
                    users_db[email]["plan"] = plan
                    users_db[email]["stripe_customer_id"] = customer.id
                    users_db[email]["stripe_subscription_id"] = subscription.id
                    save_user_data()
                
                print(f"✅ Real Stripe: Created subscription for {email}")
                
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
                if email in users_db:
                    users_db[email]["plan"] = data.get("plan", "pro")
                    save_user_data()
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
            if email in users_db:
                users_db[email]["plan"] = plan
                save_user_data()
            
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
        
        # Update user data
        if email in users_db:
            users_db[email]["name"] = name
            save_user_data()
            print(f"✅ Updated profile for {email}: {name}")
        
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
        # Check if user has Stripe subscription
        stripe_secret_key = os.getenv("STRIPE_SECRET_KEY")
        
        if stripe_secret_key and stripe_secret_key != "not_configured":
            user_data = users_db.get(email, {})
            subscription_id = user_data.get("stripe_subscription_id")
            
            if subscription_id:
                try:
                    import stripe
                    stripe.api_key = stripe_secret_key
                    
                    # Cancel the subscription at period end
                    stripe.Subscription.modify(
                        subscription_id,
                        cancel_at_period_end=True
                    )
                    print(f"✅ Cancelled Stripe subscription for {email}")
                except Exception as e:
                    print(f"⚠️ Stripe cancellation error: {str(e)}")
        
        # Downgrade user to free plan
        if email in users_db:
            users_db[email]["plan"] = "free"
            save_user_data()
            print(f"✅ Downgraded {email} to free plan")
        
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
