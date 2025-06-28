import random
from django.shortcuts import render
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant
import os
from datetime import datetime
import json
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from twilio.twiml.voice_response import VoiceResponse, Dial
from .models import Call, Note
from .serializers import CallSerializer, CallCreateSerializer, CallHistorySerializer, NoteSerializer
from contact.models import Contact
from django.contrib.auth.models import User
from django.db.models import Q
import logging

# Create your views here.

logging.basicConfig(level=logging.INFO)
logging.info("This will always show up in Render logs")

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_token(request):
    """Generate Twilio access token for voice calls"""
    identity = request.GET.get("identity", request.user.username)
    

    try:
        token = AccessToken(
            os.getenv("TWILIO_ACCOUNT_SID"),
            os.getenv("TWILIO_API_KEY"),
            os.getenv("TWILIO_API_SECRET"),
            identity=identity,
        )
        
        voice_grant = VoiceGrant(
            outgoing_application_sid=os.getenv("TWIML_APP_SID"),
            incoming_allow=True
        )
        token.add_grant(voice_grant)
        
        
        return Response({
            "token": token.to_jwt(),
            "identity": identity,
            "status": "success"
        })
    except Exception as e:
        return Response({
            "error": str(e),
            "status": "error"
        }, status=500)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def call_history(request):
    """Get all call history (no user filtering)"""
    try:
        # Get query parameters for filtering
        status_filter = request.GET.get("status")
        contact_id = request.GET.get("contact_id")
        date_from = request.GET.get("date_from")
        date_to = request.GET.get("date_to")
        search = request.GET.get("search")
        call_direction = request.GET.get("call_direction") or request.GET.get("direction")
        
        # Start with all calls (no user filtering)
        calls = Call.objects.all().order_by('-created_at')
        
        # Apply filters
        if status_filter:
            calls = calls.filter(call_status=status_filter)

        if call_direction:
            calls = calls.filter(call_direction=call_direction)   

        if contact_id:
            calls = calls.filter(contact_id=contact_id)
        
        if date_from:
            try:
                date_from = datetime.strptime(date_from, "%Y-%m-%d")
                calls = calls.filter(created_at__date__gte=date_from.date())
            except ValueError:
                pass
        
        if date_to:
            try:
                date_to = datetime.strptime(date_to, "%Y-%m-%d")
                calls = calls.filter(created_at__date__lte=date_to.date())
            except ValueError:
                pass
        
        if search:
            calls = calls.filter(
                Q(contact__name__icontains=search) |
                Q(contact_number__icontains=search) |
                Q(contact__phone_number__icontains=search)
            )
        
        # Pagination
        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 20))
        start = (page - 1) * page_size
        end = start + page_size
        
        total_calls = calls.count()
        calls_page = calls[start:end]
        
        serializer = CallHistorySerializer(calls_page, many=True)
        
        return Response({
            "calls": serializer.data,
            "total": total_calls,
            "page": page,
            "page_size": page_size,
            "total_pages": (total_calls + page_size - 1) // page_size,
            "status": "success"
        })
        
    except Exception as e:
        return Response({
            "error": str(e),
            "status": "error"
        }, status=500)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def call_detail(request, call_id):
    """Get detailed information about a specific call"""
    try:
        call = Call.objects.get(id=call_id)
        serializer = CallSerializer(call)
        
        return Response({
            "call": serializer.data,
            "status": "success"
        })
        
    except Call.DoesNotExist:
        return Response({
            "error": "Call not found",
            "status": "error"
        }, status=404)
    except Exception as e:
        return Response({
            "error": str(e),
            "status": "error"
        }, status=500)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def add_note(request, call_id):
    """Add a note to a call"""
    try:
        call = Call.objects.get(id=call_id)
        note_text = request.data.get("note")
        
        if not note_text:
            return Response({
                "error": "Note text is required",
                "status": "error"
            }, status=400)
        
        note = Note.objects.create(call=call, note=note_text)
        serializer = NoteSerializer(note)
        
        return Response({
            "note": serializer.data,
            "status": "success"
        })
        
    except Call.DoesNotExist:
        return Response({
            "error": "Call not found",
            "status": "error"
        }, status=404)
    except Exception as e:
        return Response({
            "error": str(e),
            "status": "error"
        }, status=500)



