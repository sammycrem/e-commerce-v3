# Architectural Design Documentation

## 1. Introduction
This document provides a comprehensive overview of the e-commerce application's architecture. The application is a monolithic web service built using Flask (Python), designed to handle product management, order processing, user accounts, and administrative functions. It utilizes server-side rendering with Jinja2 templates, augmented by client-side JavaScript for dynamic interactions.

## 2. High-Level Architecture

The system follows a traditional Model-View-Controller (MVC) pattern adapted for Flask (Model-View-Template).

```mermaid
graph TD
    Client[Client Browser]
    LoadBalancer[Nginx / Load Balancer (Optional)]
    AppServer[Flask Application Server (Gunicorn/Werkzeug)]
    Database[(SQL Database (SQLite/PostgreSQL))]
    FileSystem[File System (Static Assets)]

    Client -->|HTTP/HTTPS| LoadBalancer
    LoadBalancer -->|Proxy| AppServer
    AppServer -->|SQLAlchemy| Database
    AppServer -->|Read/Write| FileSystem
```

### Core Components
*   **Client**: Web browsers interacting via HTML, CSS, and JavaScript.
*   **Application Server**: Python Flask application handling routing, business logic, and API responses.
*   **Database**: Relational database (default: SQLite) storing application state.
*   **File System**: Stores user-uploaded content (product images) and static assets.

## 3. Technology Stack

*   **Backend Language**: Python 3.12+
*   **Web Framework**: Flask
*   **ORM**: SQLAlchemy (via Flask-SQLAlchemy)
*   **Template Engine**: Jinja2
*   **Frontend**:
    *   **Markup**: HTML5
    *   **Styling**: Bootstrap 5 (Responsive Design)
    *   **Scripting**: Vanilla JavaScript (ES6+)
*   **Database**: SQLite (Development/Default), compatible with PostgreSQL/MySQL.
*   **Deployment**: Docker (Containerization).

## 4. Backend Architecture

### 4.1. Application Factory Pattern
The application is initialized in `app/app.py` using the Factory Pattern (`create_app`). This approach facilitates testing and cleaner configuration management.

*   **Configuration**: Settings are loaded from `config.txt` and environment variables (e.g., `ENCRYPTION_KEY`).
*   **Extensions Initialization**: `db`, `login_manager`, `mail`, `limiter`, `cache`, `csrf`.

### 4.2. Blueprints (Modular Design)
The application logic is segmented into Blueprints to separate concerns:

| Blueprint | Path | Purpose |
| :--- | :--- | :--- |
| `main` | `app/blueprints/main.py` | Core pages (Home, Shop, Profile, Auth), Error handling. |
| `api` | `app/blueprints/api.py` | RESTful endpoints for AJAX calls (Product CRUD, Cart, Admin Reports). |
| `cart` | `app/blueprints/cart.py` | Shopping cart management logic. |
| `checkout` | `app/blueprints/checkout.py` | Order placement and payment processing integration (e.g., Mollie). |
| `account` | `app/blueprints/account.py` | User-specific dashboards and settings. |
| `countries` | `app/blueprints/countries.py` | Location-based logic (Shipping/VAT). |

### 4.3. Service Layer vs. View Layer
*   **View Layer (Routes)**: Handles request parsing, input validation, and response formatting (HTML or JSON).
*   **Service Logic**: Complex business rules (e.g., `products_to_csv`, `process_loyalty_reward`) are often encapsulated in utility modules like `app/product_service.py` or `app/utils.py`.

## 5. Database Design

The database uses a relational model managed by SQLAlchemy.

### 5.1. Entity-Relationship Diagram (ERD)

```mermaid
erDiagram
    User ||--o{ Order : places
    User ||--o{ Address : has
    User ||--o{ Review : writes
    User ||--o{ Message : sends
    User ||--o{ Promotion : owns

    Product ||--|{ Variant : has
    Product ||--|{ ProductImage : has
    Product ||--o{ Review : receives

    Variant ||--|{ VariantImage : has
    Variant ||--o{ OrderItem : included_in

    Order ||--|{ OrderItem : contains
    Order ||--|{ Message : has_log
    Order }|--|| User : belongs_to

    Country ||--|{ VatRate : has

    class User {
        int id
        string username
        string email
        string password_hash
        string encrypted_password
        boolean is_admin
    }

    class Product {
        int id
        string sku
        string name
        int base_price_cents
        string status
        json dimensions
    }

    class Variant {
        int id
        string sku
        string color
        string size
        int stock
        int price_modifier
    }

    class Order {
        int id
        string public_id
        string status
        int total_cents
        datetime created_at
    }
```

