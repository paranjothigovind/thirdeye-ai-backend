# TODO: Implement Login and Signup APIs with User Registration, Login, and Subscriptions

## Step 1: Add Dependencies
- [x] Update requirements.txt with SQLAlchemy, alembic, passlib, python-jose, python-jwt

## Step 2: Update Configuration
- [x] Add DATABASE_URL, SECRET_KEY, JWT_SECRET_KEY, ACCESS_TOKEN_EXPIRE_MINUTES to app/core/config.py

## Step 3: Create Database Setup
- [x] Create app/core/database.py for SQLAlchemy engine and session management

## Step 4: Create User and Subscription Models
- [x] Create app/models/user.py with User model
- [x] Create app/models/subscription.py with Subscription model

## Step 5: Implement Authentication Utilities
- [x] Create app/core/auth.py with password hashing, JWT token generation/validation

## Step 6: Create Auth API Routes
- [x] Create app/api/routes_auth.py with signup, login, and subscription endpoints

## Step 7: Update Main Application
- [x] Update app/main.py to include the new auth router

## Step 8: Add Authentication Middleware/Dependencies
- [x] Add auth dependencies for protected routes (optional for now)

## Followup Steps
- [x] Run database migrations to create tables
- [x] Test the new APIs
- [x] Integrate with existing routes for user-specific features
- [x] Update README with new API documentation
