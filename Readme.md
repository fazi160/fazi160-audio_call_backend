# Secure Dashboard API Documentation

## Project Overview

Secure Dashboard is a comprehensive communication management system that provides secure user authentication, contact management, and call handling capabilities. The system integrates with Twilio for voice communication and supports WebAuthn (passkey) authentication for enhanced security.

### Key Features
- **Secure Authentication**: WebAuthn (passkey) and traditional password-based authentication
- **Contact Management**: Full CRUD operations for contact management with phone number validation
- **Call Handling**: Incoming/outgoing call management with Twilio integration
- **Call History**: Detailed call tracking with notes and statistics
- **Real-time Notifications**: Incoming call notifications with ringtone support

---

## Base URL to server
```
https://fazi160-audio-call-backend.onrender.com
```

## Authentication

All API endpoints require authentication unless specified otherwise. Use JWT Bearer tokens in the Authorization header:
```
Authorization: Bearer <your_jwt_token>
```

---

## API Endpoints

### 🔐 Authentication Endpoints

#### 1. User Registration
```http
POST /api/auth/register/
```
**Description**: Register a new user account

**Request Body**:
```json
{
  "username": "string",
  "email": "string",
  "first_name": "string",
  "last_name": "string",
  "password": "string",
  "password_confirm": "string"
}
```

**Response** (201):
```json
{
  "message": "User registered successfully",
  "user": {
    "id": 1,
    "username": "example",
    "email": "example@example.com",
    "first_name": "example",
    "last_name": "example",
    "date_joined": "2024-01-01T00:00:00Z"
  }
}
```

#### 2. User Login
```http
POST /api/auth/login/
```
**Description**: Authenticate user with username and password

**Request Body**:
```json
{
  "username": "string",
  "password": "string"
}
```

**Response** (200):
```json
{
  "message": "Login successful",
  "user": {
    "id": 1,
    "username": "example",
    "email": "example@example.com",
    "first_name": "example",
    "last_name": "example",
    "date_joined": "2024-01-01T00:00:00Z"
  },
  "tokens": {
    "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
  }
}
```

#### 3. User Logout
```http
POST /api/auth/logout/
```
**Description**: Logout current user (requires authentication)

**Response** (200):
```json
{
  "message": "Logout successful"
}
```

#### 4. WebAuthn Registration Begin
```http
POST /api/auth/webauthn/register/begin/
```
**Description**: Start WebAuthn (passkey) registration process

**Request Body**:
```json
{
  "username": "string",
  "display_name": "string" // optional
}
```

**Response** (200):
```json
{
  "options": {
    "challenge": "base64_encoded_challenge",
    "rp": {
      "name": "Secure Dashboard",
      "id": "localhost"
    },
    "user": {
      "id": "base64_encoded_user_id",
      "name": "john_doe",
      "displayName": "John Doe"
    },
    "pubKeyCredParams": [...],
    "timeout": 60000,
    "attestation": "direct"
  },
  "challenge_id": "uuid_string"
}
```

#### 5. WebAuthn Registration Complete
```http
POST /api/auth/webauthn/register/complete/
```
**Description**: Complete WebAuthn registration with credential data

**Request Body**:
```json
{
  "challenge_id": "string",
  "username": "string",
  "credential_id": "base64_encoded_credential_id",
  "attestation_object": "base64_encoded_attestation_object",
  "client_data_json": "base64_encoded_client_data",
  "transports": ["usb", "nfc", "ble"],
  "backup_eligible": false,
  "backup_state": false
}
```

**Response** (200):
```json
{
  "message": "WebAuthn credential registered successfully",
  "credential": {
    "id": 1,
    "credential_id": "base64_encoded_credential_id",
    "sign_count": 0,
    "transports": ["usb"],
    "backup_eligible": false,
    "backup_state": false,
    "created_at": "2024-01-01T00:00:00Z",
    "last_used_at": null
  }
}
```

#### 6. WebAuthn Authentication Begin
```http
POST /api/auth/webauthn/authenticate/begin/
```
**Description**: Start WebAuthn authentication process

