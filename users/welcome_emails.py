import html
import logging
import re
import threading
from datetime import datetime
from typing import Any, Dict, Optional

from django.conf import settings

logger = logging.getLogger(__name__)

AVAILABLE_WELCOME_VARIABLES = [
    {"key": "first_name", "token": "{first_name}", "label": "Nombre", "sample": "Carlos"},
    {"key": "last_name", "token": "{last_name}", "label": "Apellido", "sample": "González"},
    {"key": "full_name", "token": "{full_name}", "label": "Nombre completo", "sample": "Carlos González"},
    {"key": "email", "token": "{email}", "label": "Correo electrónico", "sample": "carlos@ejemplo.cl"},
    {"key": "phone_number", "token": "{phone_number}", "label": "Teléfono", "sample": "+56912345678"},
    {"key": "user_type", "token": "{user_type}", "label": "Tipo de cuenta", "sample": "Cliente"},
    {"key": "support_email", "token": "{support_email}", "label": "Correo de soporte", "sample": "soporte@clanship.cl"},
    {"key": "year", "token": "{year}", "label": "Año actual", "sample": str(datetime.now().year)},
]

_HTML_TAG_PATTERN = re.compile(r"<(p|div|ul|ol|li|table|h[1-6]|br|section|article|blockquote)\b", re.IGNORECASE)
_HEX_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{3,8}$")


def _sanitize_color(value: Optional[str], fallback: str) -> str:
    candidate = (value or "").strip()
    if _HEX_COLOR_PATTERN.match(candidate):
        return candidate
    return fallback


def _sanitize_url(value: Optional[str], fallback: str = "https://clanship.cl") -> str:
    candidate = (value or "").strip()
    if candidate.startswith(("https://", "http://", "mailto:")):
        return candidate
    return fallback


def _substitute_vars(text: str, context: Dict[str, Any], escape_values: bool = False) -> str:
    if not text:
        return ""
    result = str(text)
    for key, val in context.items():
        str_val = "" if val is None else str(val)
        if escape_values:
            str_val = html.escape(str_val, quote=True)
        result = result.replace(f"{{{key}}}", str_val)
    return result


