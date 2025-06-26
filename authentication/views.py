from django.contrib.auth.models import User
from webauthn import verify_registration_response, verify_authentication_response
from webauthn.helpers.structs import RegistrationCredential, AuthenticatorAttestationResponse, AuthenticationCredential, AuthenticatorAssertionResponse
from rest_framework.permissions import AllowAny
import base64
import json
import uuid

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from webauthn import generate_registration_options, verify_registration_response
from webauthn import generate_authentication_options, verify_authentication_response
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    UserVerificationRequirement,
    # RegistrationCredential,
    AuthenticationCredential,
    AuthenticatorAssertionResponse,
)
from .models import WebAuthnCredential
from .serializers import (
    UserRegistrationSerializer,
    UserSerializer,
    WebAuthnRegistrationBeginSerializer,
    WebAuthnRegistrationCompleteSerializer,
    WebAuthnAuthenticationBeginSerializer,
    WebAuthnAuthenticationCompleteSerializer,
    WebAuthnCredentialSerializer,
)
from datetime import datetime, timedelta



# In-memory storage for WebAuthn challenges (in production, use Redis)
webauthn_challenges = {}

# Rate limiting for WebAuthn operations
webauthn_rate_limits = {}

def check_rate_limit(operation, identifier, max_attempts=5, window_minutes=5):
    """Check rate limiting for WebAuthn operations"""
    now = datetime.now()
    key = f"{operation}:{identifier}"
    
    if key not in webauthn_rate_limits:
        webauthn_rate_limits[key] = []
    
    # Remove old attempts outside the window
    window_start = now - timedelta(minutes=window_minutes)
    webauthn_rate_limits[key] = [
        attempt for attempt in webauthn_rate_limits[key] 
        if attempt > window_start
    ]
    
    # Check if limit exceeded
    if len(webauthn_rate_limits[key]) >= max_attempts:
        return False
    
    # Add current attempt
    webauthn_rate_limits[key].append(now)
    return True

def validate_base64_data(data, field_name):
    """Validate base64 encoded data"""
    try:
        if not data:
            return False, f"{field_name} cannot be empty"
        
        # Check if it's valid base64
        decoded = base64.b64decode(data)
        if len(decoded) == 0:
            return False, f"{field_name} decoded to empty data"
        
        return True, None
    except Exception as e:
        return False, f"Invalid {field_name}: {str(e)}"

def cleanup_expired_challenges():
    """Clean up expired challenges (older than 10 minutes)"""
    now = datetime.now()
    expired_keys = []
    
    for challenge_id, challenge_data in webauthn_challenges.items():
        # Challenges should be cleaned up after use, but this is a safety net
        if 'created_at' not in challenge_data:
            # Add creation time if missing
            challenge_data['created_at'] = now
        elif now - challenge_data['created_at'] > timedelta(minutes=10):
            expired_keys.append(challenge_id)
    
    for key in expired_keys:
        del webauthn_challenges[key]
    
    return len(expired_keys)

# Create your views here.

# Placeholder views for authentication endpoints


