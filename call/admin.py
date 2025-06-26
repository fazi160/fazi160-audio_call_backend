from django.contrib import admin
from .models import Call, Note

@admin.register(Call)
class CallAdmin(admin.ModelAdmin):
    list_display = ['id', 'get_display_name', 'get_display_number', 'user', 'call_status', 'call_duration', 'created_at']
    list_filter = ['call_status', 'created_at', 'user']
    search_fields = ['contact__name', 'contact_number', 'user__username']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'
    
    def get_display_name(self, obj):
        if obj.contact:
            return obj.contact.name
        return "Unknown Contact"
    get_display_name.short_description = 'Contact Name'
    
    def get_display_number(self, obj):
        if obj.contact:
            return obj.contact.phone_number
        return obj.contact_number
    get_display_number.short_description = 'Phone Number'

@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ['id', 'get_call_info', 'note', 'created_at']
    list_filter = ['created_at']
    search_fields = ['note', 'call__contact__name', 'call__contact_number']
    readonly_fields = ['created_at', 'updated_at']
    
    def get_call_info(self, obj):
        if obj.call.contact:
            return f"{obj.call.contact.name} - {obj.call.user.username}"
        return f"{obj.call.contact_number} - {obj.call.user.username}"
    get_call_info.short_description = 'Call Info'