### 5.2. Key Models
*   **Product**: Central entity. Supports `status` ('draft', 'published', 'decommissioned').
*   **Variant**: SKU-based variations (Color/Size) linked to a parent Product.
*   **Order**: Tracks purchases, status workflow (PENDING -> PAID -> SHIPPED), and financial snapshots.
*   **User**: Stores authentication details and profile information.
*   **GlobalSetting**: Key-Value store for dynamic app configuration (e.g., Currency, VAT Mode).

## 6. Frontend Architecture

### 6.1. Template Structure
*   **Base Layout (`layout.html`)**: Defines the HTML skeleton, navigation bar, and footer.
*   **Blocks**: Child templates (e.g., `shop.html`, `admin.html`) extend `layout.html` and inject content into `{% block content %}`.

### 6.2. Client-Side Interactivity
The frontend uses **Unobtrusive JavaScript**.
*   **Data Fetching**: The `Fetch API` is used to communicate with the `api` Blueprint for actions like:
    *   Loading product lists (pagination/filtering).
    *   Updating cart quantities.
    *   Submitting admin forms (CRUD).
*   **State Management**: Complex pages (like the Admin Dashboard) maintain local state in JS variables (e.g., `currentProduct` in `admin_crud.js`) and synchronize with the backend.
*   **Admin Dashboard**: A Single-Page-Application (SPA)-like experience within a multi-page app, using tabs to switch views without full reloads, powered by `admin_reports.js`, `admin_gallery.js`, etc.

## 7. Security Architecture

### 7.1. Authentication & Authorization
*   **Flask-Login**: Manages user sessions.
*   **Role-Based Access**: The `check_admin` decorator/function enforces that only the configured `APP_ADMIN_USER` can access sensitive endpoints.
*   **Password Hashing**: Uses `werkzeug.security` (scrypt/pbkdf2) for hashing.

### 7.2. Data Protection
*   **Encryption**: Sensitive configuration values (like API keys) and specific user fields (`encrypted_password` for legacy/recovery purposes) are encrypted using `cryptography.fernet` with a server-side `ENCRYPTION_KEY`.
*   **Input Validation**: `secure_filename` is strictly used for all file uploads to prevent path traversal.
*   **CSRF Protection**: `Flask-WTF` / `CSRFProtect` is enabled globally. AJAX requests must include the `X-CSRFToken` header.

### 7.3. Network Security
*   **Rate Limiting**: `Flask-Limiter` protects auth endpoints (Login/Signup) from brute-force attacks.
*   **CSP**: Content Security Policy headers are injected to mitigate XSS (configured in `app.py`).

## 8. Development & Deployment

### 8.1. Docker
The application is containerized.
*   **Dockerfile**: Defines the python environment, installs dependencies from `requirements.txt`, and sets up the entry point.
*   **Volume Mounting**: The `/export` directory is typically mounted to persist the SQLite database and uploaded assets.

### 8.2. Configuration Management
*   **`config.txt`**: A flat-file configuration reader allows easy setup without complex environment injection in simple deployments.
*   **Environment Variables**: Critical secrets (like `ENCRYPTION_KEY`, `APP_RESET_CODE`) are read from the environment for security.

## 9. Key Workflows

### 9.1. Product Management (Admin)
1.  Admin logs in.
2.  Navigates to "Products" tab.
3.  JS fetches product list via `GET /api/admin/products`.
4.  Admin clicks "Edit" -> Modal opens with data.
5.  Admin saves -> `PUT /api/admin/products/<sku>`.
6.  Images are uploaded to `POST /api/admin/upload-image` and linked.

### 9.2. Checkout Process
1.  User adds items to cart (stored in Server-Side Session or Database Cart).
2.  Proceeds to Checkout.
3.  Address entered -> Shipping calculated based on `Country` and `ShippingZone`.
4.  Payment initiated -> Order created with status `PENDING`.
5.  Payment Provider Webhook triggers status update to `PAID`.
6.  Loyalty rewards calculated and assigned if applicable.
