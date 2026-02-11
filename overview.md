# AutoPay System Overview

## System Architecture

AutoPay is a secure webhook-based payment processing system built with FastAPI that provides enterprise-grade security, idempotency protection, and AI-powered analytics. The system processes payment webhooks from external payment providers and stores transaction data in MongoDB with comprehensive security measures.

## Core Components

### 1. FastAPI Application (`app/main.py`)
- **Entry Point**: Initializes the application with lifecycle management
- **Endpoints**:
  - `GET /`: Health check endpoint
  - `POST /webhook/payment`: Main payment processing endpoint with HMAC verification
  - `GET /transaction/{tx_id}`: Transaction retrieval endpoint
- **Middleware**: Automatic HMAC signature verification for all webhook requests

### 2. Security Layer (`app/security.py`)
- **HMAC Authentication**: Verifies webhook authenticity using SHA256 signatures
- **Timing Attack Protection**: Uses `hmac.compare_digest()` for secure signature comparison
- **Header Validation**: Requires `X-Signature` header for all webhook requests
- **Environment Configuration**: Loads HMAC secret from environment variables

### 3. Database Layer (`app/database.py`)
- **MongoDB Integration**: Uses Motor async driver for MongoDB connectivity
- **Beanie ODM**: Provides async object-document mapping for Python
- **Connection Management**: Handles database initialization and connection testing
- **Automatic Schema**: Creates collections and indexes automatically

### 4. Data Models (`app/models.py`)
- **Transaction Document**: Stores payment transaction data with fields:
  - `tx_id`: Unique transaction identifier
  - `amount`: Payment amount
  - `currency`: Currency code
  - `sender_account`: Sender account identifier
  - `receiver_account`: Receiver account identifier
  - `status`: Transaction status (pending/success)
  - `timestamp`: UTC timestamp
  - `description`: Optional transaction description

### 5. Business Logic (`app/services/payment_service.py`)
- **Payment Processing**: Handles webhook payload processing
- **Idempotency Protection**: Prevents duplicate transaction processing
- **Transaction Retrieval**: Provides transaction lookup functionality
- **Error Handling**: Comprehensive logging and error management

### 6. Data Validation (`app/schemas/transaction.py`)
- **Pydantic Models**: 
  - `WebhookPayload`: Validates incoming webhook data
  - `TransactionCreate`: Validates transaction creation requests
- **Type Safety**: Ensures data integrity and type validation

## Security Features

### HMAC Authentication Flow
1. **Request Reception**: FastAPI receives webhook with `X-Signature` header
2. **Signature Verification**: Security middleware calculates expected HMAC using shared secret
3. **Constant-Time Comparison**: Prevents timing attacks during signature validation
4. **Request Processing**: Only proceeds with valid signatures

### Idempotency Protection
1. **Transaction Lookup**: Checks if `tx_id` already exists in database
2. **Duplicate Prevention**: Returns "already_processed" status for duplicates
3. **Safe Processing**: Prevents double-charging and data corruption

## Development Tools

### Mock Payment Simulator (`scripts/mock_sender.py`)
- **Realistic Testing**: Generates authentic transaction payloads
- **Scenario Testing**: Simulates various payment scenarios:
  - Valid transactions
  - Duplicate transactions (idempotency testing)
  - Invalid signatures (security testing)
  - Multiple valid transactions
- **HMAC Integration**: Properly signs requests for realistic testing

### AI Reporter (`scripts/ai_reporter.py`)
- **Business Intelligence**: Generates payment analytics reports
- **Google Gemini Integration**: Uses AI for transaction analysis
- **Automated Insights**: Provides business intelligence from payment data

## Data Flow

### Payment Processing Flow
1. **Webhook Reception**: External payment provider sends signed webhook
2. **Security Verification**: HMAC signature is validated
3. **Payload Validation**: Pydantic schemas validate request data
4. **Idempotency Check**: System checks for existing transactions
5. **Database Storage**: New transactions are stored in MongoDB
6. **Response Generation**: Success/error response is returned

### Transaction Retrieval Flow
1. **Request Reception**: Client requests transaction by ID
2. **Database Query**: System queries MongoDB for transaction
3. **Response Formatting**: Transaction data is formatted and returned
4. **Error Handling**: Appropriate HTTP status codes for missing data

## Technology Stack

- **Backend**: FastAPI (Python 3.11+)
- **Database**: MongoDB with Beanie ODM
- **Security**: HMAC SHA256 authentication
- **Async Processing**: Full async/await support
- **Validation**: Pydantic schemas
- **Testing**: Pytest framework
- **AI Integration**: Google Gemini API
- **Environment**: Docker-ready with environment configuration

## Configuration

### Environment Variables
- `HMAC_SECRET_KEY`: Secret key for webhook signature verification
- `MONGO_URL`: MongoDB connection string
- `GOOGLE_API_KEY`: Google Gemini API key for AI reporting

### Dependencies
- FastAPI for web framework
- Motor for async MongoDB driver
- Beanie for ODM
- Pydantic for data validation
- httpx for HTTP client operations

## Security Considerations

1. **Signature Verification**: All webhooks must have valid HMAC signatures
2. **Timing Attack Prevention**: Uses constant-time comparison
3. **Input Validation**: Comprehensive Pydantic schema validation
4. **Error Handling**: Secure error responses without information leakage
5. **Idempotency**: Prevents duplicate processing and financial errors

## Scalability Features

- **Async Architecture**: Non-blocking I/O for high throughput
- **MongoDB**: Horizontal scaling capabilities
- **Connection Pooling**: Efficient database connection management
- **Minimal Dependencies**: Lightweight and fast deployment

This system provides a robust foundation for secure payment processing with enterprise-grade security, comprehensive testing tools, and AI-powered analytics capabilities.