from django.urls import path
from . import views

app_name = "crm"

urlpatterns = [
    path("leads/", views.lead_list, name="lead_list"),
    path("leads/<int:lead_id>/", views.lead_detail, name="lead_detail"),
    path("leads/<int:lead_id>/call/", views.click_to_call, name="click_to_call"),
    path("voice/connect/<int:lead_id>/", views.voice_connect_twiml, name="voice_connect_twiml"),
    path("voice/status/", views.voice_status_callback, name="voice_status_callback"),
    path("sms/send/<int:lead_id>/", views.send_sms, name="send_sms"),
    path("sms/inbound/", views.inbound_sms_webhook, name="inbound_sms_webhook"),
]