**Request Body**:
```json
{
  "username": "string"
}
```

**Response** (200):
```json
{
  "options": {
    "challenge": "base64_encoded_challenge",
    "rpId": "localhost",
    "allowCredentials": [
      {
        "id": "base64_encoded_credential_id",
        "type": "public-key",
        "transports": ["usb"]
      }
    ],
    "userVerification": "preferred",
    "timeout": 60000
  },
  "challenge_id": "uuid_string"
}
```

#### 7. WebAuthn Authentication Complete
```http
POST /api/auth/webauthn/authenticate/complete/
```
**Description**: Complete WebAuthn authentication

**Request Body**:
```json
{
  "challenge_id": "string",
  "username": "string",
  "credential_id": "base64_encoded_credential_id",
  "authenticator_data": "base64_encoded_authenticator_data",
  "client_data_json": "base64_encoded_client_data",
  "signature": "base64_encoded_signature"
}
```

**Response** (200):
```json
{
  "message": "Authentication successful",
  "user": {
    "id": 1,
    "username": "john_doe",
    "email": "john@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "date_joined": "2024-01-01T00:00:00Z"
  },
  "tokens": {
    "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
  }
}
```

#### 8. User Profile
```http
GET /api/auth/profile/
```
**Description**: Get current user profile (requires authentication)

**Response** (200):
```json
{
  "id": 1,
  "username": "john_doe",
  "email": "john@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "date_joined": "2024-01-01T00:00:00Z"
}
```

#### 9. Token Refresh
```http
POST /api/auth/token/refresh/
```
**Description**: Refresh JWT access token

**Request Body**:
```json
{
  "refresh": "refresh_token_string"
}
```

**Response** (200):
```json
{
  "access": "new_access_token_string"
}
```

---

### 📞 Call Management Endpoints

#### 1. Get Twilio Token
```http
GET /api/call/token/
```
**Description**: Get Twilio access token for client-side calls (requires authentication)

**Response** (200):
```json
{
  "token": "twilio_access_token_string"
}
```

#### 2. Call History
```http
GET /api/call/history/
```
**Description**: Get user's call history with pagination and filtering

**Query Parameters**:
- `search` (optional): Search by contact name or number
- `status` (optional): Filter by call status (completed, failed, initiated)
- `page` (optional): Page number for pagination

**Response** (200):
```json
{
  "count": 50,
  "next": "http://api.example.com/call/history/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "contact": {
        "id": 1,
        "name": "John Doe",
        "phone_number": "+1234567890",
        "email": "john@example.com"
      },
      "contact_number": "+1234567890",
      "user": {
        "id": 1,
        "username": "john_doe",
        "first_name": "John",
        "last_name": "Doe"
      },
      "created_at": "2024-01-01T10:00:00Z",
      "call_status": "completed",
      "call_duration": 120,
      "call_start_time": "2024-01-01T10:00:00Z",
      "call_end_time": "2024-01-01T10:02:00Z",
      "call_sid": "CA1234567890",
      "display_name": "John Doe",
      "display_number": "+1234567890",
      "duration_formatted": "02:00",
      "notes": []
    }
  ]
}
```

#### 3. Call Statistics
```http
GET /api/call/statistics/
```
**Description**: Get call statistics for the authenticated user

**Response** (200):
```json
{
  "total_calls": 150,
  "completed_calls": 120,
  "failed_calls": 20,
  "initiated_calls": 10,
  "total_duration": 7200,
  "average_duration": 48,
  "calls_by_status": {
    "completed": 120,
    "failed": 20,
    "initiated": 10
  },
  "calls_by_month": {
    "2024-01": 50,
    "2024-02": 45,
    "2024-03": 55
  }
}
```

#### 4. Call Detail
```http
GET /api/call/detail/{call_id}/
```
**Description**: Get detailed information about a specific call

