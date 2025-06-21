from rest_framework import serializers
from .models import Call
from contacts.models import Contact


class CallSerializer(serializers.ModelSerializer):
    """Serializer for Call model"""
    
    contact_name = serializers.CharField(source='contact.name', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = Call
        fields = [
            'id', 'user', 'user_username', 'contact', 'contact_name',
            'phone_number', 'direction', 'status', 'twilio_sid',
            'duration', 'started_at', 'ended_at', 'notes'
        ]
        read_only_fields = ['id', 'user', 'twilio_sid', 'started_at', 'ended_at']


class MakeCallSerializer(serializers.Serializer):
    """Serializer for making a call request"""
    
    phone_number = serializers.CharField(max_length=20)
    contact_id = serializers.IntegerField(required=False, allow_null=True)
    
    def validate_phone_number(self, value):
        """Validate phone number format"""
        # Remove any non-digit characters except + for international numbers
        cleaned = ''.join(c for c in value if c.isdigit() or c == '+')
        
        if not cleaned:
            raise serializers.ValidationError("Phone number must contain digits")
        
        # Basic validation - should start with + for international or be 10+ digits
        if cleaned.startswith('+'):
            if len(cleaned) < 8:  # Minimum international number length
                raise serializers.ValidationError("International phone number too short")
        else:
            if len(cleaned) < 10:  # Minimum US number length
                raise serializers.ValidationError("Phone number must be at least 10 digits")
        
        return cleaned
    
    def validate_contact_id(self, value):
        """Validate contact exists if provided"""
        if value is not None:
            try:
                Contact.objects.get(id=value)
            except Contact.DoesNotExist:
                raise serializers.ValidationError("Contact does not exist")
        return value


class CallStatusSerializer(serializers.Serializer):
    """Serializer for call status response"""
    
    sid = serializers.CharField()
    status = serializers.CharField()
    duration = serializers.IntegerField(allow_null=True)
    direction = serializers.CharField()
    from_ = serializers.CharField()
    to = serializers.CharField()
    start_time = serializers.DateTimeField(allow_null=True)
    end_time = serializers.DateTimeField(allow_null=True)
    price = serializers.CharField(allow_null=True)
    price_unit = serializers.CharField(allow_null=True)


class TwilioWebhookSerializer(serializers.Serializer):
    """Serializer for Twilio webhook data"""
    
    CallSid = serializers.CharField()
    CallStatus = serializers.CharField()
    CallDuration = serializers.CharField(required=False, allow_blank=True)
    From = serializers.CharField(required=False)
    To = serializers.CharField(required=False)
    Direction = serializers.CharField(required=False)
    
    # Additional webhook fields that might be useful
    AnsweredBy = serializers.CharField(required=False, allow_blank=True)
    CallerName = serializers.CharField(required=False, allow_blank=True)
    Timestamp = serializers.CharField(required=False, allow_blank=True) 