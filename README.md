# Feedback Management System (Backend)

## Overview
This is the backend service for the Feedback Management System. It is built using **FastAPI** and provides a robust API for collecting customer feedback, managing surveys, and powering an Admin Portal.

## 🏗️ Architecture
The codebase has been refactored into a modular architecture for scalability and maintainability.
> **[View Detailed Architecture Documentation](architecture.md)**

```
Backend/
├── core/               # Core infrastructure
│   ├── config.py       # Environment configuration
│   ├── database.py     # Database connection & session management
│   ├── logger.py       # Centralized logging
│   └── security.py     # Authentication & Security logic
├── routers/            # API Endpoints (Controllers)
│   ├── admin_portal.py # Main Dashboard & Feedback management APIs
│   ├── feedback.py     # Public feedback submission API
│   ├── whatsapp.py     # WhatsApp Webhook integration
│   └── ...
├── services/           # Business Logic Layer
│   ├── auth_service.py # Authentication dependencies
│   ├── tasks.py        # Background tasks & Scheduler (PDF Reports)
│   ├── whatsapp_client.py # Meta WhatsApp API wrapper
│   └── generate_hash.py # Password hash generator utility
├── schemas/            # Pydantic Data Models (DTOs)
├── scripts/            # Utility and maintenance scripts
├── models.py           # SQLModel Database Entities (Feedback, Admin Users)
├── models_refactor.py  # Extended Database Models (Branch/RO management)
└── main.py             # Application Entry Point
```

## 🚀 Setup & Installation

### 1. Prerequisites
- Python 3.9+
- PostgreSQL (recommended) or SQLite

### 2. Configuration
Create a `.env` file in the `Backend` directory with the following variables:

```env
DATABASE_URL=sqlite:///./database.db  # or postgresql://user:pass@localhost/db
SECRET_KEY=your_secret_key_here
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_hashed_password_here # Run `python -m services.generate_hash` to generate
ACCESS_TOKEN_EXPIRE_MINUTES=60
ALGORITHM=HS256

# Email Configuration (for Reports)
MAIL_USERNAME=your_email@example.com
MAIL_PASSWORD=your_password
MAIL_FROM=your_email@example.com
MAIL_PORT=587
MAIL_SERVER=smtp.gmail.com
MAIL_FROM_NAME=Feedback System
MAIL_TO=admin@example.com  # For multiple recipients: email1@example.com,email2@example.com,email3@example.com

# WhatsApp (Optional)
ENABLE_WHATSAPP=True
WHATSAPP_TOKEN=your_meta_token
WHATSAPP_PHONE_ID=your_phone_id
```

### 3. Installation
Install the required dependencies:
```bash
pip install fastapi uvicorn[standard] sqlmodel pydantic-settings python-jose[cryptography] passlib[bcrypt] httpx apscheduler fpdf fastapi-mail python-multipart
```

### 4. Initialization
Initialize the database and create a default admin user:
```bash
python scripts/init_admin.py
```

## ▶️ Running the Application

Start the development server:
```bash
uvicorn main:app --reload
```
The API will be available at `http://localhost:8000`.
Access the interactive API docs at `http://localhost:8000/docs`.

## 🛠️ Utility Scripts
Check the `scripts/` directory for maintenance tools:
- `add_user.py`: CLI tool to add new admins, ROs, or FOs.
- `generate_hash.py`: Located in `services/`. Run via `python -m services.generate_hash` to generate password hashes.

## 🔑 Key Features
- **Role-Based Access Control (RBAC)**: Support for Superuser, SRH, DRSM, DO, FO, and RO.
- **Excel User Onboarding**: Bulk upload users with full 5-level hierarchy (SRH -> DRSM -> DO -> FO -> RO) mapping. 
  - **Additive Updates**: New uploads only update RO codes in the file, preserving existing mappings for other RO codes.
- **Automated Reporting**: Daily PDF reports sent via email (supports multiple recipients).
- **WhatsApp Integration**: Bi-directional communication for feedback collection.
- **Visual Analytics**: Admin dashboard with trend charts, hierarchy views, and rating distributions.
