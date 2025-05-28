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
- **Database**: SQLite (development) / PostgreSQL (production)
- **ORM**: SQLModel
- **Authentication**: JWT with bcrypt password hashing
- **Validation**: Pydantic schemas
- **Documentation**: Auto-generated OpenAPI/Swagger docs

## Quick Start

### Prerequisites

- Python 3.11+
- uv (recommended) or pip

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

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Run the development server**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

6. **Access the API**
   - API: http://localhost:8000
   - Documentation: http://localhost:8000/docs
   - Alternative docs: http://localhost:8000/redoc

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

## Configuration

Key environment variables in `.env`:

```env
# Database
DATABASE_URL=sqlite:///./quiz_app.db

# JWT Security
JWT_SECRET_KEY=your-secret-key
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

# CORS
CORS_ORIGINS=["http://localhost:8501"]

# Email (for student notifications)
SMTP_HOST=smtp.gmail.com
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
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
   - Use PostgreSQL for DATABASE_URL
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