**Response** (200):
```json
{
  "id": 1,
  "contact": {
    "id": 1,
    "name": "John Doe",
    "phone_number": "+1234567890",
    "email": "john@example.com"
  },
  "contact_number": "+1234567890",
  "user": {
    "id": 1,
    "username": "john_doe",
    "first_name": "John",
    "last_name": "Doe"
  },
  "created_at": "2024-01-01T10:00:00Z",
  "updated_at": "2024-01-01T10:02:00Z",
  "call_status": "completed",
  "call_duration": 120,
  "call_start_time": "2024-01-01T10:00:00Z",
  "call_end_time": "2024-01-01T10:02:00Z",
  "call_sid": "CA1234567890",
  "display_name": "John Doe",
  "display_number": "+1234567890",
  "notes": [
    {
      "id": 1,
      "note": "Customer was satisfied with the service",
      "created_at": "2024-01-01T10:05:00Z",
      "updated_at": "2024-01-01T10:05:00Z"
    }
  ]
}
```

#### 5. Add Call Note
```http
POST /api/call/detail/{call_id}/notes/
```
**Description**: Add a note to a specific call

**Request Body**:
```json
{
  "note": "string"
}
```

**Response** (201):
```json
{
  "id": 1,
  "note": "Customer was satisfied with the service",
  "created_at": "2024-01-01T10:05:00Z",
  "updated_at": "2024-01-01T10:05:00Z"
}
```

#### 6. Twilio Webhook Endpoints (Internal)

##### Voice Handler
```http
POST /api/call/voice/handler/
```
**Description**: Handle incoming voice calls from Twilio

##### Voice Fallback
```http
POST /api/call/voice/fallback/
```
**Description**: Handle voice call fallbacks

##### Voice Status Callback
```http
POST /api/call/voice/status/
```
**Description**: Handle call status updates from Twilio

##### Incoming Call Webhook
```http
POST /api/call/webhook/incoming/
```
**Description**: Handle incoming call notifications

---

### 👥 Contact Management Endpoints

#### 1. List Contacts
```http
GET /api/contact/contacts/
```
**Description**: Get all contacts for the authenticated user

**Query Parameters**:
- `search` (optional): Search by name, phone, or email
- `page` (optional): Page number for pagination

