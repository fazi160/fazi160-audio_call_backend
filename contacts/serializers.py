from rest_framework import serializers
from .models import Contact


class ContactSerializer(serializers.ModelSerializer):
    """Serializer for Contact model"""
    
    class Meta:
        model = Contact
        fields = [
            'id', 'name', 'phone', 'email', 'notes', 
            'tags', 'last_contacted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        """Create a new contact for the current user"""
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
    
    def validate_phone(self, value):
        """Validate phone number format"""
        # Basic phone number validation - can be enhanced
        if not value.replace('+', '').replace('-', '').replace(' ', '').replace('(', '').replace(')', '').isdigit():
            raise serializers.ValidationError("Phone number must contain only digits and common separators")
        return value
    
    def validate_tags(self, value):
        """Validate tags format"""
        if not isinstance(value, list):
            raise serializers.ValidationError("Tags must be a list")
        # Ensure all tags are strings
        return [str(tag) for tag in value]


class ContactListSerializer(serializers.ModelSerializer):
    """Simplified serializer for contact lists"""
    
    class Meta:
        model = Contact
        fields = ['id', 'name', 'phone', 'email', 'tags', 'last_contacted'] 