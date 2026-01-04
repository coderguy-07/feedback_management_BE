# System Architecture

The **Feedback Management System Backend** follows a modular, layered architecture designed for scalability, maintainability, and separation of concerns. It is built using **FastAPI** (web framework), **SQLModel** (ORM), and **Pydantic** (data validation).

## Default Directory Structure

The codebase is organized into the following top-level directories:

```
Backend/
├── core/       # Infrastructure & Configuration
├── routers/    # Request Handling (Controllers)
├── services/   # Business Logic
├── schemas/    # Data Transfer Objects (DTOs)
├── scripts/    # Utility Scripts
├── models.py   # Database Entitites
└── main.py     # Application Entry Point
```

## Module Breakdown

### 1. Core (`core/`)
This module handles the low-level infrastructure required for the application to run. It doesn't contain business logic but provides the foundation.

- **`config.py`**: Managing environment variables and application settings (e.g., Database configuration, API keys, Email settings).
- **`database.py`**: Database connection management (`engine`), session dependencies (`get_session`), and initialization logic.
- **`logger.py`**: Centralized logging logic to ensure consistent log formatting across the app.
- **`security.py`**: Cryptographic functions including Password Hashing (`bcrypt`, `pbkdf2`) and JWT (JSON Web Token) generation/validation.

### 2. Services (`services/`)
Encapsulates complex business logic and external system integrations. This layer keeps the routers clean.

- **`auth_service.py`**: Authentication dependencies, specifically retrieving the current authenticated admin user (`get_current_admin`).
- **`tasks.py`**: Background tasks management (using `APScheduler`). Handles daily PDF report generation and email dispatching.
- **`whatsapp_client.py`**: A dedicated client for interacting with the Meta WhatsApp Cloud API (sending messages, handling webhooks, downloading media).
- **`generate_hash.py`**: Utility script to generate password hashes for the `.env` file.

### 3. Routers (`routers/`)
The interface layer where API Endpoints are defined. Each file corresponds to a specific domain or feature set.

- **`admin.py`**: Admin-specific actions (Login, Metric reporting, Chart data, Survey management).
- **`admin_portal.py`**: dedicated endpoints for the admin dashboard frontend.
- **`auth.py`**: User authentication endpoints (Login, Profile management).
- **`feedback.py`**: Public-facing endpoint for submitting feedback (handling form data and file uploads).
- **`users.py`**: User management endpoints (Create/Edit/Delete Admins, ROs, FOs).
- **`whatsapp.py`**: Webhook endpoint for receiving real-time updates from WhatsApp.

### 4. Schemas (`schemas/`)
Contains **Pydantic** models that define the structure of data sent to and received from the API (Requests & Responses).
- **`schemas.py`**: Shared schemas used across multiple routers (e.g., `DashboardStats`, `ChartData`).

### 5. Models (`models.py`)
Defines the **SQLModel** classes that map directly to database tables.
- **`Feedback`**: Stores customer feedback data.
- **`AdminUser`**: Stores system users (Admin, RO, DO, FO).
- **`WhatsAppState`**: Manages the state machine for the WhatsApp conversational flow.
- **`ReviewHistory`**: Audit trail for status changes on feedback items.

## Data Flow

1.  **Request**: An HTTP request hits `main.py`.
2.  **Routing**: `main.py` delegates the request to the appropriate module in `routers/`.
3.  **Dependency Injection**: The router may request dependencies (like `Session` from `core/database` or `User` from `services/auth_service`).
4.  **Logic**:
    - Simple CRUD operations are handled directly via `SQLModel` statements in the router.
    - Complex logic (e.g., "Send email report") is offloaded to a function in `services/`.
5.  **Response**: The router returns a Pydantic model (from `schemas/` or `models.py`), which FastAPI serializes to JSON.

## Key Design Patterns

- **Dependency Injection**: Used heavily for Database Sessions and User Authentication, making testing and modularity easier.
- **Layered Architecture**: Clear separation between *HTTP Handling* (Routers), *Business Logic* (Services), and *Data Access* (Models).
- **Asynchronous Execution**: `async/await` is used throughout for I/O bound operations (Database, External APIs, Email).
