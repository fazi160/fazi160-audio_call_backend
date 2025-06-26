from django.db import models
from django.contrib.auth.models import User
from contact.models import Contact
# Create your models here.

class Call(models.Model):
    contact = models.ForeignKey(Contact, on_delete=models.SET_NULL, null=True, blank=True)
    contact_number = models.CharField(max_length=255, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    call_status = models.CharField(max_length=255, choices=[('initiated', 'Initiated'), ('completed', 'Completed'), ('failed', 'Failed')])
    call_duration = models.IntegerField(default=0)
    call_start_time = models.DateTimeField(null=True, blank=True)
    call_end_time = models.DateTimeField(null=True, blank=True)
    call_sid = models.CharField(max_length=255, null=True, blank=True)
    call_direction = models.CharField(max_length=255, choices=[('incoming', 'Incoming'), ('outgoing', 'Outgoing')], null=True, blank=True)


    def __str__(self):
        if self.contact:
            return f"{self.contact.name} - {self.user.username}"
        return f"{self.contact_number} - {self.user.username}"
    

class Note(models.Model):
    call = models.ForeignKey(Call, on_delete=models.CASCADE)
    note = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.call.contact:
            return f"{self.call.contact.name} - {self.call.user.username}"
        return f"{self.call.contact_number} - {self.call.user.username}"

