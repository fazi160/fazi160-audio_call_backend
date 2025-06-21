from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from .models import WebAuthnCredential


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration"""
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'password', 'password_confirm']
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Passwords don't match")
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = User.objects.create_user(**validated_data)
        return user


class UserSerializer(serializers.ModelSerializer):
    """Serializer for user profile"""
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'date_joined']
        read_only_fields = ['id', 'date_joined']


class WebAuthnCredentialSerializer(serializers.ModelSerializer):
    """Serializer for WebAuthn credentials"""
    class Meta:
        model = WebAuthnCredential
        fields = ['id', 'credential_id', 'sign_count', 'transports', 'backup_eligible', 'backup_state', 'created_at', 'last_used_at']
        read_only_fields = ['id', 'created_at', 'last_used_at']


class WebAuthnRegistrationBeginSerializer(serializers.Serializer):
    """Serializer for WebAuthn registration begin"""
    username = serializers.CharField()
    display_name = serializers.CharField(required=False)


class WebAuthnRegistrationCompleteSerializer(serializers.Serializer):
    """Serializer for WebAuthn registration complete"""
    username = serializers.CharField()
    credential_id = serializers.CharField()
    attestation_object = serializers.CharField()
    client_data_json = serializers.CharField()
    transports = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    backup_eligible = serializers.BooleanField(required=False, default=False)
    backup_state = serializers.BooleanField(required=False, default=False)


class WebAuthnAuthenticationBeginSerializer(serializers.Serializer):
    """Serializer for WebAuthn authentication begin"""
    username = serializers.CharField()


class WebAuthnAuthenticationCompleteSerializer(serializers.Serializer):
    """Serializer for WebAuthn authentication complete"""
    username = serializers.CharField()
    credential_id = serializers.CharField()
    authenticator_data = serializers.CharField()
    client_data_json = serializers.CharField()
    signature = serializers.CharField() 