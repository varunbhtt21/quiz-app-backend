# Quiz App Backend

A FastAPI-based backend for a comprehensive quiz/assessment platform with role-based access control.

## Features

- **Role-based Authentication**: Admin and Student roles with JWT tokens
- **MCQ Problem Bank**: Global repository of multiple-choice questions
- **Course Management**: Create courses and enroll students
- **Contest System**: Time-based quizzes with auto-submission
- **Scoring Engine**: Automatic grading with exact set matching
- **Excel Export**: Download consolidated results in Excel format

## Tech Stack

- **Framework**: FastAPI 0.104.1
- **Database**: Supabase PostgreSQL (production) / SQLite (local development)
- **ORM**: SQLModel
- **Authentication**: JWT with bcrypt password hashing
- **Validation**: Pydantic schemas
- **Documentation**: Auto-generated OpenAPI/Swagger docs

## Quick Start

### Prerequisites

- Python 3.11+
- uv (recommended) or pip
- Supabase account (for database)

### Installation

1. **Clone and navigate to the backend directory**
   ```bash
   cd quiz-app-backend
   ```

2. **Create virtual environment**
   ```bash
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   uv pip install -r requirements.txt
   ```

4. **Set up Supabase Database**
   
   a. **Create a Supabase project**:
      - Go to [supabase.com](https://supabase.com) and create a new project
      - Note your project URL and password
   
   b. **Configure database access**:
      - In Supabase dashboard, go to Settings → Database
      - Find your connection string (should look like):
        ```
        postgresql://postgres:[YOUR-PASSWORD]@db.[PROJECT-ID].supabase.co:5432/postgres
        ```
   
   c. **Create .env file**:
      ```bash
      # Create .env file with your Supabase credentials
      DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.[PROJECT-ID].supabase.co:5432/postgres
      JWT_SECRET_KEY=your-super-secret-jwt-key-change-this-in-production
      JWT_ALGORITHM=HS256
      JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
      APP_NAME=QuizMaster by Jazzee
      DEBUG=true
      CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
      FRONTEND_URL=http://localhost:5173
      BCRYPT_ROUNDS=12
      ```

5. **Test database connection**
   ```bash
   python test_supabase_connection.py
   ```

6. **Initialize database tables**
   ```bash
   python init_db.py
   ```

7. **Run the development server**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

8. **Access the API**
   - API: http://localhost:8000
   - Documentation: http://localhost:8000/docs
   - Alternative docs: http://localhost:8000/redoc

## Supabase Configuration

### Database Setup

Your `.env` file should contain **both** connection strings:

```env
# Database Configuration (Supabase)

# Pooled connection for application runtime (port 6543)
DATABASE_URL=postgresql://postgres.[PROJECT_ID]:[PASSWORD]@aws-0-ap-south-1.pooler.supabase.com:6543/postgres

# Direct connection for migrations and admin operations (port 5432)  
DIRECT_URL=postgresql://postgres.[PROJECT_ID]:[PASSWORD]@aws-0-ap-south-1.pooler.supabase.com:5432/postgres

# JWT Configuration  
JWT_SECRET_KEY=your-super-secret-jwt-key-change-this-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

# Application Configuration
APP_NAME=QuizMaster by Jazzee
APP_VERSION=1.0.0
DEBUG=true

# CORS Origins (add your frontend URLs)
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173

# Frontend Configuration
FRONTEND_URL=http://localhost:5173

# Security
BCRYPT_ROUNDS=12
```

### Connection Types Explained

#### **DATABASE_URL (Pooled Connection)**
```bash
postgresql://postgres.[PROJECT_ID]:[PASSWORD]@aws-0-ap-south-1.pooler.supabase.com:6543/postgres
```
- **Port**: `6543` (Connection pooled)
- **Used for**: Runtime application queries, API endpoints
- **Benefits**: Handles many concurrent connections efficiently
- **Note**: Our app automatically removes `?pgbouncer=true` parameter for compatibility

#### **DIRECT_URL (Direct Connection)**  
```bash
postgresql://postgres.[PROJECT_ID]:[PASSWORD]@aws-0-ap-south-1.pooler.supabase.com:5432/postgres
```
- **Port**: `5432` (Direct connection)
- **Used for**: Database migrations, schema changes, admin operations
- **Benefits**: Full PostgreSQL feature support, no connection limits

### Getting Your Supabase Connection Strings

1. **Login to Supabase Dashboard**: https://supabase.com/dashboard
2. **Select your project**
3. **Go to Settings → Database**
4. **Copy both connection strings**:
   - **Connection pooling** (port 6543) → use as `DATABASE_URL`
   - **Direct connection** (port 5432) → use as `DIRECT_URL`
5. **Replace `[YOUR-PASSWORD]`** with your database password

### Troubleshooting Supabase Connection

If you get connection errors:

1. **Check IP allowlist**: In Supabase dashboard → Settings → Database → Network restrictions
2. **Verify credentials**: Make sure password is correct in both URLs
3. **Test connection**: Run `python test_supabase_connection.py`
4. **Use DIRECT_URL for migrations**: Our init script automatically prefers `DIRECT_URL`

### Storage Setup

The Quiz App uses Supabase Storage for image uploads. To enable image functionality:

1. **Add Storage Configuration to .env**:
   ```env
   # Supabase Storage Configuration
   SUPABASE_URL=https://your-project-id.supabase.co
   SUPABASE_KEY=your-anon-key-here
   SUPABASE_STORAGE_BUCKET=quiz-images
   ```

2. **Get Supabase Keys**:
   - Go to Settings → API in your Supabase dashboard
   - Copy the **URL** and **anon/public** key

3. **Test Storage Setup**:
   ```bash
   python test_storage.py
   ```

4. **Features**:
   - Automatic bucket creation
   - Image validation (JPEG, PNG, GIF, WebP)
   - Size limits (5MB uploads, 10MB bulk imports)
   - CDN delivery for fast loading

For detailed setup instructions, see [SUPABASE_STORAGE_SETUP.md](./SUPABASE_STORAGE_SETUP.md)

## API Endpoints

### Authentication
- `POST /api/auth/login` - User login
- `GET /api/auth/me` - Get current user info
- `POST /api/auth/create-admin` - Create admin user (initial setup)
- `POST /api/auth/create-students` - Bulk create student accounts

### MCQ Problems
- `POST /api/mcq/` - Create MCQ problem
- `GET /api/mcq/` - List MCQ problems (with search & pagination)
- `GET /api/mcq/{id}` - Get specific MCQ problem
- `PUT /api/mcq/{id}` - Update MCQ problem
- `DELETE /api/mcq/{id}` - Delete MCQ problem

### Courses (Coming Soon)
- Course CRUD operations
- Student enrollment management

### Contests (Coming Soon)
- Contest creation with problem selection
- Time-based access control
- Student submission handling

## Database Models

### User
- Supports Admin and Student roles
- Email-based authentication
- Course association for students

### MCQProblem
- Global problem bank
- Multi-select correct answers
- Optional explanations
- Audit trail (created_by, timestamps)

### Course
- Instructor-owned courses
- Student enrollment

### Contest
- Time-bounded quizzes
- Deep-copied problems (immutable)
- Status tracking (Not Started/In Progress/Ended)

### Submission
- Student answers and scores
- Auto-submission on timeout
- Per-problem correctness tracking

## Development

### Project Structure
```
app/
├── main.py              # FastAPI application
├── core/                # Core functionality
│   ├── config.py        # Settings management
│   ├── database.py      # Database connection
│   └── security.py      # JWT & password utilities
├── models/              # SQLModel database models
├── schemas/             # Pydantic request/response schemas
├── api/                 # API route handlers
├── services/            # Business logic (coming soon)
└── utils/               # Utility functions
```

### Running Tests
```bash
pytest
```

### Database Migrations
```bash
# Initialize Alembic (if needed)
alembic init alembic

# Create migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head
```

## Initial Setup

1. **Create Admin User**
   ```bash
   curl -X POST "http://localhost:8000/api/auth/create-admin" \
        -H "Content-Type: application/json" \
        -d '{
          "email": "admin@example.com",
          "password": "admin123",
          "role": "admin"
        }'
   ```

2. **Login and Get Token**
   ```bash
   curl -X POST "http://localhost:8000/api/auth/login" \
        -H "Content-Type: application/json" \
        -d '{
          "email": "admin@example.com",
          "password": "admin123"
        }'
   ```

3. **Create MCQ Problems**
   Use the token in Authorization header: `Bearer <token>`

## Production Deployment

1. **Update environment variables**
   - Use Supabase PostgreSQL for DATABASE_URL
   - Set strong JWT_SECRET_KEY
   - Configure SMTP settings

2. **Use production ASGI server**
   ```bash
   gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
   ```

## Contributing

1. Follow conventional commit messages
2. Add tests for new features
3. Update documentation
4. Ensure code passes linting

## License

MIT License