from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class WebAuthnCredential(models.Model):
    """WebAuthn credential model for storing passkey information"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='webauthn_credentials')
    credential_id = models.CharField(max_length=255, unique=True)
    public_key = models.TextField()
    sign_count = models.BigIntegerField(default=0)
    transports = models.JSONField(default=list, blank=True)  # List of supported transports
    backup_eligible = models.BooleanField(default=False)
    backup_state = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Credential for {self.user.username} ({self.credential_id[:20]}...)"
    
    def update_last_used(self):
        """Update the last used timestamp"""
        self.last_used_at = timezone.now()
        self.save(update_fields=['last_used_at'])
    
    def increment_sign_count(self):
        """Increment the signature count"""
        self.sign_count += 1
        self.save(update_fields=['sign_count'])