**Response** (200):
```json
{
  "count": 25,
  "next": "http://api.example.com/contact/contacts/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "name": "John Doe",
      "phone_number": "+1234567890",
      "email": "john@example.com",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

#### 2. Create Contact
```http
POST /api/contact/contacts/
```
**Description**: Create a new contact

**Request Body**:
```json
{
  "name": "string",
  "phone_number": "string",
  "email": "string" // optional
}
```

**Response** (201):
```json
{
  "message": "Contact created successfully",
  "contact": {
    "id": 1,
    "name": "John Doe",
    "phone_number": "+1234567890",
    "email": "john@example.com",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z",
    "user": {
      "id": 1,
      "username": "john_doe",
      "first_name": "John",
      "last_name": "Doe"
    }
  },
  "linked_calls": 5,
  "phone_number": "1234567890"
}
```

#### 3. Get Contact
```http
GET /api/contact/contacts/{contact_id}/
```
**Description**: Get a specific contact

**Response** (200):
```json
{
  "id": 1,
  "name": "John Doe",
  "phone_number": "+1234567890",
  "email": "john@example.com",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z",
  "user": {
    "id": 1,
    "username": "john_doe",
    "first_name": "John",
    "last_name": "Doe"
  }
}
```

#### 4. Update Contact
```http
PUT /api/contact/contacts/{contact_id}/
PATCH /api/contact/contacts/{contact_id}/
```
**Description**: Update a contact (PUT for full update, PATCH for partial)

**Request Body**:
```json
{
  "name": "string",
  "phone_number": "string",
  "email": "string" // optional
}
```

**Response** (200):
```json
{
  "message": "Contact updated successfully",
  "contact": {
    "id": 1,
    "name": "John Doe Updated",
    "phone_number": "+1234567890",
    "email": "john.updated@example.com",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T12:00:00Z",
    "user": {
      "id": 1,
      "username": "john_doe",
      "first_name": "John",
      "last_name": "Doe"
    }
  },
  "linked_calls": 2,
  "phone_number": "1234567890"
}
```

#### 5. Delete Contact
```http
DELETE /api/contact/contacts/{contact_id}/
```
**Description**: Delete a contact

**Response** (204): No content

#### 6. Search Contacts
```http
GET /api/contact/contacts/search/
```
**Description**: Search contacts by name, phone, or email

**Query Parameters**:
- `q` (required): Search query

**Response** (200):
```json
{
  "contacts": [
    {
      "id": 1,
      "name": "John Doe",
      "phone_number": "+1234567890",
      "email": "john@example.com",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ],
  "count": 1,
  "query": "john"
}
```

#### 7. Contact Statistics
```http
GET /api/contact/contacts/stats/
```
**Description**: Get contact statistics

**Response** (200):
```json
{
  "total_contacts": 25,
  "contacts_with_email": 20,
  "contacts_without_email": 5,
  "recent_contacts": 5,
  "contacts_by_month": {
    "2024-01": 10,
    "2024-02": 8,
    "2024-03": 7
  }
}
```

#### 8. Unlinked Calls Statistics
```http
GET /api/contact/contacts/unlinked_calls_stats/
```
**Description**: Get statistics about unlinked calls and potential contact matches

**Response** (200):
```json
{
  "total_unlinked_calls": 15,
  "potential_matches": [
    {
      "phone_number": "+1234567890",
      "call_count": 3,
      "original_numbers": ["+1-234-567-8900", "+1234567890"],
      "first_call": "2024-01-01T00:00:00Z",
      "last_call": "2024-01-15T00:00:00Z"
    }
  ]
}
```

#### 9. Link Calls to Contact
```http
POST /api/contact/contacts/{contact_id}/link_calls/
```
**Description**: Manually link unlinked calls to a contact

**Response** (200):
```json
{
  "message": "Calls linked successfully",
  "linked_count": 3,
  "contact": {
    "id": 1,
    "name": "John Doe",
    "phone_number": "+1234567890"
  }
}
```

---

## Error Responses

### Standard Error Format
```json
{
  "error": "Error message description",
  "details": {
    "field_name": ["Specific field error"]
  }
}
```

### Common HTTP Status Codes
- `200` - Success
- `201` - Created
- `204` - No Content
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `429` - Too Many Requests
- `500` - Internal Server Error

---

## Rate Limiting

- **WebAuthn operations**: 5 attempts per 5 minutes per user
- **Authentication endpoints**: Standard rate limiting applied
- **API endpoints**: 1000 requests per hour per user

---

## Environment Variables

```env
# Database Configuration
DEPLOY=True
DB_NAME=db_name
DB_USER=db_user
DB_PASSWORD=db_password
DB_HOST=host_url
DB_PORT=port

# Django Configuration
SECRET_KEY=your-secret-key
DEBUG=False
ALLOWED_HOSTS=fazi160-audio-call-backend.onrender.com

# Twilio Configuration
TWILIO_ACCOUNT_SID=your-twilio-account-sid
TWILIO_API_KEY=your-twilio-api-key
TWILIO_API_SECRET=your-twilio-api-secret
TWILIO_PHONE_NUMBER=your-twilio-phone-number
TWIML_APP_SID=your-twiml-app-sid

# WebAuthn Configuration
WEBAUTHN_RP_ID=localhost
WEBAUTHN_RP_NAME=Secure Dashboard
WEBAUTHN_RP_ORIGIN=http://localhost:5173

# Base URL
BASE_URL=https://fazi160-audio-call-backend.onrender.com
```

---

## Technologies Used

- **Backend**: Django 5.2.3, Django REST Framework
- **Database**: PostgreSQL (production), SQLite (development)
- **Authentication**: JWT, WebAuthn (passkey)
- **Communication**: Twilio Voice API
- **Deployment**: Render
- **Security**: CORS, CSRF protection, rate limiting
