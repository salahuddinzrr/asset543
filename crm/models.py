from django.conf import settings
from django.db import models
from django.utils import timezone


class EmployeeProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="employee_profile")
    phone_number = models.CharField(max_length=32, help_text="E.164 format e.g. +15551234567")

    def __str__(self) -> str:
        return f"{self.user.get_username()} ({self.phone_number})"


class Lead(models.Model):
    name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=32, help_text="E.164 format e.g. +15551234567")
    email = models.EmailField(blank=True, null=True)
    notes = models.TextField(blank=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="leads")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.phone_number})"


class CallLog(models.Model):
    DIRECTION_CHOICES = (
        ("outbound", "Outbound"),
        ("inbound", "Inbound"),
    )
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="call_logs")
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="call_logs")
    twilio_call_sid = models.CharField(max_length=64, blank=True)
    direction = models.CharField(max_length=16, choices=DIRECTION_CHOICES, default="outbound")
    status = models.CharField(max_length=64, blank=True)
    duration_seconds = models.PositiveIntegerField(default=0)
    recording_url = models.URLField(blank=True)
    notes = models.TextField(blank=True)
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(blank=True, null=True)

    def __str__(self) -> str:
        return f"{self.direction} call to {self.lead} at {self.started_at:%Y-%m-%d %H:%M}"


class MessageLog(models.Model):
    DIRECTION_CHOICES = (
        ("outbound", "Outbound"),
        ("inbound", "Inbound"),
    )
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="message_logs")
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="message_logs")
    twilio_message_sid = models.CharField(max_length=64, blank=True)
    direction = models.CharField(max_length=16, choices=DIRECTION_CHOICES, default="outbound")
    body = models.TextField()
    status = models.CharField(max_length=64, blank=True)
    media_urls = models.TextField(blank=True, help_text="JSON array string of media URLs if any")
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self) -> str:
        return f"{self.direction} message to {self.lead} at {self.created_at:%Y-%m-%d %H:%M}"
