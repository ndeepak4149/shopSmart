from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from config import get_settings

router = APIRouter()


class AlertRequest(BaseModel):
    email: str
    target_price: float
    product_title: str
    current_price: float
    seller: str


@router.post("/alerts")
async def create_price_alert(req: AlertRequest):
    settings = get_settings()

    if not settings.resend_api_key:
        raise HTTPException(status_code=503, detail="Email alerts not configured")

    try:
        import resend
        resend.api_key = settings.resend_api_key

        short_title = req.product_title[:60] + ("…" if len(req.product_title) > 60 else "")
        savings = req.current_price - req.target_price

        resend.Emails.send({
            "from": "ShopSmart <alerts@shopsmart.app>",
            "to": [req.email],
            "subject": f"Alert set: {short_title}",
            "html": f"""
            <div style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:24px">
              <h2 style="color:#4f46e5">Price Alert Confirmed ✓</h2>
              <p>We'll email you when <strong>{req.product_title}</strong> drops below
                 <strong style="color:#16a34a">${req.target_price:.2f}</strong>.</p>
              <table style="width:100%;border-collapse:collapse;margin:16px 0">
                <tr>
                  <td style="padding:8px 0;color:#64748b">Current price</td>
                  <td style="padding:8px 0;font-weight:600">${req.current_price:.2f} at {req.seller}</td>
                </tr>
                <tr>
                  <td style="padding:8px 0;color:#64748b">You save when triggered</td>
                  <td style="padding:8px 0;font-weight:600;color:#16a34a">${savings:.2f}</td>
                </tr>
              </table>
              <p style="color:#94a3b8;font-size:12px">ShopSmart · We only email you when your target price is hit.</p>
            </div>
            """,
        })

        # store the alert in Supabase so we can check it later (non-blocking)
        try:
            from services.database import get_db
            get_db().table("price_alerts").insert({
                "email": req.email,
                "product_title": req.product_title[:200],
                "seller": req.seller,
                "current_price": req.current_price,
                "target_price": req.target_price,
            }).execute()
        except Exception as db_err:
            print(f"[Alerts] Supabase insert failed (non-fatal): {db_err}")

        return {"status": "ok"}

    except Exception as e:
        print(f"[Alerts] Resend failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to send confirmation email")
