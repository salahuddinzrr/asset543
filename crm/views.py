from __future__ import annotations

import json
from typing import Optional

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt

from .models import CallLog, EmployeeProfile, Lead, MessageLog, SipAccount


try:
    from twilio.rest import Client as TwilioClient
    from twilio.twiml.voice_response import VoiceResponse, Dial
except Exception:  # twilio may not be installed yet during code navigation
    TwilioClient = None  # type: ignore
    VoiceResponse = None  # type: ignore
    Dial = None  # type: ignore


def _get_twilio_client() -> TwilioClient:
    if TwilioClient is None:
        raise RuntimeError("Twilio client not available. Install twilio and configure settings.")
    return TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)


@login_required
def lead_list(request: HttpRequest) -> HttpResponse:
    leads = Lead.objects.all().order_by("-created_at")
    return render(request, "crm/lead_list.html", {"leads": leads})


@login_required
def sip_settings(request: HttpRequest) -> HttpResponse:
    sip: Optional[SipAccount] = getattr(request.user, "sip_account", None)
    if request.method == "POST":
        username = request.POST.get("sip_username", "").strip()
        domain = request.POST.get("sip_domain", "").strip()
        display = request.POST.get("display_name", "").strip()
        active = request.POST.get("is_active") == "on"
        if sip is None:
            sip = SipAccount.objects.create(
                user=request.user,
                sip_username=username,
                sip_domain=domain,
                display_name=display,
                is_active=active,
            )
        else:
            sip.sip_username = username
            sip.sip_domain = domain
            sip.display_name = display
            sip.is_active = active
            sip.save()
        return redirect("crm:sip_settings")
    return render(request, "crm/sip_settings.html", {"sip": sip})


@login_required
def lead_detail(request: HttpRequest, lead_id: int) -> HttpResponse:
    lead = get_object_or_404(Lead, id=lead_id)
    call_logs = lead.call_logs.order_by("-started_at")[:50]
    message_logs = lead.message_logs.order_by("-created_at")[:50]
    return render(
        request,
        "crm/lead_detail.html",
        {"lead": lead, "call_logs": call_logs, "message_logs": message_logs},
    )


@login_required
def click_to_call(request: HttpRequest, lead_id: int) -> HttpResponse:
    lead = get_object_or_404(Lead, id=lead_id)
    employee_profile: Optional[EmployeeProfile] = getattr(request.user, "employee_profile", None)
    if employee_profile is None or not employee_profile.phone_number:
        # allow SIP-only users
        sip: Optional[SipAccount] = getattr(request.user, "sip_account", None)
        if sip is None or not sip.is_active:
            return JsonResponse({"error": "Configure phone number or SIP account first."}, status=400)

    call_log = CallLog.objects.create(
        lead=lead,
        employee=request.user,
        direction="outbound",
        status="queued",
    )

    client = _get_twilio_client()

    connect_url = request.build_absolute_uri(
        reverse("crm:voice_connect_twiml", kwargs={"lead_id": lead.id})
    )
    status_callback_url = request.build_absolute_uri(reverse("crm:voice_status_callback"))

    # Prefer SIP if configured and active
    sip_account: Optional[SipAccount] = getattr(request.user, "sip_account", None)
    to_target: str
    used_sip = False
    if sip_account and sip_account.is_active:
        username = sip_account.sip_username
        domain = sip_account.sip_domain
        to_target = f"sip:{username}@{domain}"
        used_sip = True
    else:
        to_target = employee_profile.phone_number

    try:
        call = client.calls.create(
            to=to_target,
            from_=settings.TWILIO_FROM_NUMBER,
            url=connect_url,
            status_callback=status_callback_url,
            status_callback_event=["initiated", "ringing", "answered", "completed"],
        )
        call_log.twilio_call_sid = call.sid
        call_log.status = getattr(call, "status", None) or "queued"
        call_log.used_sip = used_sip
        call_log.save(update_fields=["twilio_call_sid", "status", "used_sip"])
    except Exception as exc:  # pragma: no cover - depends on external service
        call_log.status = "failed"
        call_log.notes = str(exc)
        call_log.save(update_fields=["status", "notes"])
        return JsonResponse({"error": "Failed to initiate call", "detail": str(exc)}, status=500)

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "sid": call_log.twilio_call_sid})
    return redirect("crm:lead_detail", lead_id=lead.id)


@login_required
def voice_connect_twiml(request: HttpRequest, lead_id: int) -> HttpResponse:
    lead = get_object_or_404(Lead, id=lead_id)
    if VoiceResponse is None:
        return HttpResponse("<Response></Response>", content_type="text/xml")

    response = VoiceResponse()
    dial = Dial(record="record-from-answer", recording_status_callback_event=["completed"])
    dial.number(lead.phone_number)
    response.say("Connecting you to the customer.")
    response.append(dial)
    xml = str(response)
    return HttpResponse(xml, content_type="text/xml")


@csrf_exempt
def voice_status_callback(request: HttpRequest) -> HttpResponse:
    # Twilio will POST status updates
    if request.method != "POST":
        return HttpResponse(status=405)

    call_sid = request.POST.get("CallSid", "")
    call_status = request.POST.get("CallStatus", "")
    duration = request.POST.get("CallDuration")
    recording_url = request.POST.get("RecordingUrl", "")

    try:
        call_log = CallLog.objects.get(twilio_call_sid=call_sid)
        call_log.status = call_status
        if duration and duration.isdigit():
            call_log.duration_seconds = int(duration)
        if recording_url:
            call_log.recording_url = recording_url
        call_log.save(update_fields=["status", "duration_seconds", "recording_url"])
    except CallLog.DoesNotExist:
        pass

    return HttpResponse("OK")


@login_required
def send_sms(request: HttpRequest, lead_id: int) -> HttpResponse:
    if request.method != "POST":
        return HttpResponse(status=405)

    lead = get_object_or_404(Lead, id=lead_id)
    body = request.POST.get("body", "").strip()
    if not body:
        return JsonResponse({"error": "Message body cannot be empty"}, status=400)

    client = _get_twilio_client()
    try:
        msg = client.messages.create(
            to=lead.phone_number,
            from_=settings.TWILIO_FROM_NUMBER,
            body=body,
        )
        MessageLog.objects.create(
            lead=lead,
            employee=request.user,
            direction="outbound",
            body=body,
            status=msg.status or "queued",
            twilio_message_sid=msg.sid,
        )
    except Exception as exc:  # pragma: no cover
        MessageLog.objects.create(
            lead=lead,
            employee=request.user,
            direction="outbound",
            body=body,
            status="failed",
        )
        return JsonResponse({"error": "Failed to send SMS", "detail": str(exc)}, status=500)

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": True})
    return redirect("crm:lead_detail", lead_id=lead.id)


@csrf_exempt
def inbound_sms_webhook(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return HttpResponse(status=405)

    from_number = request.POST.get("From", "")
    body = request.POST.get("Body", "")
    sid = request.POST.get("MessageSid", "")
    status = request.POST.get("SmsStatus", "received")

    # Try to match lead by phone number
    lead = Lead.objects.filter(phone_number=from_number).first()
    MessageLog.objects.create(
        lead=lead,  # may be None if unknown sender
        employee=None,
        direction="inbound",
        body=body or "",
        status=status or "received",
        twilio_message_sid=sid or "",
    )

    return HttpResponse("OK")