@api_view(['POST'])
@permission_classes([AllowAny])
def register_user(request):
    """Register a new user with password"""


    serializer = UserRegistrationSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        
        return Response({
            'message': 'User registered successfully',
            'user': UserSerializer(user).data
        }, status=status.HTTP_201_CREATED)


    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_user(request):
    """Login with username and password (fallback)"""


    username = request.data.get('username')
    password = request.data.get('password')

    if not username or not password:

        return Response({
            'error': 'Username and password are required'
        }, status=status.HTTP_400_BAD_REQUEST)

    user = authenticate(username=username, password=password)
    if user:
        refresh = RefreshToken.for_user(user)

        return Response({
            'message': 'Login successful',
            'user': UserSerializer(user).data,
            'tokens': {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            }
        })
    else:

        return Response({
            'error': 'Invalid credentials'
        }, status=status.HTTP_401_UNAUTHORIZED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_user(request):
    """Logout user"""

    logout(request)

    return Response({'message': 'Logout successful'})


@api_view(['POST'])
@permission_classes([AllowAny])
def webauthn_register_begin(request):
    """Begin WebAuthn registration process"""


    serializer = WebAuthnRegistrationBeginSerializer(data=request.data)
    if not serializer.is_valid():

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    username = serializer.validated_data['username']
    display_name = serializer.validated_data.get('display_name', username)



    # Check if user exists
    try:
        from django.contrib.auth.models import User
        user = User.objects.get(username=username)

    except User.DoesNotExist:

        return Response({
            'error': 'User not found. Please register first.'
        }, status=status.HTTP_404_NOT_FOUND)

    # Generate registration options


    registration_options = generate_registration_options(
        rp_name=settings.WEBAUTHN_RP_NAME,
        rp_id=settings.WEBAUTHN_RP_ID,
        user_id=username.encode(),  # Convert to bytes directly
        user_name=username,
        user_display_name=display_name,
        authenticator_selection=AuthenticatorSelectionCriteria(
            user_verification=UserVerificationRequirement.PREFERRED
        ),
    )



    # Generate a unique challenge ID and store the challenge
    challenge_id = str(uuid.uuid4())
    webauthn_challenges[challenge_id] = {
        'challenge': base64.b64encode(registration_options.challenge).decode(),
        'username': username,
        'type': 'registration'
    }



    # Convert options to dictionary for JSON serialization
    options_dict = {
        'challenge': base64.b64encode(registration_options.challenge).decode(),
        'rp': {
            'name': registration_options.rp.name,
            'id': registration_options.rp.id,
        },
        'user': {
            'id': base64.b64encode(registration_options.user.id).decode(),
            'name': registration_options.user.name,
            'displayName': registration_options.user.display_name,
        },
        'pubKeyCredParams': [
            {
                'type': param.type,
                'alg': param.alg,
            } for param in registration_options.pub_key_cred_params
        ],
        'timeout': registration_options.timeout,
        'excludeCredentials': [
            {
                'type': cred.type,
                'id': base64.b64encode(cred.id).decode(),
                'transports': cred.transports,
            } for cred in registration_options.exclude_credentials
        ] if registration_options.exclude_credentials else [],
        'authenticatorSelection': {
            'authenticatorAttachment': registration_options.authenticator_selection.authenticator_attachment,
            'requireResidentKey': registration_options.authenticator_selection.require_resident_key,
            'residentKey': registration_options.authenticator_selection.resident_key,
            'userVerification': registration_options.authenticator_selection.user_verification,
        },
        'attestation': registration_options.attestation,
    }



    response_data = {
        'options': options_dict,
        'challenge_id': challenge_id
    }



    return Response(response_data)


@api_view(['POST'])
@permission_classes([AllowAny])
def webauthn_register_complete(request):


    serializer = WebAuthnRegistrationCompleteSerializer(data=request.data)
    if not serializer.is_valid():

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


    challenge_id = request.data.get('challenge_id')

    if not challenge_id or challenge_id not in webauthn_challenges:

        return Response({'error': 'Invalid or expired challenge'}, status=status.HTTP_400_BAD_REQUEST)

    stored_data = webauthn_challenges[challenge_id]
    challenge = stored_data['challenge']
    username = stored_data['username']



    try:
        user = User.objects.get(username=username)

    except User.DoesNotExist:

        return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

    try:

        credential_id = serializer.validated_data['credential_id']


        # Ensure proper padding for base64url decoding
        padding = len(credential_id) % 4
        if padding:
            credential_id += '=' * (4 - padding)

        raw_id = base64.urlsafe_b64decode(credential_id)

        # Test re-encoding to verify integrity
        re_encoded = base64.urlsafe_b64encode(
            raw_id).decode('utf-8').rstrip('=')

        # Test standard base64 encoding
        std_encoded = base64.b64encode(raw_id).decode('utf-8')

        attestation_object = base64.b64decode(
            serializer.validated_data['attestation_object'])
        client_data_json = base64.b64decode(
            serializer.validated_data['client_data_json'])

        response = AuthenticatorAttestationResponse(
            client_data_json=client_data_json,
            attestation_object=attestation_object
        )

        # Convert standard base64 to base64url format for the id field
        from webauthn.helpers import bytes_to_base64url
        credential_id_base64url = bytes_to_base64url(raw_id)

        credential = RegistrationCredential(
            id=credential_id_base64url,  # Use base64url format
            raw_id=raw_id,  # Use the decoded bytes
            response=response,
            type="public-key"
        )

        # Verify that base64url encoding of raw_id matches id
        raw_id_encoded = bytes_to_base64url(credential.raw_id)

        verification = verify_registration_response(
            credential=credential,
            expected_rp_id=settings.WEBAUTHN_RP_ID,
            expected_origin=settings.WEBAUTHN_RP_ORIGIN,
            expected_challenge=base64.b64decode(challenge),
        )



        credential_obj = WebAuthnCredential.objects.create(
            user=user,
            credential_id=credential_id,
            public_key=base64.b64encode(
                verification.credential_public_key).decode(),
            sign_count=verification.sign_count,
            transports=serializer.validated_data.get('transports', []),
            backup_eligible=serializer.validated_data.get(
                'backup_eligible', False),
            backup_state=serializer.validated_data.get('backup_state', False),
        )


        del webauthn_challenges[challenge_id]

        response_data = {
            'message': 'WebAuthn credential registered successfully',
            'credential': WebAuthnCredentialSerializer(credential_obj).data
        }


        return Response(response_data)

    except Exception as e:
        import traceback
        return Response({
            'error': f'Registration verification failed: {str(e)}'
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def webauthn_authenticate_begin(request):
    """Begin WebAuthn authentication process"""
    
    # Clean up expired challenges
    cleanup_expired_challenges()
    
    serializer = WebAuthnAuthenticationBeginSerializer(data=request.data)
    if not serializer.is_valid():   
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    username = serializer.validated_data['username']
    
    # Check rate limiting
    if not check_rate_limit('authenticate_begin', username):
        return Response({
            'error': 'Too many authentication attempts. Please try again later.'
        }, status=status.HTTP_429_TOO_MANY_REQUESTS)
    

    try:
        from django.contrib.auth.models import User
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        return Response({
            'error': 'User not found'
        }, status=status.HTTP_404_NOT_FOUND)

    # Get user's credentials
    credentials = WebAuthnCredential.objects.filter(user=user)

    if not credentials.exists():
        return Response({
            'error': 'No WebAuthn credentials found for this user'
        }, status=status.HTTP_404_NOT_FOUND)

    # Generate authentication options
    allow_credentials = []
    for credential in credentials:
        allow_credentials.append({
            'id': credential.credential_id,
            'type': 'public-key',
            'transports': credential.transports,
        })

    authentication_options = generate_authentication_options(
        rp_id=settings.WEBAUTHN_RP_ID,
        allow_credentials=allow_credentials,
        user_verification=UserVerificationRequirement.PREFERRED,
    )

    # Generate a unique challenge ID and store the challenge
    challenge_id = str(uuid.uuid4())
    webauthn_challenges[challenge_id] = {
        'challenge': base64.b64encode(authentication_options.challenge).decode(),
        'username': username,
        'type': 'authentication'
    }


    # Convert options to dictionary for JSON serialization

    options_dict = {
        'challenge': base64.b64encode(authentication_options.challenge).decode(),
        'rpId': authentication_options.rp_id,
        'allowCredentials': [
            {
                'type': cred['type'],
                'id': cred['id'],
                'transports': cred['transports'],
            } for cred in authentication_options.allow_credentials
        ],
        'userVerification': authentication_options.user_verification,
        'timeout': authentication_options.timeout,
    }



    response_data = {
        'options': options_dict,
        'challenge_id': challenge_id
    }



    return Response(response_data)


@api_view(['POST'])
@permission_classes([AllowAny])
def webauthn_authenticate_complete(request):
    """Complete WebAuthn authentication process"""
    
    # Clean up expired challenges
    cleanup_expired_challenges()
    
    serializer = WebAuthnAuthenticationCompleteSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    
    # Validate base64 data
    credential_id = serializer.validated_data['credential_id']
    authenticator_data = serializer.validated_data['authenticator_data']
    client_data_json = serializer.validated_data['client_data_json']
    signature = serializer.validated_data['signature']
    
    is_valid, error_msg = validate_base64_data(credential_id, 'credential_id')
    if not is_valid:
        return Response({'error': error_msg}, status=status.HTTP_400_BAD_REQUEST)
    
    is_valid, error_msg = validate_base64_data(authenticator_data, 'authenticator_data')
    if not is_valid:
        return Response({'error': error_msg}, status=status.HTTP_400_BAD_REQUEST)
    
    is_valid, error_msg = validate_base64_data(client_data_json, 'client_data_json')
    if not is_valid:    
        return Response({'error': error_msg}, status=status.HTTP_400_BAD_REQUEST)
    
    is_valid, error_msg = validate_base64_data(signature, 'signature')
    if not is_valid:
        return Response({'error': error_msg}, status=status.HTTP_400_BAD_REQUEST)
    
    # Check rate limiting
    username = serializer.validated_data['username']
    if not check_rate_limit('authenticate_complete', username):
        return Response({
            'error': 'Too many authentication attempts. Please try again later.'
        }, status=status.HTTP_429_TOO_MANY_REQUESTS)

    # Get challenge ID and retrieve stored challenge
    challenge_id = request.data.get('challenge_id')

    if not challenge_id or challenge_id not in webauthn_challenges:

        return Response({
            'error': 'Invalid or expired challenge'
        }, status=status.HTTP_400_BAD_REQUEST)

    stored_data = webauthn_challenges[challenge_id]
    challenge = stored_data['challenge']
    username = stored_data['username']



    try:
        from django.contrib.auth.models import User
        user = User.objects.get(username=username)

    except User.DoesNotExist:

        return Response({
            'error': 'User not found'
        }, status=status.HTTP_404_NOT_FOUND)

    # Get credential
    try:
        credential = WebAuthnCredential.objects.get(
            user=user,
            credential_id=serializer.validated_data['credential_id']
        )

    except WebAuthnCredential.DoesNotExist:

        return Response({
            'error': 'Credential not found'
        }, status=status.HTTP_404_NOT_FOUND)

    # Verify authentication response
    try:


        # Create the credential object for verification
        decoded_credential_id = base64.b64decode(
            serializer.validated_data['credential_id'])


        # Test re-encoding to verify integrity
        re_encoded = base64.b64encode(decoded_credential_id).decode('utf-8')


        # Test urlsafe encoding
        urlsafe_encoded = base64.urlsafe_b64encode(
            decoded_credential_id).decode('utf-8').rstrip('=')


        # Create the credential object with the correct structure
        from webauthn.helpers import bytes_to_base64url
        credential_id_base64url = bytes_to_base64url(decoded_credential_id)

        
        # Create the authenticator assertion response
        authenticator_assertion_response = AuthenticatorAssertionResponse(
            authenticator_data=base64.b64decode(
                serializer.validated_data['authenticator_data']),
            client_data_json=base64.b64decode(
                serializer.validated_data['client_data_json']),
            signature=base64.b64decode(
                serializer.validated_data['signature']),
        )

        
        credential_obj = AuthenticationCredential(
            id=credential_id_base64url,  # Use base64url format
            raw_id=decoded_credential_id,  # Use decoded bytes
            response=authenticator_assertion_response,
            type="public-key",
        )

        
        # Verify that base64url encoding of raw_id matches id
        raw_id_encoded = bytes_to_base64url(credential_obj.raw_id)
        
        verification = verify_authentication_response(
            credential=credential_obj,
            expected_rp_id=settings.WEBAUTHN_RP_ID,
            expected_origin=settings.WEBAUTHN_RP_ORIGIN,
            expected_challenge=base64.b64decode(challenge),
            credential_public_key=base64.b64decode(credential.public_key),
            credential_current_sign_count=credential.sign_count,
        )



        # Update credential sign count
        credential.sign_count = verification.new_sign_count
        credential.update_last_used()
        credential.save()


        # Login user
        login(request, user)


        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)


        # Clear the challenge
        del webauthn_challenges[challenge_id]


        response_data = {
            'message': 'Authentication successful',
            'user': UserSerializer(user).data,
            'tokens': {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            }
        }



        return Response(response_data)

    except Exception as e:
        return Response({
            'error': f'Authentication verification failed: {str(e)}'
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    """Get current user profile"""


    serializer = UserSerializer(request.user)
    response_data = serializer.data


    return Response(response_data)
