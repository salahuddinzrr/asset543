from django.contrib import admin

from .models import Lead, CallLog, MessageLog, EmployeeProfile, SipAccount


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("name", "phone_number", "email", "assigned_to", "created_at")
    search_fields = ("name", "phone_number", "email")
    list_filter = ("assigned_to",)


@admin.register(CallLog)
class CallLogAdmin(admin.ModelAdmin):
    list_display = ("lead", "employee", "direction", "status", "duration_seconds", "started_at")
    list_filter = ("direction", "status")
    search_fields = ("lead__name", "lead__phone_number", "twilio_call_sid")


@admin.register(MessageLog)
class MessageLogAdmin(admin.ModelAdmin):
    list_display = ("lead", "employee", "direction", "status", "created_at")
    list_filter = ("direction", "status")
    search_fields = ("lead__name", "lead__phone_number", "twilio_message_sid", "body")


@admin.register(EmployeeProfile)
class EmployeeProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "phone_number")
    search_fields = ("user__username", "phone_number")


@admin.register(SipAccount)
class SipAccountAdmin(admin.ModelAdmin):
    list_display = ("user", "sip_username", "sip_domain", "is_active")
    list_filter = ("is_active",)
    search_fields = ("user__username", "sip_username", "sip_domain")
