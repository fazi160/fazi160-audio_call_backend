from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import *

app_name = 'authentication'

urlpatterns = [
    path('register/', register_user, name='register'),
    path('login/', login_user, name='login'),
    path('logout/', logout_user, name='logout'),
    path('webauthn/register/begin/', webauthn_register_begin, name='webauthn_register_begin'),
    path('webauthn/register/complete/', webauthn_register_complete, name='webauthn_register_complete'),
    path('webauthn/authenticate/begin/', webauthn_authenticate_begin, name='webauthn_authenticate_begin'),
    path('webauthn/authenticate/complete/', webauthn_authenticate_complete, name='webauthn_authenticate_complete'),
    path('profile/', user_profile, name='user_profile'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
] 