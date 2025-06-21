from django.shortcuts import render
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import Contact
from .serializers import ContactSerializer, ContactListSerializer


class ContactViewSet(viewsets.ModelViewSet):
    """ViewSet for Contact model with CRUD operations"""
    
    serializer_class = ContactSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['tags']
    search_fields = ['name', 'phone', 'email', 'notes']
    ordering_fields = ['name', 'created_at', 'updated_at', 'last_contacted']
    ordering = ['-updated_at']
    
    def get_queryset(self):
        """Return contacts for the current user only"""
        return Contact.objects.filter(user=self.request.user)
    
    def get_serializer_class(self):
        """Use different serializers for list and detail views"""
        if self.action == 'list':
            return ContactListSerializer
        return ContactSerializer
    
    @action(detail=False, methods=['get'])
    def search(self, request):
        """Enhanced search endpoint with multiple filters"""
        queryset = self.get_queryset()
        
        # Get query parameters
        name = request.query_params.get('name', '')
        phone = request.query_params.get('phone', '')
        email = request.query_params.get('email', '')
        tags = request.query_params.getlist('tags', [])
        
        # Apply filters
        if name:
            queryset = queryset.filter(name__icontains=name)
        if phone:
            queryset = queryset.filter(phone__icontains=phone)
        if email:
            queryset = queryset.filter(email__icontains=email)
        if tags:
            queryset = queryset.filter(tags__contains=tags)
        
        # Paginate results
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def update_last_contacted(self, request, pk=None):
        """Update the last contacted timestamp for a contact"""
        contact = self.get_object()
        contact.update_last_contacted()
        serializer = self.get_serializer(contact)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def tags(self, request):
        """Get all unique tags for the current user's contacts"""
        queryset = self.get_queryset()
        tags = set()
        for contact in queryset:
            tags.update(contact.tags)
        return Response({'tags': list(tags)})
