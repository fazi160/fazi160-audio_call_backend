from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Contact(models.Model):
    """Contact model for storing contact information"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='contacts')
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    tags = models.JSONField(default=list, blank=True)  # Store tags as a list
    last_contacted = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
        unique_together = ['user', 'phone']
    
    def __str__(self):
        return f"{self.name} ({self.phone})"
    
    def update_last_contacted(self):
        """Update the last contacted timestamp"""
        self.last_contacted = timezone.now()
        self.save(update_fields=['last_contacted'])
