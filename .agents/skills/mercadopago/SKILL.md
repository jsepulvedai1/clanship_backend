---
name: mercadopago
description: |
  Comprehensive integration guide and toolset for Mercado Pago (Chile / Latin America).
  Use when designing, implementing, testing, or debugging Mercado Pago payments in Django / Python backends,
  Flutter mobile apps, or web frontends. Covers Checkout Pro, Checkout API/Bricks, WebPay Chile (CLP),
  Webhook listeners, sandbox test flows, and interacting with the Mercado Pago MCP Server tools.
license: Apache-2.0
metadata:
  version: v1
  publisher: clanship
---

# Mercado Pago Integration Guide & MCP Toolset

This skill provides complete reference, best practices, and integration workflows for **Mercado Pago** with focus on **Chile (`MLC` / CLP)** across the Clanship ecosystem (Django Backend + Flutter Clients).

---

## 1. Environment & Credentials

### Active Test Credentials (Sandbox)
* **Country / Site**: Chile (`MLC`) — Currency: `CLP` (Pesos Chilenos)
* **Application ID**: `7380703821527282`
* **User ID**: `3784328780`
* **Public Key**: `APP_USR-7c1fce11-fe20-4e12-8350-53c5c519c64e`
* **Access Token**: `APP_USR-7380703821527282-102115-e7b79ef670baa5a2da1aea4e851af134-3784328780`
* **Test Payer User**: `TESTUSER1792065942059288300`

> [!IMPORTANT]
> In production, replace test keys with production credentials (`APP_USR-...`) in `.env` and configure production Webhook endpoints with HTTPS.

---

## 2. Mercado Pago MCP Server Tools

Antigravity is configured with the official Mercado Pago MCP server. You can execute these tools or guide the user:

| MCP Tool | Description |
| :--- | :--- |
| `search_documentation` | Query official technical documentation, guides, and error codes. |
| `create_test_user` | Create sandbox buyer/seller accounts with preloaded balances. |
| `add_money_test_user` | Deposit funds into a test user account for payment simulations. |
| `application_list` | List available applications and details. |
| `get_credentials` | Fetch application keys securely. |
| `save_webhook` | Configure webhook endpoints for notifications. |
| `notifications_history` | Inspect webhook delivery logs and debug connection failures. |
| `quality_checklist` | View requirements for approval and homologation. |
| `quality_evaluation` | Audit a recent test payment (`payment_id`) against Mercado Pago standards. |

---

## 3. Django Backend Architecture (`backend-clanship`)

### Installation
```bash
pip install mercadopago
```

### Preference Creation (Checkout Pro)
```python
import mercadopago
from django.conf import settings

def create_job_payment_preference(job, back_url_base="https://clanship.cl"):
    sdk = mercadopago.SDK(settings.MERCADOPAGO_ACCESS_TOKEN)

    preference_data = {
        "items": [
            {
                "id": str(job.id),
                "title": f"Servicio Clanship: {job.title}",
                "quantity": 1,
                "currency_id": "CLP",
                "unit_price": float(job.price),
            }
        ],
        "payer": {
            "name": job.client.first_name,
            "surname": job.client.last_name,
            "email": job.client.email,
        },
        "back_urls": {
            "success": f"{back_url_base}/payments/success",
            "failure": f"{back_url_base}/payments/failure",
            "pending": f"{back_url_base}/payments/pending",
        },
        "auto_return": "approved",
        "external_reference": str(job.id),
        "notification_url": f"{settings.BACKEND_API_URL}/api/payments/webhook/mercadopago/",
    }

    preference_response = sdk.preference().create(preference_data)
    preference = preference_response["response"]
    
    # Return init_point (production) or sandbox_init_point (development)
    init_point = (
        preference["sandbox_init_point"] 
        if settings.DEBUG 
        else preference["init_point"]
    )
    return {
        "preference_id": preference["id"],
        "init_point": init_point,
    }
```

### Webhook / IPN Handler
Mercado Pago sends POST requests to `notification_url` with query parameters or JSON body:
```python
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import mercadopago
from django.conf import settings

class MercadoPagoWebhookView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, *args, **kwargs):
        topic = request.data.get("type") or request.query_params.get("topic")
        data_id = request.data.get("data", {}).get("id") or request.query_params.get("id")

        if topic == "payment" and data_id:
            sdk = mercadopago.SDK(settings.MERCADOPAGO_ACCESS_TOKEN)
            payment_info = sdk.payment().get(data_id)
            
            if payment_info["status"] == 200:
                payment_data = payment_info["response"]
                payment_status = payment_data.get("status") # 'approved', 'pending', 'rejected'
                external_ref = payment_data.get("external_reference") # Job ID
                
                if payment_status == "approved":
                    # Mark Job / Trip as paid
                    pass

        return Response(status=status.HTTP_200_OK)
```

---

## 4. Flutter Mobile Client (`clanshi-mobile-client`)

In Flutter, Checkout Pro is initiated by launching `init_point` using `url_launcher` or an `InAppWebView`:

```dart
import 'package:url_launcher/url_launcher.dart';

Future<void> launchMercadoPagoCheckout(String initPointUrl) async {
  final Uri uri = Uri.parse(initPointUrl);
  if (await canLaunchUrl(uri)) {
    await launchUrl(
      uri,
      mode: LaunchMode.externalApplication, // or inAppWebView
    );
  } else {
    throw 'Could not launch $initPointUrl';
  }
}
```

### Deep Linking Return URL
Configure App Links / URL Scheme (e.g. `clanship://payments/success`) so the user returns smoothly into the Flutter app once the transaction completes.

---

## 5. Chilean Peculiarities & Tips
* **WebPay**: Chilean cards (Redcompra / Transbank / BancoEstado) require `CLP` currency.
* **Amounts**: Chilean Pesos do not use decimals (`15000` not `15000.00`).
* **Homologation**: Run the `quality_checklist` and `quality_evaluation` tools after running a test payment to get integration approval.
