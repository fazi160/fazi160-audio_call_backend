# Contact Management System

This module provides a complete contact management system with CRUD operations, search, and statistics.

## Models

### Contact Model
- `name`: CharField for contact name
- `phone_number`: CharField for phone number (validated)
- `email`: EmailField for email address (unique per user)
- `user`: ForeignKey to User (contact owner)
- `created_at` and `updated_at`: Timestamps

## API Endpoints

### Authentication Required
All endpoints require authentication.

### Base URL: `/api/contact/`

### 1. List Contacts
```
GET /api/contact/contacts/
```
Get paginated list of user's contacts.

**Query Parameters:**
- `search`: Search in name, phone, or email
- `page`: Page number
- `page_size`: Items per page

**Response:**
```json
{
    "count": 50,
    "next": "http://localhost:8000/api/contact/contacts/?page=2",
    "previous": null,
    "results": [
        {
            "id": 1,
            "name": "John Doe",
            "phone_number": "+1234567890",
            "email": "john@example.com",
            "created_at": "2024-01-01T10:00:00Z"
        }
    ]
}
```

### 2. Create Contact
```
POST /api/contact/contacts/
```
Create a new contact.

**Request Body:**
```json
{
    "name": "John Doe",
    "phone_number": "+1234567890",
    "email": "john@example.com"
}
```

**Response:**
```json
{
    "message": "Contact created successfully",
    "contact": {
        "id": 1,
        "name": "John Doe",
        "phone_number": "+1234567890",
        "email": "john@example.com",
        "created_at": "2024-01-01T10:00:00Z",
        "updated_at": "2024-01-01T10:00:00Z",
        "user": {
            "id": 1,
            "username": "user1",
            "first_name": "John",
            "last_name": "Doe"
        },
        "linked_calls": 5,
        "phone_number": "1234567890"
    }
}
```

### 3. Get Contact Details
```
GET /api/contact/contacts/{id}/
```
Get detailed information about a specific contact.

**Response:**
```json
{
    "id": 1,
    "name": "John Doe",
    "phone_number": "+1234567890",
    "email": "john@example.com",
    "created_at": "2024-01-01T10:00:00Z",
    "updated_at": "2024-01-01T10:00:00Z",
    "user": {
        "id": 1,
        "username": "user1",
        "first_name": "John",
        "last_name": "Doe"
    },
    "linked_calls": 2,
    "phone_number": "+1234567890"
}
```

### 4. Update Contact
```
PUT /api/contact/contacts/{id}/
PATCH /api/contact/contacts/{id}/
```
Update a contact (PUT for full update, PATCH for partial).

**Request Body:**
```json
{
    "name": "John Smith",
    "phone_number": "+1234567890"
}
```

**Response:**
```json
{
    "message": "Contact updated successfully",
    "contact": {
        "id": 1,
        "name": "John Smith",
        "phone_number": "+1234567890",
        "email": "john@example.com",
        "created_at": "2024-01-01T10:00:00Z",
        "updated_at": "2024-01-01T10:05:00Z",
        "user": {...},
        "linked_calls": 2,
        "phone_number": "+1234567890"
    }
}
```

### 5. Delete Contact
```
DELETE /api/contact/contacts/{id}/
```
Delete a contact.

**Response:**
```json
{
    "message": "Contact deleted successfully"
}
```

### 6. Search Contacts
```
GET /api/contact/contacts/search/?q=john
```
Search contacts by name, phone, or email.

**Query Parameters:**
- `q`: Search query (required)

**Response:**
```json
{
    "contacts": [
        {
            "id": 1,
            "name": "John Doe",
            "phone_number": "+1234567890",
            "email": "john@example.com",
            "created_at": "2024-01-01T10:00:00Z"
        }
    ],
    "count": 1,
    "query": "john"
}
```

### 7. Contact Statistics
```
GET /api/contact/contacts/stats/
```
Get contact statistics for the authenticated user.

**Response:**
```json
{
    "total_contacts": 50,
    "contacts_with_email": 45,
    "contacts_with_phone": 48,
    "completion_rate": {
        "email": 90.0,
        "phone": 96.0
    }
}
```

### 8. Manual Call Linking
```
POST /api/contact/contacts/{id}/link_calls/
```
Manually link existing calls to a contact.

**Response:**
```json
{
    "message": "Successfully linked 3 calls to contact",
    "contact": {
        "id": 1,
        "name": "John Doe",
        "phone_number": "+1234567890"
    },
    "linked_calls": 3,
    "phone_number": "+1234567890"
}
```

### 9. Unlinked Calls Statistics
```
GET /api/contact/contacts/unlinked_calls_stats/
```
Get statistics about unlinked calls and potential matches.

**Response:**
```json
{
    "total_unlinked_calls": 25,
    "unique_phone_numbers": 8,
    "potential_matches": [
        {
            "phone_number": "1234567890",
            "contact_name": "John Doe",
            "contact_id": 1,
            "call_count": 5,
            "original_numbers": ["+1-234-567-8900", "1234567890"],
            "first_call": "2024-01-01T10:00:00Z",
            "last_call": "2024-01-15T14:30:00Z"
        }
    ],
    "potential_matches_count": 1
}
```

