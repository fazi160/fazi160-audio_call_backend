from django.shortcuts import render
from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q
from django.db import transaction
from .models import Contact
from .serializers import ContactSerializer, ContactListSerializer
from rest_framework.permissions import IsAuthenticated
from call.models import Call
import re

def normalize_phone_number(phone_number):
    """Normalize phone number by removing all non-digit characters"""
    if not phone_number:
        return ""
    # Remove all non-digit characters
    normalized = re.sub(r'\D', '', phone_number)
    return normalized

# Create your views here.
class ContactView(ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Contact.objects.all()
    serializer_class = ContactSerializer

    def get_queryset(self):
        """Filter contacts by authenticated user"""
        return Contact.objects.filter(user=self.request.user)
    
    def get_serializer_class(self):
        """Use different serializers for different actions"""
        if self.action == 'list':
            return ContactListSerializer
        return ContactSerializer
    
    def list(self, request, *args, **kwargs):
        """Enhanced list with search and filtering"""
        queryset = self.get_queryset()
        
        # Search functionality
        search = request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(phone_number__icontains=search) |
                Q(email__icontains=search)
            )
        
        # Pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    def create(self, request, *args, **kwargs):
        """Create a new contact and link existing call history"""
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            with transaction.atomic():
                # Create the contact
                contact = serializer.save(user=request.user)
                
                # Find existing calls with the same phone number for this user
                phone_number = normalize_phone_number(contact.phone_number)
                existing_calls = Call.objects.filter(
                    user=request.user,
                    contact__isnull=True  # Only calls that don't already have a contact
                )
                
                # Filter calls by normalized phone number
                matching_calls = []
                for call in existing_calls:
                    if normalize_phone_number(call.contact_number) == phone_number:
                        matching_calls.append(call)
                
                # Update all matching calls to link them to this contact
                linked_calls_count = 0
                for call in matching_calls:
                    call.contact = contact
                    call.save()
                    linked_calls_count += 1
                
                return Response({
                    'message': 'Contact created successfully',
                    'contact': ContactSerializer(contact).data,
                    'linked_calls': linked_calls_count,
                    'phone_number': phone_number
                }, status=status.HTTP_201_CREATED)
        return Response({
            'error': 'Invalid data',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    def update(self, request, *args, **kwargs):
        """Update a contact with validation and link existing call history"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        if serializer.is_valid():
            with transaction.atomic():
                # Check if phone number is being updated
                old_phone_number = instance.phone_number
                contact = serializer.save()
                new_phone_number = contact.phone_number
                
                linked_calls_count = 0
                
                # If phone number changed, link existing calls with the new number
                if old_phone_number != new_phone_number:
                    normalized_new_number = normalize_phone_number(new_phone_number)
                    existing_calls = Call.objects.filter(
                        user=request.user,
                        contact__isnull=True  # Only calls that don't already have a contact
                    )
                    
                    # Filter calls by normalized phone number
                    matching_calls = []
                    for call in existing_calls:
                        if normalize_phone_number(call.contact_number) == normalized_new_number:
                            matching_calls.append(call)
                    
                    # Update all matching calls to link them to this contact
                    for call in matching_calls:
                        call.contact = contact
                        call.save()
                        linked_calls_count += 1
                
                return Response({
                    'message': 'Contact updated successfully',
                    'contact': ContactSerializer(contact).data,
                    'linked_calls': linked_calls_count,
                    'phone_number': new_phone_number
                })
        return Response({
            'error': 'Invalid data',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    def destroy(self, request, *args, **kwargs):
        """Delete a contact"""
        instance = self.get_object()
        instance.delete()
        return Response({
            'message': 'Contact deleted successfully'
        }, status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=False, methods=['get'])
    def search(self, request):
        """Search contacts by name, phone, or email"""
        query = request.query_params.get('q', '')
        if not query:
            return Response({
                'error': 'Search query is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        contacts = self.get_queryset().filter(
            Q(name__icontains=query) |
            Q(phone_number__icontains=query) |
            Q(email__icontains=query)
        )
        
        serializer = ContactListSerializer(contacts, many=True)
        return Response({
            'contacts': serializer.data,
            'count': contacts.count(),
            'query': query
        })
    
    @action(detail=False, methods=['get'])
    def unlinked_calls_stats(self, request):
        """Get statistics about unlinked calls and potential contact matches"""
        # Get all unlinked calls for the user
        unlinked_calls = Call.objects.filter(
            user=request.user,
            contact__isnull=True
        )
        
        # Group by phone number to find potential matches
        phone_number_groups = {}
        for call in unlinked_calls:
            normalized_number = normalize_phone_number(call.contact_number)
            if normalized_number:
                if normalized_number not in phone_number_groups:
                    phone_number_groups[normalized_number] = {
                        'count': 0,
                        'original_numbers': set(),
                        'first_call': call.created_at,
                        'last_call': call.created_at
                    }
                phone_number_groups[normalized_number]['count'] += 1
                phone_number_groups[normalized_number]['original_numbers'].add(call.contact_number)
                phone_number_groups[normalized_number]['first_call'] = min(
                    phone_number_groups[normalized_number]['first_call'], 
                    call.created_at
                )
                phone_number_groups[normalized_number]['last_call'] = max(
                    phone_number_groups[normalized_number]['last_call'], 
                    call.created_at
                )
        
        # Find phone numbers that could be linked to existing contacts
        potential_matches = []
        for normalized_number, data in phone_number_groups.items():
            existing_contact = Contact.objects.filter(
                user=request.user,
                phone_number__regex=r'[^\d]*' + re.escape(normalized_number) + r'[^\d]*'
            ).first()
            
            if existing_contact:
                potential_matches.append({
                    'phone_number': normalized_number,
                    'contact_name': existing_contact.name,
                    'contact_id': existing_contact.id,
                    'call_count': data['count'],
                    'original_numbers': list(data['original_numbers']),
                    'first_call': data['first_call'],
                    'last_call': data['last_call']
                })
        
        return Response({
            'total_unlinked_calls': unlinked_calls.count(),
            'unique_phone_numbers': len(phone_number_groups),
            'potential_matches': potential_matches,
            'potential_matches_count': len(potential_matches)
        })
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get contact statistics"""
        total_contacts = self.get_queryset().count()
        contacts_with_email = self.get_queryset().filter(email__isnull=False).exclude(email='').count()
        contacts_with_phone = self.get_queryset().filter(phone_number__isnull=False).exclude(phone_number='').count()
        
        return Response({
            'total_contacts': total_contacts,
            'contacts_with_email': contacts_with_email,
            'contacts_with_phone': contacts_with_phone,
            'completion_rate': {
                'email': round((contacts_with_email / total_contacts * 100) if total_contacts > 0 else 0, 2),
                'phone': round((contacts_with_phone / total_contacts * 100) if total_contacts > 0 else 0, 2)
            }
        })
    
    @action(detail=True, methods=['post'])
    def link_calls(self, request, pk=None):
        """Manually link existing call history to a contact"""
        contact = self.get_object()
        
        with transaction.atomic():
            normalized_phone_number = normalize_phone_number(contact.phone_number)
            existing_calls = Call.objects.filter(
                user=request.user,
                contact__isnull=True  # Only calls that don't already have a contact
            )
            
            # Filter calls by normalized phone number
            matching_calls = []
            for call in existing_calls:
                if normalize_phone_number(call.contact_number) == normalized_phone_number:
                    matching_calls.append(call)
            
            # Update all matching calls to link them to this contact
            linked_calls_count = 0
            for call in matching_calls:
                call.contact = contact
                call.save()
                linked_calls_count += 1
            
            return Response({
                'message': f'Successfully linked {linked_calls_count} calls to contact',
                'contact': ContactSerializer(contact).data,
                'linked_calls': linked_calls_count,
                'phone_number': contact.phone_number
            })
    