@csrf_exempt
def voice_handler(request):
    """Unified handler for both incoming and outgoing calls."""
    from django.contrib.auth.models import User
    from contact.models import Contact

    logger = logging.getLogger("call.voice_handler")

    logger.info("=== Twilio Voice Handler Called ===")
    logger.info(f"Request method: {request.method}")
    logger.info(f"Request POST data: {dict(request.POST)}")

    response = VoiceResponse()
    direction = request.POST.get("Direction")
    to_target = request.POST.get("To") or request.POST.get("to")
    call_sid = request.POST.get("CallSid")
    from_number = request.POST.get("From")
    account_sid = request.POST.get("AccountSid")

    # Extract custom parameters sent from frontend
    user_id = request.POST.get("UserId")
    if user_id:
        logger.info(f"User ID 11111111111111111111111111111111111111111111111111111111: {user_id}")
    else:
        logger.info("No User ID provided 11111111111111111111111111111111111111111111111111111111")

    # Log custom parameters
    logger.info(f"Custom Parameters - UserId: {user_id}")

    logger.info(f"Direction: {direction}, To: {to_target}, From: {from_number}, CallSid: {call_sid}, AccountSid: {account_sid}")

    if direction == "outbound-api":
        logger.info("Handling outbound-api (outgoing call from web client)")
        # Try to find contact by number
        contact = None
        if to_target:
            try:
                contact = Contact.objects.filter(phone_number__icontains=to_target).first()
                logger.info(f"Contact found for {to_target}: {contact}")
            except Exception as e:
                logger.warning(f"Error finding contact: {e}")
                contact = None

        # Only create if not already exists
        if call_sid and not Call.objects.filter(call_sid=call_sid).exists():
            # Create call record with custom parameters
            call_data = {
                'contact': contact,
                'contact_number': to_target,
                'call_status': "initiated",
                'call_start_time': datetime.now(),
                'call_sid': call_sid,
                'call_direction': "outgoing",
            }
            if user_id:
                call_data['user'] = user_id

            Call.objects.create(**call_data)
            logger.info(f"Call record created for outgoing call: {call_sid}")

        if not to_target:
            logger.warning("No 'To' destination provided.")
            response.say("Sorry, we need a 'To' destination to connect your call.")
            return HttpResponse(str(response), content_type='application/xml')

        dial = Dial(caller_id=os.getenv("TWILIO_CALLER_ID"))
        dial.number(to_target)
        response.append(dial)
        logger.info(f"Dialing out to {to_target}")

    elif direction == "inbound":
        logger.info("Handling inbound call")
        # Check if this is a call from Twilio Client (browser) to a phone number
        if from_number and from_number.startswith("client:"):
            logger.info("Inbound call from Twilio Client")
            
            # Create call record for Twilio Client calls
            # Try to find contact by number
            contact = None
            if to_target:
                try:
                    contact = Contact.objects.filter(phone_number__icontains=to_target).first()
                    logger.info(f"Contact found for {to_target}: {contact}")
                except Exception as e:
                    logger.warning(f"Error finding contact: {e}")
                    contact = None
            
            if call_sid and not Call.objects.filter(call_sid=call_sid).exists():
                try:
                    # Create call record with custom parameters
                    call_data = {
                        'contact': contact,
                        'contact_number': to_target,
                        'call_status': "ringing",
                        'call_start_time': datetime.now(),
                        'call_sid': call_sid,
                        'call_direction': "outgoing",  # This is outgoing from the client's perspective
                    }
                    if user_id:
                        call_data['user'] = user_id

                    Call.objects.create(**call_data)
                    logger.info(f"Call record created for Twilio Client call: {call_sid}")
                except Exception as e:
                    logger.warning(f"Error creating call record: {e}")
            
            dial = Dial(caller_id=os.getenv("TWILIO_CALLER_ID"))
            dial.number(to_target)
            response.append(dial)
            logger.info(f"Dialing number {to_target} from client")
        else:
            logger.info("Inbound call from real phone number")
            # Try to find contact by phone number
            contact = None
            if from_number:
                try:
                    clean_number = from_number.replace('+', '').replace('-', '').replace('(', '').replace(')', '').replace(' ', '')
                    contact = Contact.objects.filter(
                        phone_number__icontains=clean_number[-10:]
                    ).first()
                    logger.info(f"Contact found for {from_number}: {contact}")
                except Exception as e:
                    logger.warning(f"Error finding contact: {e}")
                    contact = None

            if call_sid and not Call.objects.filter(call_sid=call_sid).exists():
                try:
                    # Create call record with custom parameters
                    call_data = {
                        'contact': contact,
                        'contact_number': from_number,
                        'call_status': "ringing",
                        'call_start_time': datetime.now(),
                        'call_sid': call_sid,
                        'call_direction': "incoming",
                    }
                    if user_id:
                        call_data['user'] = user_id

                    Call.objects.create(**call_data)
                    logger.info(f"Call record created for incoming call: {call_sid}")
                except Exception as e:
                    logger.warning(f"Error creating call record: {e}")

            dial = Dial(timeout=30, record="record-from-ringing")
            dial.client("dashboard")
            response.append(dial)
            logger.info("Forwarding call to dashboard client")

            response.say("Sorry, no one is available to take your call right now. Please try again later.")
    else:
        logger.warning("Unknown direction or missing parameters")
        response.say("Sorry, we could not process your call.")

    logger.info("Returning TwiML response:")
    logger.info(str(response))
    return HttpResponse(str(response), content_type='application/xml')


@csrf_exempt
def voice_status_callback(request):
    """Handle call status updates from Twilio (same as previous logic)."""
    try:
        call_sid = request.POST.get("CallSid")
        call_status = request.POST.get("CallStatus")
        call_duration = request.POST.get("CallDuration", 0)
        from_number = request.POST.get("From")
        to_number = request.POST.get("To")
        if call_sid:
            try:
                call = Call.objects.get(call_sid=call_sid)
                call.call_status = call_status or call.call_status
                call.call_duration = int(call_duration) if call_duration else call.call_duration
                if call_status == "completed":
                    from datetime import datetime
                    call.call_end_time = datetime.now()
                call.save()
            except Call.DoesNotExist:
                pass
        return HttpResponse("", status=200)
    except Exception as e:
        return HttpResponse("", status=500)


@csrf_exempt
def voice_fallback(request):
    """Fallback handler for TwiML App."""
    response = VoiceResponse()
    response.say("Sorry, we are unable to process your call at the moment. Please try again later.")
    return HttpResponse(str(response), content_type='application/xml')