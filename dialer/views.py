import logging
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from twilio.twiml.voice_response import VoiceResponse
from .services import get_twilio_service
from .models import Call
from .serializers import (
    MakeCallSerializer, CallSerializer, CallStatusSerializer, 
    TwilioWebhookSerializer
)
from contacts.models import Contact

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiate_call(request):
    """Initiate a call to the specified phone number"""
    
    serializer = MakeCallSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    phone_number = serializer.validated_data['phone_number']
    contact_id = serializer.validated_data.get('contact_id')
    
    try:
        # Get contact if provided
        contact = None
        if contact_id:
            try:
                contact = Contact.objects.get(id=contact_id, user=request.user)
            except Contact.DoesNotExist:
                return Response(
                    {'error': 'Contact not found or not owned by user'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # Initialize Twilio service and make call
        twilio_service = get_twilio_service()
        call = twilio_service.make_call(
            to_number=phone_number,
            user=request.user,
            contact=contact
        )
        
        # Serialize and return call data
        call_serializer = CallSerializer(call)
        return Response({
            'message': 'Call initiated successfully',
            'call': call_serializer.data
        }, status=status.HTTP_201_CREATED)
        
    except ValueError as e:
        return Response(
            {'error': f'Configuration error: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    except Exception as e:
        logger.error(f"Error initiating call: {str(e)}")
        return Response(
            {'error': f'Failed to initiate call: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def call_status(request, call_sid):
    """Get the current status of a call"""
    
    try:
        # Check if user owns this call
        try:
            call = Call.objects.get(twilio_sid=call_sid, user=request.user)
        except Call.DoesNotExist:
            return Response(
                {'error': 'Call not found or not owned by user'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get status from Twilio
        twilio_service = get_twilio_service()
        twilio_status = twilio_service.get_call_status(call_sid)
        
        # Also return our database record
        call_serializer = CallSerializer(call)
        
        return Response({
            'twilio_status': twilio_status,
            'call_record': call_serializer.data
        })
        
    except Exception as e:
        logger.error(f"Error getting call status: {str(e)}")
        return Response(
            {'error': f'Failed to get call status: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def end_call(request, call_sid):
    """End an active call"""
    
    try:
        # Check if user owns this call
        try:
            call = Call.objects.get(twilio_sid=call_sid, user=request.user)
        except Call.DoesNotExist:
            return Response(
                {'error': 'Call not found or not owned by user'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # End call via Twilio
        twilio_service = get_twilio_service()
        success = twilio_service.end_call(call_sid)
        
        if success:
            # Refresh call data from database
            call.refresh_from_db()
            call_serializer = CallSerializer(call)
            
            return Response({
                'message': 'Call ended successfully',
                'call': call_serializer.data
            })
        else:
            return Response(
                {'error': 'Failed to end call'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
    except Exception as e:
        logger.error(f"Error ending call: {str(e)}")
        return Response(
            {'error': f'Failed to end call: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def call_history(request):
    """Get call history for the authenticated user"""
    
    try:
        # Get user's calls
        calls = Call.objects.filter(user=request.user).order_by('-started_at')
        
        # Apply pagination
        paginator = PageNumberPagination()
        paginator.page_size = 20
        result_page = paginator.paginate_queryset(calls, request)
        
        # Serialize data
        serializer = CallSerializer(result_page, many=True)
        
        return paginator.get_paginated_response(serializer.data)
        
    except Exception as e:
        logger.error(f"Error getting call history: {str(e)}")
        return Response(
            {'error': f'Failed to get call history: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@csrf_exempt
@require_http_methods(["POST"])
def twilio_webhook(request):
    """Handle Twilio webhooks for call status updates"""
    
    try:
        # Parse webhook data
        webhook_data = dict(request.POST)
        # Convert lists to single values (Twilio sends single values)
        webhook_data = {k: v[0] if isinstance(v, list) and len(v) == 1 else v 
                      for k, v in webhook_data.items()}
        
        logger.info(f"Received Twilio webhook: {webhook_data}")
        
        # Validate webhook data
        serializer = TwilioWebhookSerializer(data=webhook_data)
        if not serializer.is_valid():
            logger.warning(f"Invalid webhook data: {serializer.errors}")
            return HttpResponse("Invalid webhook data", status=400)
        
        # Process webhook
        twilio_service = get_twilio_service()
        success = twilio_service.handle_webhook(webhook_data)
        
        if success:
            return HttpResponse("OK", status=200)
        else:
            return HttpResponse("Failed to process webhook", status=400)
        
    except Exception as e:
        logger.error(f"Error processing Twilio webhook: {str(e)}")
        return HttpResponse("Internal server error", status=500)


@csrf_exempt
@require_http_methods(["POST"])
def twiml_voice(request):
    """Generate TwiML for voice calls"""
    
    try:
        # Create TwiML response
        response = VoiceResponse()
        
        # Simple message for now - you can customize this
        response.say("Hello! This is a call from your secure dashboard. Please hold while we connect you.", 
                    voice='alice', language='en-US')
        
        # You can add more TwiML verbs here:
        # - <Dial> to connect to another number
        # - <Record> to record the call
        # - <Gather> to collect DTMF input
        # - <Play> to play audio files
        
        # For now, just hang up after the message
        response.hangup()
        
        return HttpResponse(str(response), content_type='text/xml')
        
    except Exception as e:
        logger.error(f"Error generating TwiML: {str(e)}")
        # Return basic TwiML even if there's an error
        response = VoiceResponse()
        response.say("Sorry, there was an error. Goodbye.")
        response.hangup()
        return HttpResponse(str(response), content_type='text/xml')
