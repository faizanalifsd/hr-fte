# AI Job Application System - Backend

Python backend for the AI Job Application System implementing a 12-phase autonomous job application workflow with Human-in-the-Loop (HITL) approval.

## Architecture

### Tech Stack
- **Framework**: FastAPI
- **Database**: MySQL with SQLAlchemy ORM
- **AI Services**:
  - Claude Sonnet 4.5 (Orchestration)
  - Gemini Pro (Content Generation)
- **MCP Integrations**:
  - Apify (Job Scraping)
  - Gmail (Email Sending)

### Project Structure

```
backend/
├── app.py                      # FastAPI main application
├── requirements.txt            # Python dependencies
├── models/                     # Database models (SQLAlchemy)
│   ├── __init__.py
│   ├── mission.py              # Mission entity
│   ├── job.py                  # Job entity
│   ├── cv_version.py           # CV version entity
│   ├── email_draft.py          # Email draft entity
│   ├── application_record.py   # Application record entity
│   ├── execution_state.py      # Execution state entity
│   └── audit_log.py            # Audit log entity
├── services/                   # Business logic
│   ├── orchestrator.py         # Main workflow orchestrator
│   ├── ai/                     # AI service integrations
│   │   ├── claude_service.py   # Claude API integration
│   │   └── gemini_service.py   # Gemini API integration
│   └── mcp/                    # MCP integrations
│       ├── apify_service.py    # Apify MCP integration
│       └── gmail_service.py    # Gmail MCP integration
├── routes/                     # API endpoints
│   ├── mission_routes.py       # Mission CRUD
│   ├── job_routes.py           # Job management
│   ├── email_routes.py         # Email HITL approval
│   └── application_routes.py  # Application sending
├── config/                     # Configuration
│   ├── database.py             # Database configuration
│   └── env_loader.py           # Environment loader
└── utils/                      # Utilities (future)
```

## Setup

### 1. Prerequisites

- Python 3.10+
- MySQL 8.0+
- Virtual environment (recommended)

### 2. Install Dependencies

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Unix/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration

```bash
# Copy environment template
cp ../.env.example ../.env

# Edit .env and add your credentials
```

Required environment variables:
- `DATABASE_URL` - MySQL connection string
- `ANTHROPIC_API_KEY` - Claude API key
- `GEMINI_API_KEY` - Gemini API key
- `APIFY_API_KEY` - Apify API key
- `GMAIL_CLIENT_ID` - Gmail OAuth client ID
- `GMAIL_CLIENT_SECRET` - Gmail OAuth client secret
- `GMAIL_REFRESH_TOKEN` - Gmail OAuth refresh token

### 4. Database Setup

```bash
# Create MySQL database
mysql -u root -p
CREATE DATABASE job_application_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

# Database tables will be created automatically on first run
```

### 5. Run Development Server

```bash
# From backend directory
python -m uvicorn app:app --reload --port 8000

# Or using the app directly
python app.py
```

Server will start at: http://localhost:8000

## API Documentation

Once the server is running, access:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Workflow Phases

### Phase 1: Mission Initialization
```http
POST /api/missions/
{
  "user_input": "Apply to 20 Python Developer positions in Remote"
}
```

### Phase 2-3: CV Upload & Parsing
Handled within workflow execution

### Phase 4: Job Scraping
Automatically triggered during workflow

### Phase 5: Job Matching
Automatically scores jobs against CV

### Phase 6: CV Optimization
Generates tailored CV per job

### Phase 7: Email Generation
Creates personalized application emails

### Phase 8: HITL Approval
```http
# List pending approvals
GET /api/emails/pending

# Approve email
POST /api/emails/{email_id}/approve

# Reject email
POST /api/emails/{email_id}/reject

# Edit email
PATCH /api/emails/{email_id}
```

### Phase 9: Application Sending
```http
POST /api/applications/send
{
  "email_draft_id": 1,
  "cv_version_id": 1
}
```

### Phase 10-11: Audit & Validation
Automatic logging and mission completion tracking

## Governance Rules

As per `constitution.md`:

1. **No email sent without human approval** (HITL)
2. **Rate limiting**: Max 20 applications/day (configurable)
3. **Retry logic**: 3 attempts with exponential backoff
4. **Audit trail**: All actions logged immutably
5. **Security**: No credentials in code or database

## Model Assignment

### Claude Sonnet (Orchestrator)
- Mission parsing
- MCP tool invocation
- Governance enforcement
- HITL validation
- Final decisions

### Gemini Pro (Content Generation)
- CV parsing
- Job matching
- CV optimization
- Email generation
- Resume editing

**Security Rule**: Only Claude can invoke MCP tools.

## Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=backend

# Run specific test file
pytest tests/test_orchestrator.py
```

## Production Deployment

### Using Gunicorn

```bash
gunicorn app:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000
```

### Using Docker (future)

```bash
docker build -t job-application-backend .
docker run -p 8000:8000 --env-file .env job-application-backend
```

## Monitoring

### Health Check
```http
GET /health
```

### System Status
```http
GET /api/system/status
```

## Error Handling

All errors follow the retry policy:
- Max 3 retry attempts
- Exponential backoff (2s, 4s, 8s)
- Failures logged to `audit_logs` table

## Security Considerations

1. **API Keys**: All keys loaded from environment variables
2. **Database Credentials**: Stored securely in `.env`
3. **Rate Limiting**: Enforced per mission and globally
4. **Audit Trail**: Immutable logs for compliance
5. **CORS**: Restricted to frontend origin only

## Contributing

Follow Python best practices:
- Black for code formatting
- Type hints for all functions
- Docstrings for all public methods
- Unit tests for business logic

## License

Proprietary - Faizan Ali

## Support

For issues or questions, see `constitution.md` and `execution_plan.md`.
