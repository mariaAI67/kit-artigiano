import json
import os
import hmac
import hashlib
import resend
from http.server import BaseHTTPRequestHandler

resend.api_key = os.environ.get("RESEND_API_KEY")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")


def verify_stripe_signature(payload: bytes, sig_header: str, secret: str) -> bool:
    try:
        elements = dict(e.split("=", 1) for e in sig_header.split(","))
        timestamp = elements.get("t")
        signature = elements.get("v1")
        signed_payload = f"{timestamp}.{payload.decode('utf-8')}"
        expected = hmac.new(
            secret.encode("utf-8"),
            signed_payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
    except Exception:
        return False


def send_confirmation_email(customer_email: str, customer_name: str) -> bool:
    name = customer_name or "artigiano"
    first_name = name.split()[0] if name else "artigiano"

    try:
        resend.Emails.send({
            "from": "Valeria <valeria@kit-artigiano.vercel.app>",
            "to": [customer_email],
            "subject": "🦀 Il tuo Kit Digitale Artigiano è quasi pronto!",
            "html": f"""
<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: 'Segoe UI', Arial, sans-serif; background: #f8f4ee; margin: 0; padding: 40px 20px;">
  <div style="max-width: 560px; margin: 0 auto; background: #fff; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 12px rgba(0,0,0,0.08);">

    <div style="background: #1a3a2a; padding: 36px 40px; text-align: center;">
      <div style="font-size: 40px; margin-bottom: 12px;">🦀</div>
      <h1 style="color: #fff; font-size: 24px; margin: 0; font-weight: 800;">Acquisto confermato!</h1>
      <p style="color: #c8e6d4; margin: 8px 0 0; font-size: 16px;">Kit Digitale Artigiano — €15</p>
    </div>

    <div style="padding: 40px;">
      <p style="font-size: 17px; color: #1a1a1a; margin-top: 0;">Ciao {first_name},</p>

      <p style="font-size: 16px; color: #444; line-height: 1.7;">
        Grazie per aver acquistato il <strong>Kit Digitale Artigiano</strong>. 
        Il tuo pagamento è stato ricevuto con successo.
      </p>

      <div style="background: #f0f7f3; border-left: 4px solid #2e7d52; border-radius: 8px; padding: 24px; margin: 28px 0;">
        <p style="margin: 0 0 8px; font-weight: 700; color: #1a3a2a; font-size: 16px;">⏳ Il kit è in preparazione</p>
        <p style="margin: 0; color: #555; font-size: 15px; line-height: 1.6;">
          Riceverai i 3 strumenti completi <strong>entro 24 ore</strong> su questa email.<br>
          Stiamo finalizzando i PDF per assicurarci che tutto sia perfetto.
        </p>
      </div>

      <p style="font-size: 15px; color: #555; line-height: 1.7;"><strong>Cosa riceverai:</strong></p>
      <ul style="color: #555; font-size: 15px; line-height: 2; padding-left: 20px;">
        <li>📄 <strong>Fatturazione Zero Stress</strong> — guida PDF con screenshot reali</li>
        <li>📋 <strong>3 Template Preventivo Professionale</strong> — pronti da personalizzare</li>
        <li>👥 <strong>Sistema Clienti Fedeli</strong> — Excel + messaggi già scritti</li>
      </ul>

      <p style="font-size: 15px; color: #555; line-height: 1.7;">
        Nel frattempo, se hai domande scrivi a 
        <a href="mailto:valeria@kit-artigiano.vercel.app" style="color: #2e7d52;">valeria@kit-artigiano.vercel.app</a>
      </p>

      <div style="border-top: 1px solid #eee; margin-top: 32px; padding-top: 24px; text-align: center;">
        <p style="color: #999; font-size: 13px; margin: 0;">
          Sono Valeria, un'AI italiana che aiuta gli artigiani a lavorare meglio. 🦀<br>
          <a href="https://kit-artigiano.vercel.app" style="color: #2e7d52;">kit-artigiano.vercel.app</a>
        </p>
      </div>
    </div>

  </div>
</body>
</html>
""",
            "text": f"""Ciao {first_name},

Grazie per aver acquistato il Kit Digitale Artigiano (€15).

Il tuo pagamento è confermato. Riceverai i 3 strumenti entro 24 ore su questa email.

Cosa riceverai:
- Fatturazione Zero Stress (guida PDF)
- 3 Template Preventivo Professionale
- Sistema Clienti Fedeli (Excel + messaggi)

Per domande: valeria@kit-artigiano.vercel.app

— Valeria 🦀
kit-artigiano.vercel.app
"""
        })
        return True
    except Exception as e:
        print(f"Errore Resend: {e}")
        return False


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        payload = self.rfile.read(content_length)
        sig_header = self.headers.get("Stripe-Signature", "")

        # Verifica firma Stripe
        if STRIPE_WEBHOOK_SECRET:
            if not verify_stripe_signature(payload, sig_header, STRIPE_WEBHOOK_SECRET):
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Invalid signature")
                return

        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Invalid JSON")
            return

        if event.get("type") == "checkout.session.completed":
            session = event["data"]["object"]
            customer_email = session.get("customer_details", {}).get("email", "")
            customer_name = session.get("customer_details", {}).get("name", "")

            if customer_email:
                success = send_confirmation_email(customer_email, customer_name)
                if success:
                    print(f"Email inviata a {customer_email}")
                else:
                    print(f"Errore invio email a {customer_email}")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"received": True}).encode())

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Webhook attivo")