def _strip_html(raw_html: str) -> str:
    if not raw_html:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", raw_html, flags=re.IGNORECASE)
    text = re.sub(r"</(p|div|li|h[1-6]|tr)>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<li[^>]*>", "• ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _normalize_body_html(body: str) -> str:
    content = (body or "").strip()
    if not content:
        return ""
    if _HTML_TAG_PATTERN.search(content):
        return content
    paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
    return "".join(
        f'<p style="margin:0 0 14px 0;">{p.replace(chr(10), "<br/>")}</p>'
        for p in paragraphs
    )


def build_welcome_context(user) -> Dict[str, str]:
    is_professional = getattr(user, "user_type", "") == "PROFESSIONAL"
    role_label = "Maestro" if is_professional else "Cliente"
    raw_first = (getattr(user, "first_name", "") or "").strip()
    raw_last = (getattr(user, "last_name", "") or "").strip()

    first_name = raw_first.title() if raw_first else role_label
    last_name = raw_last.title() if raw_last else ""
    full_name = f"{raw_first} {raw_last}".strip().title() if (raw_first or raw_last) else role_label
    email = (getattr(user, "email", "") or "").strip()
    phone_number = (getattr(user, "phone_number", "") or "").strip() or "No registrado"
    support_email = getattr(settings, "SUPPORT_EMAIL", "soporte@clanship.cl")

    return {
        "first_name": first_name,
        "last_name": last_name,
        "full_name": full_name,
        "email": email,
        "phone_number": phone_number,
        "user_type": role_label,
        "support_email": support_email,
        "year": str(datetime.now().year),
    }


def build_sample_context(user_type: str) -> Dict[str, str]:
    is_prof = str(user_type).upper() == "PROFESSIONAL"
    support_email = getattr(settings, "SUPPORT_EMAIL", "soporte@clanship.cl")
    if is_prof:
        return {
            "first_name": "Matías",
            "last_name": "Rojas",
            "full_name": "Matías Rojas",
            "email": "matias.maestro@ejemplo.cl",
            "phone_number": "+56987654321",
            "user_type": "Maestro",
            "support_email": support_email,
            "year": str(datetime.now().year),
        }
    return {
        "first_name": "Camila",
        "last_name": "Fuentes",
        "full_name": "Camila Fuentes",
        "email": "camila.cliente@ejemplo.cl",
        "phone_number": "+56912345678",
        "user_type": "Cliente",
        "support_email": support_email,
        "year": str(datetime.now().year),
    }


def render_welcome_email(template, context: Dict[str, str]) -> Dict[str, Any]:
    """
    Renderiza asunto, remitente, HTML completo y texto plano a partir de una plantilla
    (puede ser una instancia de WelcomeEmailTemplate o un objeto/dict simple para vista previa).
    """
    def get_val(attr: str, default: str = "") -> Any:
        if isinstance(template, dict):
            return template.get(attr, default)
        return getattr(template, attr, default)

    sender_name = (get_val("sender_name", "Equipo Clanship") or "Equipo Clanship").strip()
    sender_name = sender_name.replace("<", "").replace(">", "").strip() or "Equipo Clanship"
    no_reply_addr = getattr(settings, "NO_REPLY_EMAIL_USER", "noreply@clanship.cl")
    from_email = f"{sender_name} <{no_reply_addr}>"

    reply_to = (get_val("reply_to", "") or "").strip()
    subject = _substitute_vars(get_val("subject", "Bienvenido a Clanship"), context, escape_values=False)

    use_raw_html = bool(get_val("use_raw_html", False))
    raw_html_tpl = (get_val("raw_html", "") or "").strip()

    if use_raw_html and raw_html_tpl:
        rendered_html = _substitute_vars(raw_html_tpl, context, escape_values=True)
        custom_text = (get_val("body_text", "") or "").strip()
        rendered_text = (
            _substitute_vars(custom_text, context, escape_values=False)
            if custom_text
            else _strip_html(rendered_html)
        )
        return {
            "subject": subject,
            "from_email": from_email,
            "reply_to": reply_to,
            "html": rendered_html,
            "text": rendered_text,
        }

    header_bg = _sanitize_color(get_val("header_bg_color", "#0D2B45"), "#0D2B45")
    accent = _sanitize_color(get_val("accent_color", "#5D87FF"), "#5D87FF")

    preheader = _substitute_vars(get_val("preheader", ""), context, escape_values=True)
    header_badge = _substitute_vars(get_val("header_badge", ""), context, escape_values=True)
    header_title = _substitute_vars(get_val("header_title", ""), context, escape_values=True)
    header_subtitle = _substitute_vars(get_val("header_subtitle", ""), context, escape_values=True)

    raw_body = _normalize_body_html(get_val("body_html", ""))
    rendered_body = _substitute_vars(raw_body, context, escape_values=True)

    cta_text = _substitute_vars((get_val("cta_text", "") or "").strip(), context, escape_values=True)
    cta_url = html.escape(
        _sanitize_url(_substitute_vars(get_val("cta_url", "https://clanship.cl"), context, escape_values=False)),
        quote=True,
    )

    footer_raw = _substitute_vars((get_val("footer_text", "") or "").strip(), context, escape_values=True)
    footer_html = footer_raw.replace("\n", "<br/>")

    preheader_block = (
        f'<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">{preheader}</div>'
        if preheader
        else ""
    )
    badge_block = (
        f'<div style="display:inline-block;padding:5px 12px;border-radius:999px;background-color:{accent};'
        f'color:#ffffff;font-size:11px;font-weight:700;letter-spacing:0.8px;text-transform:uppercase;margin-bottom:14px;">'
        f'{header_badge}</div>'
        if header_badge
        else ""
    )
    subtitle_block = (
        f'<p style="margin:10px 0 0 0;font-size:15px;line-height:1.5;color:#dbeafe;">{header_subtitle}</p>'
        if header_subtitle
        else ""
    )
    cta_block = (
        f'<div style="text-align:center;margin:28px 0 8px 0;">'
        f'<a href="{cta_url}" target="_blank" style="display:inline-block;padding:13px 28px;border-radius:10px;'
        f'background-color:{accent};color:#ffffff;font-size:14px;font-weight:700;text-decoration:none;'
        f'box-shadow:0 4px 12px rgba(13,43,69,0.16);">{cta_text}</a>'
        f'</div>'
        if cta_text
        else ""
    )
    footer_block = (
        f'<tr><td style="padding:20px 32px 28px 32px;background-color:#f8fafc;border-top:1px solid #e2e8f0;'
        f'text-align:center;font-size:12px;line-height:1.6;color:#64748b;">{footer_html}</td></tr>'
        if footer_html
        else ""
    )

    rendered_html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{html.escape(subject, quote=True)}</title>
</head>
<body style="margin:0;padding:0;background-color:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#1e293b;">
  {preheader_block}
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color:#f1f5f9;padding:28px 12px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:600px;background-color:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 8px 24px rgba(15,23,42,0.08);border:1px solid #e2e8f0;">
          <tr>
            <td style="background-color:{header_bg};padding:32px 32px 28px 32px;text-align:left;">
              {badge_block}
              <h1 style="margin:0;font-size:24px;line-height:1.3;font-weight:800;color:#ffffff;">{header_title}</h1>
              {subtitle_block}
            </td>
          </tr>
          <tr>
            <td style="padding:28px 32px;font-size:15px;line-height:1.65;color:#334155;">
              {rendered_body}
              {cta_block}
            </td>
          </tr>
          {footer_block}
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    custom_text = (get_val("body_text", "") or "").strip()
    if custom_text:
        rendered_text = _substitute_vars(custom_text, context, escape_values=False)
    else:
        parts = [
            _substitute_vars(get_val("header_title", ""), context, escape_values=False),
            _substitute_vars(get_val("header_subtitle", ""), context, escape_values=False),
            _strip_html(_substitute_vars(get_val("body_html", ""), context, escape_values=False)),
        ]
        if cta_text:
            clean_url = _sanitize_url(_substitute_vars(get_val("cta_url", "https://clanship.cl"), context, escape_values=False))
            parts.append(f"{_substitute_vars(get_val('cta_text', ''), context, escape_values=False)}: {clean_url}")
        if footer_raw:
            parts.append(_substitute_vars(get_val("footer_text", ""), context, escape_values=False))
        rendered_text = "\n\n".join(p for p in parts if p)

    return {
        "subject": subject,
        "from_email": from_email,
        "reply_to": reply_to,
        "html": rendered_html,
        "text": rendered_text,
    }


def _send_via_resend(to_email: str, rendered: Dict[str, Any]) -> Dict[str, Any]:
    resend_api_key = getattr(settings, "RESEND_API_KEY", "")
    if not resend_api_key:
        logger.warning("[WELCOME EMAIL] RESEND_API_KEY no configurada. No se pudo enviar a %s.", to_email)
        return {"sent": False, "error": "RESEND_API_KEY no configurada en el servidor."}

    import resend

    resend.api_key = resend_api_key
    params: Dict[str, Any] = {
        "from": rendered["from_email"],
        "to": [to_email],
        "subject": rendered["subject"],
        "html": rendered["html"],
        "text": rendered["text"],
    }
    if rendered.get("reply_to"):
        params["reply_to"] = rendered["reply_to"]

    response = resend.Emails.send(params)
    resend_id = response.get("id") if isinstance(response, dict) else getattr(response, "id", None)
    logger.info("[WELCOME EMAIL] Enviado exitosamente a '%s'. id=%s", to_email, resend_id)
    return {"sent": True, "id": resend_id}


def send_welcome_email(user, force: bool = False) -> Dict[str, Any]:
    """
    Envía el correo de bienvenida correspondiente al tipo de usuario (CUSTOMER o PROFESSIONAL)
    si la plantilla está activa en base de datos.
    """
    from users.models import WelcomeEmailTemplate

    to_email = (getattr(user, "email", "") or "").strip()
    if not to_email or "@" not in to_email:
        logger.info("[WELCOME EMAIL] Usuario %s sin email válido; omitiendo envío.", getattr(user, "id", None))
        return {"sent": False, "reason": "missing_email"}

    user_type = getattr(user, "user_type", "")
    template = WelcomeEmailTemplate.get_for_user_type(user_type)
    if not template:
        return {"sent": False, "reason": "unsupported_user_type"}

    if not template.is_active and not force:
        logger.info("[WELCOME EMAIL] Plantilla para %s desactivada; omitiendo envío a %s.", user_type, to_email)
        return {"sent": False, "reason": "disabled"}

    context = build_welcome_context(user)
    rendered = render_welcome_email(template, context)
    try:
        return _send_via_resend(to_email, rendered)
    except Exception as exc:
        logger.error("[WELCOME EMAIL ERROR] Fallo al enviar bienvenida a '%s': %s", to_email, exc, exc_info=True)
        return {"sent": False, "error": str(exc)}


def send_welcome_email_async(user) -> None:
    """
    Dispara el envío del correo de bienvenida en segundo plano para no bloquear el registro.
    """
    user_id = getattr(user, "id", None)
    user_email = (getattr(user, "email", "") or "").strip()
    if not user_email or "@" not in user_email:
        return

    def _worker():
        try:
            send_welcome_email(user)
        except Exception as exc:
            logger.error("[WELCOME EMAIL THREAD ERROR] user_id=%s: %s", user_id, exc, exc_info=True)
        finally:
            if threading.current_thread() is not threading.main_thread():
                from django.db import connections
                connections.close_all()

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()


def send_test_welcome_email(template_or_payload: Any, user_type: str, to_email: str) -> Dict[str, Any]:
    """
    Envía un correo de prueba con datos de ejemplo para el rol indicado.
    """
    context = build_sample_context(user_type)
    rendered = render_welcome_email(template_or_payload, context)
    return _send_via_resend(to_email.strip(), rendered)
