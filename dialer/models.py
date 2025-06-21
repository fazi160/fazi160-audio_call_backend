from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Call(models.Model):
    """Call model for tracking call history and status"""
    
    CALL_STATUS_CHOICES = [
        ('initiated', 'Initiated'),
        ('ringing', 'Ringing'),
        ('in-progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('busy', 'Busy'),
        ('no-answer', 'No Answer'),
        ('canceled', 'Canceled'),
    ]
    
    CALL_DIRECTION_CHOICES = [
        ('outbound', 'Outbound'),
        ('inbound', 'Inbound'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='calls')
    contact = models.ForeignKey('contacts.Contact', on_delete=models.SET_NULL, null=True, blank=True, related_name='calls')
    phone_number = models.CharField(max_length=20)
    direction = models.CharField(max_length=10, choices=CALL_DIRECTION_CHOICES, default='outbound')
    status = models.CharField(max_length=20, choices=CALL_STATUS_CHOICES, default='initiated')
    twilio_sid = models.CharField(max_length=100, blank=True, null=True)  # Twilio Call SID
    duration = models.IntegerField(default=0)  # Duration in seconds
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-started_at']
    
    def __str__(self):
        return f"{self.direction} call to {self.phone_number} ({self.status})"
    
    def end_call(self, duration=None):
        """End the call and update duration"""
        self.ended_at = timezone.now()
        if duration:
            self.duration = duration
        elif self.started_at:
            self.duration = int((self.ended_at - self.started_at).total_seconds())
        self.save()
    
    @property
    def is_active(self):
        """Check if the call is currently active"""
        return self.status in ['initiated', 'ringing', 'in-progress']
