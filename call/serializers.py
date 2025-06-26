from rest_framework import serializers
from .models import Call, Note
from contact.models import Contact
from django.contrib.auth.models import User

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name']

class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = ['id', 'name', 'phone_number', 'email']

class NoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Note
        fields = ['id', 'note', 'created_at', 'updated_at']

class CallSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    contact = ContactSerializer(read_only=True)
    notes = NoteSerializer(many=True, read_only=True)
    display_name = serializers.SerializerMethodField()
    display_number = serializers.SerializerMethodField()
    
    class Meta:
        model = Call
        fields = [
            'id', 'contact', 'contact_number', 'user', 'created_at', 
            'updated_at', 'call_status', 'call_duration', 'call_start_time', 
            'call_end_time', 'call_sid', 'display_name', 'display_number', 'notes', 'call_direction'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_display_name(self, obj):
        """Return contact name if contact exists, otherwise return 'Unknown Contact'"""
        if obj.contact:
            return obj.contact.name
        return "Unknown Contact"
    
    def get_display_number(self, obj):
        """Return contact number from contact if exists, otherwise return contact_number"""
        if obj.contact:
            return obj.contact.phone_number
        return obj.contact_number

class CallCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Call
        fields = [
            'contact', 'contact_number', 'user', 'call_status', 
                'call_duration', 'call_start_time', 'call_end_time', 'call_sid'
        ]
    
    def validate(self, data):
        """Validate that either contact or contact_number is provided"""
        if not data.get('contact') and not data.get('contact_number'):
            raise serializers.ValidationError("Either contact or contact_number must be provided")
        return data

class CallHistorySerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    contact = ContactSerializer(read_only=True)
    display_name = serializers.SerializerMethodField()
    display_number = serializers.SerializerMethodField()
    duration_formatted = serializers.SerializerMethodField()
    
    class Meta:
        model = Call
        fields = [
            'id', 'contact', 'contact_number', 'user', 'created_at', 
            'call_status', 'call_duration', 'call_start_time', 
            'call_end_time', 'display_name', 'display_number', 'duration_formatted', 
            'call_direction'
        ]
    
    def get_display_name(self, obj):
        """Return contact name if contact exists, otherwise return 'Unknown Contact'"""
        if obj.contact:
            return obj.contact.name
        return "Unknown Contact"
    
    def get_display_number(self, obj):
        """Return contact number from contact if exists, otherwise return contact_number"""
        if obj.contact:
            return obj.contact.phone_number
        return obj.contact_number
    
    def get_duration_formatted(self, obj):
        """Format call duration in minutes:seconds format"""
        if obj.call_duration:
            minutes = obj.call_duration // 60
            seconds = obj.call_duration % 60
            return f"{minutes:02d}:{seconds:02d}"
        return "00:00"
