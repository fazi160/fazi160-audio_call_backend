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

# Create your views here.

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
    """Get call history for the authenticated user"""
    try:
        # Get query parameters for filtering
        status_filter = request.GET.get("status")
        contact_id = request.GET.get("contact_id")
        date_from = request.GET.get("date_from")
        date_to = request.GET.get("date_to")
        search = request.GET.get("search")
        
        # Start with user's calls
        calls = Call.objects.filter(user=request.user).order_by('-created_at')
        
        # Apply filters
        if status_filter:
            calls = calls.filter(call_status=status_filter)
        
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
        call = Call.objects.get(id=call_id, user=request.user)
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
        call = Call.objects.get(id=call_id, user=request.user)
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

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def call_statistics(request):
    """Get call statistics for the authenticated user"""
    try:
        from django.db.models import Count, Avg, Sum
        from django.utils import timezone
        from datetime import timedelta
        
        # Get date range (default to last 30 days)
        days = int(request.GET.get("days", 30))
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Get calls in date range
        calls = Call.objects.filter(
            user=request.user,
            created_at__range=(start_date, end_date)
        )
        
        # Calculate statistics
        total_calls = calls.count()
        completed_calls = calls.filter(call_status="completed").count()
        failed_calls = calls.filter(call_status="failed").count()
        initiated_calls = calls.filter(call_status="initiated").count()
        
        # Average call duration
        avg_duration = calls.filter(call_duration__gt=0).aggregate(
            avg_duration=Avg('call_duration')
        )['avg_duration'] or 0
        
        # Total call duration
        total_duration = calls.aggregate(
            total_duration=Sum('call_duration')
        )['total_duration'] or 0
        
        # Calls by status
        status_breakdown = calls.values('call_status').annotate(
            count=Count('id')
        )
        
        return Response({
            "statistics": {
                "total_calls": total_calls,
                "completed_calls": completed_calls,
                "failed_calls": failed_calls,
                "initiated_calls": initiated_calls,
                "avg_duration_seconds": round(avg_duration, 2),
                "total_duration_seconds": total_duration,
                "success_rate": round((completed_calls / total_calls * 100) if total_calls > 0 else 0, 2),
                "status_breakdown": list(status_breakdown),
                "date_range": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "days": days
                }
            },
            "status": "success"
        })
        
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
    
    response = VoiceResponse()
    direction = request.POST.get("Direction")
    to_target = request.POST.get("To") or request.POST.get("to")
    call_sid = request.POST.get("CallSid")
    from_number = request.POST.get("From")
    account_sid = request.POST.get("AccountSid")



    if direction == "outbound-api":
        # Outgoing call from web client

        
        # Try to find contact by number
        contact = None
        if to_target:
            try:
                contact = Contact.objects.filter(phone_number__icontains=to_target).first()
            except Exception:
                contact = None
        
        # Try to find the user (fallback to first user if not found)
        user = User.objects.first()
        
        # Only create if not already exists
        if call_sid and not Call.objects.filter(call_sid=call_sid).exists():
            Call.objects.create(
                contact=contact,
                contact_number=to_target,
                user=user,
                call_status="initiated",
                call_start_time=datetime.now(),
                call_sid=call_sid,
            )
        
        if not to_target:
            response.say("Sorry, we need a 'To' destination to connect your call.")
            return HttpResponse(str(response), content_type='application/xml')
        
        dial = Dial(caller_id=os.getenv("TWILIO_CALLER_ID"))
        dial.number(to_target)
        response.append(dial)
        
    elif direction == "inbound":

        
        # Check if this is a call from Twilio Client (browser) to a phone number
        if from_number and from_number.startswith("client:"):
            dial = Dial(caller_id=os.getenv("TWILIO_CALLER_ID"))
            dial.number(to_target)
            response.append(dial)
        else:
            # This is a real incoming call from a phone number to your Twilio number
            
            # Try to find contact by phone number
            contact = None
            if from_number:
                try:
                    # Remove any country code formatting for better matching
                    clean_number = from_number.replace('+', '').replace('-', '').replace('(', '').replace(')', '').replace(' ', '')
                    contact = Contact.objects.filter(
                        phone_number__icontains=clean_number[-10:]  # Match last 10 digits
                    ).first()
                except Exception as e:
                    contact = None
            
            # Get user (fallback to first user)
            user = User.objects.first()
            
            # Create call record if it doesn't exist
            if call_sid and not Call.objects.filter(call_sid=call_sid).exists():
                try:
                    Call.objects.create(
                        contact=contact,
                        contact_number=from_number,
                        user=user,
                        call_status="ringing",
                        call_start_time=datetime.now(),
                        call_sid=call_sid,
                    )
                except Exception as e:
                    pass
            # Forward the call to your Twilio Client (browser/dashboard)
            dial = Dial(timeout=30, record="record-from-ringing")
            dial.client("dashboard")  # This should match your client identifier
            response.append(dial)
            
            # Optional: Add a fallback message if no one answers
            response.say("Sorry, no one is available to take your call right now. Please try again later.")
    else:
        # Fallback for unknown direction
        response.say("Sorry, we could not process your call.")
    
    return HttpResponse(str(response), content_type='application/xml')

@csrf_exempt
def voice_fallback(request):
    """Fallback handler for TwiML App."""
    response = VoiceResponse()
    response.say("Sorry, we are unable to process your call at the moment. Please try again later.")
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
def incoming_call_webhook(request):
    """Handle incoming call webhook from Twilio."""
    try:
        # Get incoming call details
        call_sid = request.POST.get("CallSid")
        from_number = request.POST.get("From")
        to_number = request.POST.get("To")
        
        
        # Try to find contact by phone number
        contact = None
        try:
            # Remove + and any formatting from phone number
            clean_number = from_number.replace("+", "").replace("-", "").replace(" ", "")
            contact = Contact.objects.get(phone_number__icontains=clean_number)
        except Contact.DoesNotExist:
            pass
        
        # Create call record
        call_data = {
            "contact": contact.id if contact else None,
            "contact_number": from_number,
            "user": contact.user.id if contact else User.objects.first().id,
            "call_status": "incoming",
            "call_start_time": datetime.now(),
            "call_sid": call_sid
        }
        
        serializer = CallCreateSerializer(data=call_data)
        if serializer.is_valid():
            call = serializer.save()
        else:
            pass
        
        # Generate TwiML response
        response = VoiceResponse()
        response.say("Hello! Welcome to our calling system.")
        
        return HttpResponse(str(response), content_type='application/xml')
        
    except Exception as e:
        # Return a basic TwiML response even on error
        response = VoiceResponse()
        response.say("Thank you for calling.")
        return HttpResponse(str(response), content_type='application/xml')


