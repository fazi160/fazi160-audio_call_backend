from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create a router and register our viewsets with it
router = DefaultRouter()
router.register(r'contacts', views.ContactView, basename='contact')

# The API URLs are now determined automatically by the router
urlpatterns = [
    path('', include(router.urls)),
]
