from django.urls import path
from . import views

app_name = 'dialer'

urlpatterns = [
    path('call/initiate/', views.initiate_call, name='initiate_call'),
    path('call/status/<str:call_sid>/', views.call_status, name='call_status'),
    path('call/end/<str:call_sid>/', views.end_call, name='end_call'),
    path('calls/', views.call_history, name='call_history'),
    path('webhook/twilio/', views.twilio_webhook, name='twilio_webhook'),
    path('twiml/voice/', views.twiml_voice, name='twiml_voice'),
] 