# 💳 Stripe Payment Gateway Setup Guide

## Overview

The payment gateway is now **fully implemented** with Stripe integration. It works in two modes:

1. **Test Mode** (Default) - Works without Stripe configuration, uses test cards
2. **Production Mode** - Full Stripe integration with real payments

---

## 🎯 Quick Start (Test Mode)

**Test mode is enabled by default** - No configuration needed!

1. Go to your profile page: `/profile`
2. Click "Upgrade to Pro"
3. Use test card: `4242 4242 4242 4242`
4. Expiry: Any future date (e.g., `12/25`)
5. CVC: Any 3 digits (e.g., `123`)
6. Click "Subscribe Now"

✅ Your account will be upgraded instantly!

---

## 🚀 Production Setup (Real Payments)

### Step 1: Create Stripe Account

1. Go to [https://stripe.com](https://stripe.com)
2. Click "Start now" to create account
3. Complete verification process
4. Activate your account

### Step 2: Get API Keys

1. Login to [Stripe Dashboard](https://dashboard.stripe.com)
2. Go to **Developers** → **API keys**
3. You'll see two keys:
   - **Publishable key** (starts with `pk_test_` or `pk_live_`)
   - **Secret key** (starts with `sk_test_` or `sk_live_`)

**For Testing:**
- Use **Test mode** keys (toggle in top right)
- `pk_test_...` and `sk_test_...`

**For Production:**
- Use **Live mode** keys
- `pk_live_...` and `sk_live_...`

### Step 3: Configure Environment Variables

Create or edit your `.env` file:

```env
# Stripe Configuration
STRIPE_PUBLIC_KEY=pk_test_51xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
STRIPE_SECRET_KEY=sk_test_51xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Or set in environment:**

**Windows:**
```batch
set STRIPE_PUBLIC_KEY=pk_test_51xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
set STRIPE_SECRET_KEY=sk_test_51xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Linux/Mac:**
```bash
export STRIPE_PUBLIC_KEY=pk_test_51xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
export STRIPE_SECRET_KEY=sk_test_51xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### Step 4: Install Stripe Library

```bash
pip install stripe
```

### Step 5: Restart Application

```bash
python start.py
```

---

## 💡 How It Works

### Test Mode (No Stripe Keys)
- Uses manual card input
- Validates test card (4242 4242 4242 4242)
- Instant account upgrade
- No real payment processing
- Perfect for development and demos

### Production Mode (With Stripe Keys)
- Uses Stripe Elements (secure card form)
- Real payment processing
- Creates Stripe customer
- Creates subscription
- Handles 3D Secure authentication
- Stores subscription ID
- Full cancellation support

---

## 🧪 Testing Stripe Integration

### Test Cards (Stripe Test Mode)

**Success:**
- `4242 4242 4242 4242` - Basic card
- `4000 0025 0000 3155` - Requires 3D Secure

**Failure:**
- `4000 0000 0000 0002` - Card declined
- `4000 0000 0000 9995` - Insufficient funds

**International:**
- `4000 0003 6000 0006` - Brazil card
- `4000 0076 4000 0016` - India card

[Full test card list](https://stripe.com/docs/testing#cards)

### Testing Flow

1. **Upgrade to Pro:**
   - Go to `/profile`
   - Click "Upgrade to Pro - $29/month"
   - Payment modal opens

2. **Test Mode (no keys):**
   - See: "Demo Mode - Use test card: 4242 4242 4242 4242"
   - Enter test card details
   - Click "Subscribe Now"
   - Account upgraded ✅

3. **Production Mode (with keys):**
   - See Stripe's secure card form
   - Enter real or test card
   - Click "Subscribe Now"
   - Stripe processes payment
   - Account upgraded ✅

---

## 🔧 API Endpoints

### Get Stripe Config
```
GET /api/stripe-config
```
Returns:
```json
{
  "publicKey": "pk_test_xxx..."
}
```

### Subscribe
```
POST /api/subscribe
```

**Test Mode:**
```json
{
  "testMode": true,
  "plan": "pro",
  "cardNumber": "4242"
}
```

**Production Mode:**
```json
{
  "paymentMethodId": "pm_xxx...",
  "plan": "pro",
  "amount": 2900
}
```

### Cancel Subscription
```
POST /api/cancel-subscription
```
Returns:
```json
{
  "success": true,
  "message": "Subscription cancelled..."
}
```

---

## 💰 Pricing Configuration

Current pricing in `templates/profile.html`:

```javascript
amount: 2900  // $29.00 in cents
```

**To change pricing:**

1. Update modal display:
```html
<span class="text-2xl font-bold">$29<span class="text-sm">...</span></span>
```

2. Update payment amount:
```javascript
amount: 2900  // Change this (in cents)
```

3. Update button text:
```html
Subscribe Now - $29/month
```

---

## 🔒 Security Features

### Built-in Security:
- ✅ Stripe Elements (PCI compliant)
- ✅ No card data touches your server
- ✅ Secure token exchange
- ✅ 3D Secure support
- ✅ Fraud detection (Stripe Radar)
- ✅ HTTPS recommended

### Best Practices:
- Never log card details
- Store only Stripe IDs
- Use webhooks for subscription updates
- Validate on server-side
- Keep API keys secret

---

## 📊 Subscription Management

### User Upgrade Flow:
1. User clicks "Upgrade to Pro"
2. Payment modal opens
3. Card details entered (Stripe Elements or test)
4. Payment processed
5. Stripe customer created
6. Subscription created
7. User plan updated to "pro"
8. Success notification shown
9. Page reloads with Pro features

### Cancellation Flow:
1. User clicks "Cancel Subscription"
2. Confirmation dialog
3. Stripe subscription cancelled (at period end)
4. User plan downgraded to "free"
5. Access retained until period end
6. Success message shown

### Data Stored:
```python
users_db[email] = {
    "plan": "pro",
    "stripe_customer_id": "cus_xxx...",
    "stripe_subscription_id": "sub_xxx..."
}
```

---

## 🌐 Webhook Setup (Advanced)

For production, set up webhooks to handle:
- Subscription updates
- Payment failures
- Cancellations
- Renewals

### 1. Create Webhook Endpoint

In `app.py`:
```python
@app.post("/api/stripe-webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, WEBHOOK_SECRET
        )
        
        # Handle event types
        if event['type'] == 'customer.subscription.updated':
            # Update user subscription
            pass
        
        return JSONResponse({"status": "success"})
    except Exception as e:
        raise HTTPException(status_code=400)
```

### 2. Configure in Stripe Dashboard
1. Go to **Developers** → **Webhooks**
2. Add endpoint: `https://yourdomain.com/api/stripe-webhook`
3. Select events to listen for
4. Copy webhook secret to `.env`

---

## 🐛 Troubleshooting

### Issue: "Stripe not configured - Using test mode"
**Solution:** Add STRIPE_PUBLIC_KEY to environment variables

### Issue: "Payment failed"
**Solution:** 
- Check Stripe API keys are correct
- Verify Stripe library is installed: `pip install stripe`
- Check Stripe dashboard for error details

### Issue: "Module stripe not found"
**Solution:**
```bash
pip install stripe
```

### Issue: "Invalid API key"
**Solution:**
- Verify keys match test/live mode
- Check for extra spaces in .env file
- Regenerate keys in Stripe dashboard

### Issue: Test card not working
**Solution:**
- Use exactly: `4242 4242 4242 4242`
- Expiry must be future date
- CVC any 3 digits
- Make sure in test mode

---

## 📈 Monitoring Payments

### Stripe Dashboard
- View all transactions
- See customer details
- Track subscriptions
- Handle disputes
- Export data
- View analytics

### Application Logs
```
✅ Test mode: Upgraded user@email.com to pro plan
✅ Real Stripe: Created subscription for user@email.com
✅ Cancelled Stripe subscription for user@email.com
```

---

## 🎨 Customization

### Change Plan Names:
Edit `templates/profile.html`:
```html
<h3 class="text-3xl font-bold">Pro</h3>
```

### Change Features:
```html
<div class="flex items-center">
    <i class="fas fa-check text-green-500 mr-3"></i>
    <span>Your feature here</span>
</div>
```

### Change Success Message:
```javascript
notification.innerHTML = `
    <div class="font-bold text-lg">Your message! 🎉</div>
`;
```

---

## ✅ Checklist

### For Testing:
- [ ] Test mode works without Stripe keys
- [ ] Test card (4242...) processes successfully
- [ ] User plan upgrades to "pro"
- [ ] Success notification appears
- [ ] Profile shows Pro status
- [ ] Cancellation works

### For Production:
- [ ] Stripe account created and verified
- [ ] API keys added to environment
- [ ] Stripe library installed
- [ ] HTTPS enabled
- [ ] Webhook configured (optional)
- [ ] Test with real test card
- [ ] Monitor Stripe dashboard
- [ ] Set up email notifications (optional)

---

## 📚 Resources

- [Stripe Documentation](https://stripe.com/docs)
- [Stripe API Reference](https://stripe.com/docs/api)
- [Test Cards](https://stripe.com/docs/testing)
- [Stripe Elements](https://stripe.com/docs/stripe-js)
- [Webhooks Guide](https://stripe.com/docs/webhooks)
- [Security Best Practices](https://stripe.com/docs/security)

---

## 🎉 Summary

Your payment gateway is **fully implemented** and ready to use!

**Default Behavior:**
- ✅ Works out of the box (test mode)
- ✅ No configuration required for testing
- ✅ Seamless upgrade flow
- ✅ Proper error handling
- ✅ Beautiful UI with animations

**With Stripe Configuration:**
- ✅ Real payment processing
- ✅ Secure card handling
- ✅ 3D Secure support
- ✅ Subscription management
- ✅ Production-ready

**Test it now:**
1. Go to `/profile`
2. Click "Upgrade to Pro"
3. Use card: `4242 4242 4242 4242`
4. Enjoy! 🚀

---

*Payment processing secured by Stripe*

