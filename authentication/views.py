from django.contrib.auth.models import User
from webauthn import verify_registration_response, verify_authentication_response
from webauthn.helpers.structs import RegistrationCredential, AuthenticatorAttestationResponse, AuthenticationCredential, AuthenticatorAssertionResponse
from rest_framework.permissions import AllowAny
import base64
import json
import uuid
import logging
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

# Configure logging
logger = logging.getLogger('authentication')

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
        logger.info(f"Cleaned up expired challenge: {key}")
    
    return len(expired_keys)

# Create your views here.

# Placeholder views for authentication endpoints


@api_view(['POST'])
@permission_classes([AllowAny])
def register_user(request):
    """Register a new user with password"""
    logger.info("=== User Registration ===")
    logger.info(f"Request data: {request.data}")

    serializer = UserRegistrationSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        logger.info(
            f"User registered successfully: {user.username} (ID: {user.id})")
        return Response({
            'message': 'User registered successfully',
            'user': UserSerializer(user).data
        }, status=status.HTTP_201_CREATED)

    logger.error(f"Registration failed: {serializer.errors}")
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_user(request):
    """Login with username and password (fallback)"""
    logger.info("=== Password Login ===")
    logger.info(f"Request data: {request.data}")

    username = request.data.get('username')
    password = request.data.get('password')

    if not username or not password:
        logger.error("Missing username or password")
        return Response({
            'error': 'Username and password are required'
        }, status=status.HTTP_400_BAD_REQUEST)

    user = authenticate(username=username, password=password)
    if user:
        refresh = RefreshToken.for_user(user)
        logger.info(f"Password login successful: {user.username}")
        return Response({
            'message': 'Login successful',
            'user': UserSerializer(user).data,
            'tokens': {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            }
        })
    else:
        logger.error(f"Invalid credentials for user: {username}")
        return Response({
            'error': 'Invalid credentials'
        }, status=status.HTTP_401_UNAUTHORIZED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_user(request):
    """Logout user"""
    logger.info(f"=== User Logout ===")
    logger.info(f"User logging out: {request.user.username}")
    logout(request)
    logger.info("Logout successful")
    return Response({'message': 'Logout successful'})


@api_view(['POST'])
@permission_classes([AllowAny])
def webauthn_register_begin(request):
    """Begin WebAuthn registration process"""
    logger.info("=== WebAuthn Registration Begin ===")
    logger.info(f"Request data: {request.data}")

    serializer = WebAuthnRegistrationBeginSerializer(data=request.data)
    if not serializer.is_valid():
        logger.error(f"Serializer validation failed: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    username = serializer.validated_data['username']
    display_name = serializer.validated_data.get('display_name', username)

    logger.info(
        f"Processing registration for user: {username}, display_name: {display_name}")

    # Check if user exists
    try:
        from django.contrib.auth.models import User
        user = User.objects.get(username=username)
        logger.info(f"User found: {user.username} (ID: {user.id})")
    except User.DoesNotExist:
        logger.error(f"User not found: {username}")
        return Response({
            'error': 'User not found. Please register first.'
        }, status=status.HTTP_404_NOT_FOUND)

    # Generate registration options
    logger.info("Generating registration options...")
    logger.info(f"RP Name: {settings.WEBAUTHN_RP_NAME}")
    logger.info(f"RP ID: {settings.WEBAUTHN_RP_ID}")
    logger.info(f"User ID (bytes): {username.encode()}")

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

    logger.info(f"Registration options generated successfully")
    logger.info(
        f"Challenge (base64): {base64.b64encode(registration_options.challenge).decode()}")
    logger.info(
        f"Challenge length: {len(registration_options.challenge)} bytes")

    # Generate a unique challenge ID and store the challenge
    challenge_id = str(uuid.uuid4())
    webauthn_challenges[challenge_id] = {
        'challenge': base64.b64encode(registration_options.challenge).decode(),
        'username': username,
        'type': 'registration'
    }

    logger.info(f"Challenge stored with ID: {challenge_id}")
    logger.info(f"Total challenges in memory: {len(webauthn_challenges)}")

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

    logger.info("Registration options converted to dictionary")
    logger.info(f"Options dict keys: {list(options_dict.keys())}")
    logger.info(f"User ID in options: {options_dict['user']['id']}")
    logger.info(f"Challenge in options: {options_dict['challenge']}")

    response_data = {
        'options': options_dict,
        'challenge_id': challenge_id
    }

    logger.info("=== WebAuthn Registration Begin Complete ===")
    logger.info(f"Response data: {response_data}")

    return Response(response_data)


@api_view(['POST'])
@permission_classes([AllowAny])
def webauthn_register_complete(request):
    logger.info("=== WebAuthn Registration Complete ===")
    logger.info(f"Request data: {request.data}")
    logger.info(f"Request data type: {type(request.data)}")
    logger.info(
        f"Request data keys: {list(request.data.keys()) if hasattr(request.data, 'keys') else 'Not a dict'}")

    # Log each field individually to check for encoding issues
    for key, value in request.data.items():
        logger.info(
            f"Field '{key}': type={type(value)}, length={len(str(value)) if value else 0}")
        if key in ['credential_id', 'attestation_object', 'client_data_json']:
            logger.info(f"  Value: {value}")
            if value:
                logger.info(f"  Contains padding: {'=' in str(value)}")
                logger.info(
                    f"  Valid base64 length: {len(str(value)) % 4 == 0}")

    serializer = WebAuthnRegistrationCompleteSerializer(data=request.data)
    if not serializer.is_valid():
        logger.error(f"Serializer validation failed: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    logger.info(f"Serializer validated successfully")
    logger.info(f"Validated data: {serializer.validated_data}")

    challenge_id = request.data.get('challenge_id')
    logger.info(f"Challenge ID from request: {challenge_id}")

    if not challenge_id or challenge_id not in webauthn_challenges:
        logger.error(
            f"Invalid or expired challenge. Challenge ID: {challenge_id}")
        logger.error(
            f"Available challenges: {list(webauthn_challenges.keys())}")
        return Response({'error': 'Invalid or expired challenge'}, status=status.HTTP_400_BAD_REQUEST)

    stored_data = webauthn_challenges[challenge_id]
    challenge = stored_data['challenge']
    username = stored_data['username']

    logger.info(f"Retrieved stored challenge data:")
    logger.info(f"  - Challenge: {challenge}")
    logger.info(f"  - Username: {username}")
    logger.info(f"  - Type: {stored_data['type']}")

    try:
        user = User.objects.get(username=username)
        logger.info(f"User found: {user.username} (ID: {user.id})")
    except User.DoesNotExist:
        logger.error(f"User not found: {username}")
        return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

    try:
        logger.info(f"Starting verification for user: {username}")
        logger.info(f"Challenge: {challenge}")
        logger.info(f"RP ID: {settings.WEBAUTHN_RP_ID}")
        logger.info(f"Origin: {settings.WEBAUTHN_RP_ORIGIN}")

        credential_id = serializer.validated_data['credential_id']
        logger.info(f"Original credential_id: {credential_id}")
        logger.info(f"Credential_id length: {len(credential_id)}")
        logger.info(f"Credential_id contains padding: {'=' in credential_id}")
        logger.info(
            f"Credential_id is valid base64: {len(credential_id) % 4 == 0}")

        # Ensure proper padding for base64url decoding
        padding = len(credential_id) % 4
        if padding:
            credential_id += '=' * (4 - padding)
            logger.info(f"Added padding, new credential_id: {credential_id}")

        raw_id = base64.urlsafe_b64decode(credential_id)
        logger.info(f"Decoded raw_id length: {len(raw_id)} bytes")
        logger.info(f"Raw_id (hex): {raw_id.hex()}")

        # Test re-encoding to verify integrity
        re_encoded = base64.urlsafe_b64encode(
            raw_id).decode('utf-8').rstrip('=')
        logger.info(f"Re-encoded credential_id: {re_encoded}")
        logger.info(
            f"Original vs re-encoded match: {serializer.validated_data['credential_id'] == re_encoded}")

        # Test standard base64 encoding
        std_encoded = base64.b64encode(raw_id).decode('utf-8')
        logger.info(f"Standard base64 encoded: {std_encoded}")
        logger.info(
            f"Original vs standard base64 match: {serializer.validated_data['credential_id'] == std_encoded}")

        attestation_object = base64.b64decode(
            serializer.validated_data['attestation_object'])
        client_data_json = base64.b64decode(
            serializer.validated_data['client_data_json'])

        logger.info(
            f"Attestation object length: {len(attestation_object)} bytes")
        logger.info(f"Client data JSON length: {len(client_data_json)} bytes")
        logger.info(f"Client data JSON content: {client_data_json.decode()}")

        response = AuthenticatorAttestationResponse(
            client_data_json=client_data_json,
            attestation_object=attestation_object
        )
        logger.info("AuthenticatorAttestationResponse created successfully")

        # Convert standard base64 to base64url format for the id field
        from webauthn.helpers import bytes_to_base64url
        credential_id_base64url = bytes_to_base64url(raw_id)
        logger.info(
            f"Converted credential_id to base64url: {credential_id_base64url}")
        logger.info(
            f"Original vs base64url match: {serializer.validated_data['credential_id'] == credential_id_base64url}")

        credential = RegistrationCredential(
            id=credential_id_base64url,  # Use base64url format
            raw_id=raw_id,  # Use the decoded bytes
            response=response,
            type="public-key"
        )
        logger.info("RegistrationCredential created successfully")
        logger.info(f"Credential ID type: {type(credential.id)}")
        logger.info(f"Credential ID value: {credential.id}")
        logger.info(f"Credential raw_id type: {type(credential.raw_id)}")
        logger.info(
            f"Credential raw_id length: {len(credential.raw_id)} bytes")
        logger.info(f"Credential raw_id (hex): {credential.raw_id.hex()}")
        logger.info(f"Credential type: {credential.type}")

        # Verify that base64url encoding of raw_id matches id
        raw_id_encoded = bytes_to_base64url(credential.raw_id)
        logger.info(f"Base64url encoding of raw_id: {raw_id_encoded}")
        logger.info(
            f"ID and base64url(raw_id) match: {credential.id == raw_id_encoded}")
        logger.info(
            f"ID and raw_id have correct types: {isinstance(credential.id, str) and isinstance(credential.raw_id, bytes)}")

        logger.info("Starting verification with webauthn library...")
        verification = verify_registration_response(
            credential=credential,
            expected_rp_id=settings.WEBAUTHN_RP_ID,
            expected_origin=settings.WEBAUTHN_RP_ORIGIN,
            expected_challenge=base64.b64decode(challenge),
        )

        logger.info("=== Verification Successful ===")
        logger.info(f"Verification object: {verification}")
        logger.info(f"Sign count: {verification.sign_count}")
        logger.info(
            f"Credential public key length: {len(verification.credential_public_key)} bytes")
        logger.info(
            f"Credential public key (base64): {base64.b64encode(verification.credential_public_key).decode()}")

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

        logger.info(f"WebAuthnCredential saved to database:")
        logger.info(f"  - ID: {credential_obj.id}")
        logger.info(f"  - User: {credential_obj.user.username}")
        logger.info(f"  - Credential ID: {credential_obj.credential_id}")
        logger.info(f"  - Sign count: {credential_obj.sign_count}")
        logger.info(f"  - Transports: {credential_obj.transports}")

        del webauthn_challenges[challenge_id]
        logger.info(f"Challenge {challenge_id} removed from memory")
        logger.info(f"Remaining challenges: {len(webauthn_challenges)}")

        response_data = {
            'message': 'WebAuthn credential registered successfully',
            'credential': WebAuthnCredentialSerializer(credential_obj).data
        }

        logger.info("=== WebAuthn Registration Complete Success ===")
        logger.info(f"Response data: {response_data}")

        return Response(response_data)

    except Exception as e:
        import traceback
        logger.error(f"Registration verification failed: {str(e)}")
        logger.error(f"Exception type: {type(e).__name__}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return Response({
            'error': f'Registration verification failed: {str(e)}'
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def webauthn_authenticate_begin(request):
    """Begin WebAuthn authentication process"""
    logger.info("=== WebAuthn Authentication Begin ===")
    logger.info(f"Request data: {request.data}")
    
    # Clean up expired challenges
    cleanup_expired_challenges()
    
    serializer = WebAuthnAuthenticationBeginSerializer(data=request.data)
    if not serializer.is_valid():
        logger.error(f"Serializer validation failed: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    username = serializer.validated_data['username']
    
    # Check rate limiting
    if not check_rate_limit('authenticate_begin', username):
        logger.warning(f"Rate limit exceeded for authentication begin: {username}")
        return Response({
            'error': 'Too many authentication attempts. Please try again later.'
        }, status=status.HTTP_429_TOO_MANY_REQUESTS)
    
    logger.info(f"Processing authentication for user: {username}")

    try:
        from django.contrib.auth.models import User
        user = User.objects.get(username=username)
        logger.info(f"User found: {user.username} (ID: {user.id})")
    except User.DoesNotExist:
        logger.error(f"User not found: {username}")
        return Response({
            'error': 'User not found'
        }, status=status.HTTP_404_NOT_FOUND)

    # Get user's credentials
    credentials = WebAuthnCredential.objects.filter(user=user)
    logger.info(f"Found {credentials.count()} credentials for user {username}")

    if not credentials.exists():
        logger.error(f"No WebAuthn credentials found for user: {username}")
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
        logger.info(
            f"Added credential: {credential.credential_id} (transports: {credential.transports})")

    logger.info("Generating authentication options...")
    logger.info(f"RP ID: {settings.WEBAUTHN_RP_ID}")
    logger.info(f"Allow credentials count: {len(allow_credentials)}")

    authentication_options = generate_authentication_options(
        rp_id=settings.WEBAUTHN_RP_ID,
        allow_credentials=allow_credentials,
        user_verification=UserVerificationRequirement.PREFERRED,
    )

    logger.info(f"Authentication options generated successfully")
    logger.info(
        f"Challenge (base64): {base64.b64encode(authentication_options.challenge).decode()}")
    logger.info(
        f"Challenge length: {len(authentication_options.challenge)} bytes")

    # Generate a unique challenge ID and store the challenge
    challenge_id = str(uuid.uuid4())
    webauthn_challenges[challenge_id] = {
        'challenge': base64.b64encode(authentication_options.challenge).decode(),
        'username': username,
        'type': 'authentication'
    }

    logger.info(f"Challenge stored with ID: {challenge_id}")
    logger.info(f"Total challenges in memory: {len(webauthn_challenges)}")

    # Convert options to dictionary for JSON serialization
    for cred in authentication_options.allow_credentials:
        logger.info(f"Allow credential: {cred}")
        logger.info(f"Allow credential id: {cred['id']}")
        logger.info(f"Allow credential type: {cred['type']}")
        logger.info(f"Allow credential transports: {cred['transports']}")

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

    logger.info("Authentication options converted to dictionary")
    logger.info(f"Options dict keys: {list(options_dict.keys())}")
    logger.info(f"Challenge in options: {options_dict['challenge']}")
    logger.info(
        f"Allow credentials count in options: {len(options_dict['allowCredentials'])}")

    response_data = {
        'options': options_dict,
        'challenge_id': challenge_id
    }

    logger.info("=== WebAuthn Authentication Begin Complete ===")
    logger.info(f"Response data: {response_data}")

    return Response(response_data)


@api_view(['POST'])
@permission_classes([AllowAny])
def webauthn_authenticate_complete(request):
    """Complete WebAuthn authentication process"""
    logger.info("=== WebAuthn Authentication Complete ===")
    logger.info(f"Request data: {request.data}")
    
    # Clean up expired challenges
    cleanup_expired_challenges()
    
    serializer = WebAuthnAuthenticationCompleteSerializer(data=request.data)
    if not serializer.is_valid():
        logger.error(f"Serializer validation failed: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    logger.info("Serializer validated successfully")
    logger.info(f"Validated data: {serializer.validated_data}")
    
    # Validate base64 data
    credential_id = serializer.validated_data['credential_id']
    authenticator_data = serializer.validated_data['authenticator_data']
    client_data_json = serializer.validated_data['client_data_json']
    signature = serializer.validated_data['signature']
    
    is_valid, error_msg = validate_base64_data(credential_id, 'credential_id')
    if not is_valid:
        logger.error(f"Credential ID validation failed: {error_msg}")
        return Response({'error': error_msg}, status=status.HTTP_400_BAD_REQUEST)
    
    is_valid, error_msg = validate_base64_data(authenticator_data, 'authenticator_data')
    if not is_valid:
        logger.error(f"Authenticator data validation failed: {error_msg}")
        return Response({'error': error_msg}, status=status.HTTP_400_BAD_REQUEST)
    
    is_valid, error_msg = validate_base64_data(client_data_json, 'client_data_json')
    if not is_valid:
        logger.error(f"Client data JSON validation failed: {error_msg}")
        return Response({'error': error_msg}, status=status.HTTP_400_BAD_REQUEST)
    
    is_valid, error_msg = validate_base64_data(signature, 'signature')
    if not is_valid:
        logger.error(f"Signature validation failed: {error_msg}")
        return Response({'error': error_msg}, status=status.HTTP_400_BAD_REQUEST)
    
    # Check rate limiting
    username = serializer.validated_data['username']
    if not check_rate_limit('authenticate_complete', username):
        logger.warning(f"Rate limit exceeded for authentication complete: {username}")
        return Response({
            'error': 'Too many authentication attempts. Please try again later.'
        }, status=status.HTTP_429_TOO_MANY_REQUESTS)

    # Get challenge ID and retrieve stored challenge
    challenge_id = request.data.get('challenge_id')
    logger.info(f"Challenge ID from request: {challenge_id}")

    if not challenge_id or challenge_id not in webauthn_challenges:
        logger.error(
            f"Invalid or expired challenge. Challenge ID: {challenge_id}")
        logger.error(
            f"Available challenges: {list(webauthn_challenges.keys())}")
        return Response({
            'error': 'Invalid or expired challenge'
        }, status=status.HTTP_400_BAD_REQUEST)

    stored_data = webauthn_challenges[challenge_id]
    challenge = stored_data['challenge']
    username = stored_data['username']

    logger.info(f"Retrieved stored challenge data:")
    logger.info(f"  - Challenge: {challenge}")
    logger.info(f"  - Username: {username}")
    logger.info(f"  - Type: {stored_data['type']}")

    try:
        from django.contrib.auth.models import User
        user = User.objects.get(username=username)
        logger.info(f"User found: {user.username} (ID: {user.id})")
    except User.DoesNotExist:
        logger.error(f"User not found: {username}")
        return Response({
            'error': 'User not found'
        }, status=status.HTTP_404_NOT_FOUND)

    # Get credential
    try:
        credential = WebAuthnCredential.objects.get(
            user=user,
            credential_id=serializer.validated_data['credential_id']
        )
        logger.info(f"Credential found: {credential.credential_id}")
        logger.info(
            f"Credential public key length: {len(base64.b64decode(credential.public_key))} bytes")
        logger.info(f"Credential sign count: {credential.sign_count}")
    except WebAuthnCredential.DoesNotExist:
        logger.error(
            f"Credential not found for user {username} with ID {serializer.validated_data['credential_id']}")
        return Response({
            'error': 'Credential not found'
        }, status=status.HTTP_404_NOT_FOUND)

    # Verify authentication response
    try:
        logger.info("Starting authentication verification...")
        logger.info(f"Challenge: {challenge}")
        logger.info(f"RP ID: {settings.WEBAUTHN_RP_ID}")
        logger.info(f"Origin: {settings.WEBAUTHN_RP_ORIGIN}")

        # Create the credential object for verification
        decoded_credential_id = base64.b64decode(
            serializer.validated_data['credential_id'])
        logger.info(
            f"Decoded credential_id length: {len(decoded_credential_id)} bytes")
        logger.info(
            f"Decoded credential_id (hex): {decoded_credential_id.hex()}")

        # Test re-encoding to verify integrity
        re_encoded = base64.b64encode(decoded_credential_id).decode('utf-8')
        logger.info(f"Re-encoded credential_id: {re_encoded}")
        logger.info(
            f"Original vs re-encoded match: {serializer.validated_data['credential_id'] == re_encoded}")

        # Test urlsafe encoding
        urlsafe_encoded = base64.urlsafe_b64encode(
            decoded_credential_id).decode('utf-8').rstrip('=')
        logger.info(f"URL-safe encoded credential_id: {urlsafe_encoded}")
        logger.info(
            f"Original vs urlsafe match: {serializer.validated_data['credential_id'] == urlsafe_encoded}")

        # Create the credential object with the correct structure
        from webauthn.helpers import bytes_to_base64url
        credential_id_base64url = bytes_to_base64url(decoded_credential_id)
        logger.info(f"Converted credential_id to base64url: {credential_id_base64url}")
        
        # Create the authenticator assertion response
        authenticator_assertion_response = AuthenticatorAssertionResponse(
            authenticator_data=base64.b64decode(
                serializer.validated_data['authenticator_data']),
            client_data_json=base64.b64decode(
                serializer.validated_data['client_data_json']),
            signature=base64.b64decode(
                serializer.validated_data['signature']),
        )
        logger.info("AuthenticatorAssertionResponse created successfully")
        
        credential_obj = AuthenticationCredential(
            id=credential_id_base64url,  # Use base64url format
            raw_id=decoded_credential_id,  # Use decoded bytes
            response=authenticator_assertion_response,
            type="public-key",
        )
        logger.info("AuthenticationCredential created successfully")
        logger.info(f"Credential ID type: {type(credential_obj.id)}")
        logger.info(f"Credential ID value: {credential_obj.id}")
        logger.info(f"Credential raw_id type: {type(credential_obj.raw_id)}")
        logger.info(
            f"Credential raw_id length: {len(credential_obj.raw_id)} bytes")
        logger.info(f"Credential raw_id (hex): {credential_obj.raw_id.hex()}")
        logger.info(f"Credential type: {credential_obj.type}")
        
        # Verify that base64url encoding of raw_id matches id
        raw_id_encoded = bytes_to_base64url(credential_obj.raw_id)
        logger.info(f"Base64url encoding of raw_id: {raw_id_encoded}")
        logger.info(f"ID and base64url(raw_id) match: {credential_obj.id == raw_id_encoded}")
        logger.info(f"ID and raw_id have correct types: {isinstance(credential_obj.id, str) and isinstance(credential_obj.raw_id, bytes)}")
        
        logger.info("Starting verification with webauthn library...")
        verification = verify_authentication_response(
            credential=credential_obj,
            expected_rp_id=settings.WEBAUTHN_RP_ID,
            expected_origin=settings.WEBAUTHN_RP_ORIGIN,
            expected_challenge=base64.b64decode(challenge),
            credential_public_key=base64.b64decode(credential.public_key),
            credential_current_sign_count=credential.sign_count,
        )

        logger.info("=== Authentication Verification Successful ===")
        logger.info(f"Verification object: {verification}")
        logger.info(f"New sign count: {verification.new_sign_count}")
        logger.info(f"Previous sign count: {credential.sign_count}")

        # Update credential
        credential.sign_count = verification.new_sign_count
        credential.update_last_used()
        credential.save()
        logger.info(
            f"Credential updated - new sign count: {credential.sign_count}")

        # Login user
        login(request, user)
        logger.info(f"User {user.username} logged in successfully")

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        logger.info("JWT tokens generated successfully")

        # Clear the challenge
        del webauthn_challenges[challenge_id]
        logger.info(f"Challenge {challenge_id} removed from memory")
        logger.info(f"Remaining challenges: {len(webauthn_challenges)}")

        response_data = {
            'message': 'Authentication successful',
            'user': UserSerializer(user).data,
            'tokens': {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            }
        }

        logger.info("=== WebAuthn Authentication Complete Success ===")
        logger.info(f"Response data: {response_data}")

        return Response(response_data)

    except Exception as e:
        import traceback
        logger.error(f"Authentication verification failed: {str(e)}")
        logger.error(f"Exception type: {type(e).__name__}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return Response({
            'error': f'Authentication verification failed: {str(e)}'
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    """Get current user profile"""
    logger.info(f"=== User Profile Access ===")
    logger.info(
        f"User accessing profile: {request.user.username} (ID: {request.user.id})")

    serializer = UserSerializer(request.user)
    response_data = serializer.data
    logger.info(f"Profile data retrieved: {response_data}")

    return Response(response_data)