## Validation Rules

### Phone Number Validation
- Must contain at least 10 digits
- Automatically cleans non-digit characters (except + for international format)
- Examples of valid formats:
  - `+1234567890`
  - `123-456-7890`
  - `(123) 456-7890`

### Email Validation
- Must be a valid email format
- Must be unique per user (no duplicate emails for the same user)
- Case-insensitive validation

## Error Handling

All endpoints return consistent error responses:

### Validation Error
```json
{
    "error": "Invalid data",
    "details": {
        "phone_number": ["Phone number must contain at least 10 digits"],
        "email": ["A contact with this email already exists"]
    }
}
```

### Not Found Error
```json
{
    "detail": "Not found."
}
```

### Authentication Error
```json
{
    "detail": "Authentication credentials were not provided."
}
```

## Usage Examples

### Create a new contact:
```javascript
const response = await fetch('/api/contact/contacts/', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({
        name: 'John Doe',
        phone_number: '+1234567890',
        email: 'john@example.com'
    })
});
```

### Search contacts:
```javascript
const response = await fetch('/api/contact/contacts/search/?q=john', {
    headers: {
        'Authorization': `Bearer ${token}`
    }
});
```

### Update a contact:
```javascript
const response = await fetch('/api/contact/contacts/1/', {
    method: 'PATCH',
    headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({
        name: 'John Smith'
    })
});
```

### Get contact statistics:
```javascript
const response = await fetch('/api/contact/contacts/stats/', {
    headers: {
        'Authorization': `Bearer ${token}`
    }
});
```

## Admin Interface

The contact system includes a comprehensive Django admin interface with:
- List view with search and filtering
- Detailed edit forms with field grouping
- User-based filtering
- Timestamp tracking 

# Contact Management with Call History Linking

## Overview

The contact management system now includes automatic call history linking functionality, similar to mobile phone behavior. When a new contact is created, the system automatically links all existing call history for that phone number to the newly created contact.

## Features

### 1. Automatic Call Linking on Contact Creation

When a new contact is created:
- The system searches for all existing calls with the same phone number
- All matching calls are automatically linked to the new contact
- Phone numbers are normalized for comparison (removes formatting characters)
- Only calls without existing contact links are considered

### 2. Call Linking on Contact Updates

When a contact's phone number is updated:
- The system checks if the phone number has changed
- If changed, it searches for calls with the new phone number
- Matching calls are linked to the contact

### 3. Manual Call Linking

A new endpoint allows manual linking of calls to contacts:
- `POST /contacts/{id}/link_calls/` - Manually link existing calls to a contact

### 4. Unlinked Calls Statistics

Get statistics about unlinked calls and potential matches:
- `GET /contacts/unlinked_calls_stats/` - Get statistics about unlinked calls

## API Endpoints

### Create Contact
```http
POST /contacts/
```

**Response:**
```json
{
    "message": "Contact created successfully",
    "contact": {
        "id": 1,
        "name": "John Doe",
        "phone_number": "+1234567890",
        "email": "john@example.com"
    },
    "linked_calls": 5,
    "phone_number": "1234567890"
}
```

### Update Contact
```http
PUT /contacts/{id}/
```

**Response:**
```json
{
    "message": "Contact updated successfully",
    "contact": {
        "id": 1,
        "name": "John Doe",
        "phone_number": "+1234567890",
        "email": "john@example.com"
    },
    "linked_calls": 2,
    "phone_number": "+1234567890"
}
```

### Manual Call Linking
```http
POST /contacts/{id}/link_calls/
```

**Response:**
```json
{
    "message": "Successfully linked 3 calls to contact",
    "contact": {
        "id": 1,
        "name": "John Doe",
        "phone_number": "+1234567890"
    },
    "linked_calls": 3,
    "phone_number": "+1234567890"
}
```

### Unlinked Calls Statistics
```http
GET /contacts/unlinked_calls_stats/
```

**Response:**
```json
{
    "total_unlinked_calls": 25,
    "unique_phone_numbers": 8,
    "potential_matches": [
        {
            "phone_number": "1234567890",
            "contact_name": "John Doe",
            "contact_id": 1,
            "call_count": 5,
            "original_numbers": ["+1-234-567-8900", "1234567890"],
            "first_call": "2024-01-01T10:00:00Z",
            "last_call": "2024-01-15T14:30:00Z"
        }
    ],
    "potential_matches_count": 1
}
```

## Phone Number Normalization

The system normalizes phone numbers by removing all non-digit characters for comparison:

- `+1-234-567-8900` → `12345678900`
- `(123) 456-7890` → `1234567890`
- `123.456.7890` → `1234567890`

This ensures that calls with different formatting are properly linked to contacts.

## Database Transactions

All contact creation and call linking operations use database transactions to ensure data consistency. If any part of the operation fails, all changes are rolled back.

## Logging

The system logs when calls are linked to contacts:
```
INFO: Linked 5 calls to contact John Doe (+1234567890) for user johnsmith
```

## Error Handling

- Invalid contact data returns 400 with validation errors
- Database errors are handled gracefully with transaction rollback
- Phone number normalization handles null/empty values 