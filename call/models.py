from django.db import models
from django.contrib.auth.models import User
from contact.models import Contact

# Create your models here.

class Call(models.Model):
    contact = models.ForeignKey(Contact, on_delete=models.SET_NULL, null=True, blank=True)
    contact_number = models.CharField(max_length=255, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    call_status = models.CharField(max_length=255, choices=[('initiated', 'Initiated'), ('completed', 'Completed'), ('failed', 'Failed')])
    call_duration = models.IntegerField(default=0)
    call_start_time = models.DateTimeField(null=True, blank=True)
    call_end_time = models.DateTimeField(null=True, blank=True)
    call_sid = models.CharField(max_length=255, null=True, blank=True)
    call_direction = models.CharField(max_length=255, choices=[('incoming', 'Incoming'), ('outgoing', 'Outgoing')], null=True, blank=True)

    class Meta:
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"{self.contact.name if self.contact else self.contact_number} ({self.contact_number})"
    
    def save(self, *args, **kwargs):
        if self.contact_number and not self.contact:
            # Normalize phone numbers by removing '+' prefix for comparison
            normalized_contact_number = self.contact_number.lstrip('+')
            
            # Check for contacts with matching phone number (with or without '+')
            matching_contacts = Contact.objects.filter(
                phone_number__in=[
                    self.contact_number,  # Original format
                    normalized_contact_number,  # Without '+'
                    f"+{normalized_contact_number}"  # With '+'
                ]
            )
            
            if matching_contacts.exists():
                self.contact = matching_contacts.first()
        super().save(*args, **kwargs)
            
    

    

class Note(models.Model):
    call = models.ForeignKey(Call, on_delete=models.CASCADE)
    note = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.call.contact:
            return f"{self.call.contact.name} - {self.call.user.username if self.call.user else 'Unknown User'}"
        return f"{self.call.contact_number} - {self.call.user.username if self.call.user else 'Unknown User'}"

