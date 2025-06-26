from rest_framework import serializers
from .models import Contact
from django.contrib.auth.models import User

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name']

class ContactSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = Contact
        fields = ['id', 'name', 'phone_number', 'email', 'created_at', 'updated_at', 'user']
        read_only_fields = ['created_at', 'updated_at', 'user']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
    
    def validate_phone_number(self, value):
        """Validate phone number format"""
        # Remove any non-digit characters except + for international format
        cleaned_number = ''.join(c for c in value if c.isdigit() or c == '+')
        
        # Basic validation - should be at least 10 digits
        digits_only = ''.join(c for c in cleaned_number if c.isdigit())
        if len(digits_only) < 10:
            raise serializers.ValidationError("Phone number must contain at least 10 digits")
        
        return cleaned_number
    
    def validate_email(self, value):
        """Validate email format"""
        if value:
            # Check if email already exists for this user
            user = self.context['request'].user
            if Contact.objects.filter(user=user, email=value).exists():
                # If updating, exclude current instance
                if self.instance:
                    if Contact.objects.filter(user=user, email=value).exclude(id=self.instance.id).exists():
                        raise serializers.ValidationError("A contact with this email already exists")
                else:
                    raise serializers.ValidationError("A contact with this email already exists")
        return value

class ContactListSerializer(serializers.ModelSerializer):
    """Simplified serializer for list views"""
    class Meta:
        model = Contact
        fields = ['id', 'name', 'phone_number', 'email', 'created_at']
        read_only_fields = ['created_at']
