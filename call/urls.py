from django.urls import path
from . import views

urlpatterns = [
    path("token/", views.get_token, name="get_token"),
    path("voice/handler/", views.voice_handler, name="voice_handler"),
    path("voice/fallback/", views.voice_fallback, name="voice_fallback"),
    path("voice/status/", views.voice_status_callback, name="voice_status_callback"),
    path("history/", views.call_history, name="call_history"),
    path("statistics/", views.call_statistics, name="call_statistics"),
    path("detail/<int:call_id>/", views.call_detail, name="call_detail"),
    path("detail/<int:call_id>/notes/", views.add_note, name="add_note"),
] 