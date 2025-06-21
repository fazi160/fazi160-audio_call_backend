import logging
from twilio.rest import Client
from twilio.base.exceptions import TwilioException
from django.conf import settings
from django.utils import timezone
from .models import Call
from contacts.models import Contact

logger = logging.getLogger(__name__)

class TwilioService:
    """Service class for handling Twilio voice calls"""
    
    def __init__(self):
        self.account_sid = settings.TWILIO_ACCOUNT_SID
        self.auth_token = settings.TWILIO_AUTH_TOKEN
        self.from_number = settings.TWILIO_PHONE_NUMBER
        
        if not all([self.account_sid, self.auth_token, self.from_number]):
            raise ValueError("Twilio credentials not properly configured")
        
        self.client = Client(self.account_sid, self.auth_token)
    
    def make_call(self, to_number, user, contact=None, webhook_url=None):
        """
        Initiate a call to the specified number
        
        Args:
            to_number (str): Phone number to call
            user: Django User object
            contact: Contact object (optional)
            webhook_url (str): URL for Twilio webhooks (optional)
        
        Returns:
            Call object
        """
        try:
            # Create call record in database
            call = Call.objects.create(
                user=user,
                contact=contact,
                phone_number=to_number,
                direction='outbound',
                status='initiated'
            )
            
            # Prepare Twilio call parameters
            call_params = {
                'to': to_number,
                'from_': self.from_number,
                'url': webhook_url or self._get_default_twiml_url(),
                'method': 'POST',
                'status_callback': self._get_status_callback_url(),
                'status_callback_event': ['initiated', 'ringing', 'answered', 'completed'],
                'status_callback_method': 'POST',
                'record': False,  # Set to True if you want to record calls
                'timeout': 30,  # Ring timeout in seconds
            }
            
            # Make the call via Twilio
            twilio_call = self.client.calls.create(**call_params)
            
            # Update call record with Twilio SID
            call.twilio_sid = twilio_call.sid
            call.status = 'ringing'
            call.save()
            
            logger.info(f"Call initiated: {call.id} -> {to_number} (Twilio SID: {twilio_call.sid})")
            
            return call
            
        except TwilioException as e:
            logger.error(f"Twilio error making call to {to_number}: {str(e)}")
            if 'call' in locals():
                call.status = 'failed'
                call.notes = f"Twilio error: {str(e)}"
                call.save()
            raise Exception(f"Failed to make call: {str(e)}")
        
        except Exception as e:
            logger.error(f"Error making call to {to_number}: {str(e)}")
            if 'call' in locals():
                call.status = 'failed'
                call.notes = f"Error: {str(e)}"
                call.save()
            raise
    
    def end_call(self, call_sid):
        """
        End an active call
        
        Args:
            call_sid (str): Twilio call SID
        
        Returns:
            bool: True if successful
        """
        try:
            # End call via Twilio
            call = self.client.calls(call_sid).update(status='completed')
            
            # Update database record
            try:
                db_call = Call.objects.get(twilio_sid=call_sid)
                db_call.status = 'completed'
                db_call.ended_at = timezone.now()
                db_call.save()
            except Call.DoesNotExist:
                logger.warning(f"Call record not found for Twilio SID: {call_sid}")
            
            logger.info(f"Call ended: {call_sid}")
            return True
            
        except TwilioException as e:
            logger.error(f"Twilio error ending call {call_sid}: {str(e)}")
            raise Exception(f"Failed to end call: {str(e)}")
    
    def get_call_status(self, call_sid):
        """
        Get current status of a call from Twilio
        
        Args:
            call_sid (str): Twilio call SID
        
        Returns:
            dict: Call status information
        """
        try:
            call = self.client.calls(call_sid).fetch()
            
            # Update database record
            try:
                db_call = Call.objects.get(twilio_sid=call_sid)
                db_call.status = self._map_twilio_status(call.status)
                if call.duration:
                    db_call.duration = int(call.duration)
                if call.end_time:
                    db_call.ended_at = call.end_time
                db_call.save()
            except Call.DoesNotExist:
                logger.warning(f"Call record not found for Twilio SID: {call_sid}")
            
            return {
                'sid': call.sid,
                'status': call.status,
                'duration': call.duration,
                'direction': call.direction,
                'from_': call.from_,
                'to': call.to,
                'start_time': call.start_time,
                'end_time': call.end_time,
                'price': call.price,
                'price_unit': call.price_unit,
            }
            
        except TwilioException as e:
            logger.error(f"Twilio error getting call status {call_sid}: {str(e)}")
            raise Exception(f"Failed to get call status: {str(e)}")
    
    def handle_webhook(self, webhook_data):
        """
        Handle Twilio webhook data
        
        Args:
            webhook_data (dict): Webhook data from Twilio
        
        Returns:
            bool: True if handled successfully
        """
        try:
            call_sid = webhook_data.get('CallSid')
            call_status = webhook_data.get('CallStatus')
            call_duration = webhook_data.get('CallDuration')
            
            if not call_sid:
                logger.warning("Webhook received without CallSid")
                return False
            
            # Update database record
            try:
                call = Call.objects.get(twilio_sid=call_sid)
                call.status = self._map_twilio_status(call_status)
                
                if call_duration:
                    call.duration = int(call_duration)
                
                if call_status in ['completed', 'failed', 'busy', 'no-answer', 'canceled']:
                    call.ended_at = timezone.now()
                
                call.save()
                
                # Update contact's last_contacted if this is a completed outbound call
                if call.contact and call.direction == 'outbound' and call_status == 'completed':
                    call.contact.last_contacted = timezone.now()
                    call.contact.save()
                
                logger.info(f"Webhook processed for call {call_sid}: {call_status}")
                return True
                
            except Call.DoesNotExist:
                logger.warning(f"Call record not found for webhook CallSid: {call_sid}")
                return False
            
        except Exception as e:
            logger.error(f"Error processing webhook: {str(e)}")
            return False
    
    def _map_twilio_status(self, twilio_status):
        """Map Twilio status to our internal status"""
        status_mapping = {
            'queued': 'initiated',
            'initiated': 'initiated',
            'ringing': 'ringing',
            'answered': 'in-progress',
            'in-progress': 'in-progress',
            'completed': 'completed',
            'failed': 'failed',
            'busy': 'busy',
            'no-answer': 'no-answer',
            'canceled': 'canceled',
        }
        return status_mapping.get(twilio_status, twilio_status)
    
    def _get_default_twiml_url(self):
        """Get default TwiML URL for voice calls"""
        # This should be your server's URL + the TwiML endpoint
        # For now, we'll use a simple TwiML that plays a message
        base_url = getattr(settings, 'BASE_URL', 'http://localhost:8000')
        
        # For local development, use a public TwiML URL if BASE_URL is localhost
        if 'localhost' in base_url or '127.0.0.1' in base_url:
            # Use Twilio's demo TwiML for testing (you can replace with your ngrok URL)
            return "http://demo.twilio.com/docs/voice.xml"
        
        return f"{base_url}/api/dialer/twiml/voice/"
    
    def _get_status_callback_url(self):
        """Get status callback URL for webhooks"""
        base_url = getattr(settings, 'BASE_URL', 'http://localhost:8000')
        return f"{base_url}/api/dialer/webhook/twilio/"

# Utility function to get TwilioService instance
def get_twilio_service():
    """Get configured TwilioService instance"""
    return TwilioService() 