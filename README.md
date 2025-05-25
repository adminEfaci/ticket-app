# Ticket Management System

A comprehensive ticket management system for processing weight tickets from XLS/PDF pairs, with automatic client assignment, rate management, and weekly billing exports.

## 🚀 Features

### Core Functionality
- **Batch Upload & Processing**: Upload XLS/PDF pairs for automatic parsing
- **Smart Ticket Parsing**: Multi-row XLS support with intelligent field extraction
- **PDF Image Extraction**: Automatic ticket image extraction and OCR processing
- **Client Management**: Reference-based client assignment with pattern matching
- **Rate Management**: Time-based rate tracking with approval workflows
- **Weekly Export System**: Automated invoice generation with image organization

### Key Capabilities
- ✅ Process weight tickets (ORIGINAL, REPRINT, VOID)
- ✅ Extract images from multi-page PDFs
- ✅ Match tickets to clients via reference patterns
- ✅ Calculate billing with configurable rates
- ✅ Generate weekly invoices grouped by client/reference
- ✅ Full audit trail for compliance

## 📋 Prerequisites

- Python 3.12+
- PostgreSQL 13+ (or Docker)
- Tesseract OCR
- Poppler (for PDF processing)

## 🛠️ Installation

### 1. Clone the repository
```bash
git clone https://github.com/adminEfaci/ticket-app.git
cd ticket-app
```

### 2. Create virtual environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Install system dependencies

**macOS:**
```bash
brew install tesseract poppler
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr poppler-utils
```

### 5. Set up PostgreSQL

**Option A: Using Docker**
```bash
docker-compose up -d
```

**Option B: Local PostgreSQL**
Create a database and update the connection string in `.env`

### 6. Configure environment
```bash
cp .env.example .env
# Edit .env with your settings
```

### 7. Initialize database
```bash
python -c "from backend.core.database import create_db_and_tables; create_db_and_tables()"
```

### 8. Create admin user
```bash
python -m backend.scripts.create_admin
```

## 🚦 Quick Start

### 1. Start the server
```bash
uvicorn main:app --reload
```

### 2. Access the API
- API Documentation: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

### 3. Upload and process tickets
```bash
# Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your-password"}'

# Upload batch
curl -X POST http://localhost:8000/api/upload/batch \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "xls_file=@sample.xls" \
  -F "pdf_file=@sample.pdf"

# Process batch
curl -X POST http://localhost:8000/api/batch/{batch_id}/process \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## 📊 Weekly Export System

### Generate weekly invoices
```bash
# Quick export for a week
curl -o export.zip http://localhost:8000/api/export/invoices-bundle/2024-04-15 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Export Structure
```
invoices_export.zip
├── merged.csv                 # All tickets with billing info
├── week_2024-04-15/          # Week folder (Monday-Saturday)
│   ├── manifest.csv          # Weekly summary
│   ├── client_Client_007/    # Client folder
│   │   ├── invoice.csv       # Client invoice
│   │   └── tickets/          # Ticket images
│   │       ├── #007/        # Reference folder
│   │       │   ├── 4121.png # Ticket images
│   │       │   └── 4122.png
│   │       └── MM1001/
│   │           └── 4123.png
│   └── client_Client_004/
│       └── ...
└── audit.json               # Validation report (if issues)
```

## 🧪 Testing

### Run all tests
```bash
pytest
```

### Run with coverage
```bash
pytest --cov=backend --cov-report=html
```

### E2E Export Test
```bash
python test_export_e2e.py sample.xls sample.pdf --date 2024-04-15
```

## 📁 Project Structure

```
ticket-app/
├── backend/
│   ├── core/           # Core functionality (auth, database)
│   ├── models/         # SQLModel/Pydantic models
│   ├── routers/        # FastAPI endpoints
│   ├── services/       # Business logic
│   ├── middleware/     # Auth middleware
│   ├── utils/          # Utility functions
│   └── tests/          # Unit and integration tests
├── exports/            # Generated export files
├── volumes/            # File storage
├── main.py            # FastAPI application
├── requirements.txt   # Python dependencies
├── docker-compose.yml # Docker configuration
└── test_export_e2e.py # E2E test script
```

## 🔧 Configuration

### Environment Variables
```env
DATABASE_URL=postgresql://user:password@localhost/ticketdb
SECRET_KEY=your-secret-key-here
ENVIRONMENT=development
```

`SECRET_KEY` must remain constant between application restarts so that JWT tokens
issued to users stay valid. Provide a strong value via environment variable in
production.

### Client Reference Patterns
Clients are assigned based on reference patterns:
- `#007` → Client 007
- `T-xxx` → TOPPS client
- `MM1001` → Custom pattern

## 🚀 Deployment

### Using Docker
```bash
docker build -t ticket-app .
docker run -p 8000:8000 --env-file .env ticket-app
```

### Production Considerations
- Use a production database (PostgreSQL)
- Set strong SECRET_KEY
- Enable HTTPS
- Configure proper CORS origins
- Set up regular backups
- Monitor disk space for exports

## 📝 API Documentation

Full API documentation is available at `/docs` when the server is running.

### Key Endpoints
- `POST /auth/login` - User authentication
- `POST /auth/register` - Public user registration
- `POST /upload/pairs` - Upload XLS/PDF pair
- `POST /batches/{id}/parse` - Process uploaded batch
- `GET /api/export/invoices-bundle/{date}` - Generate weekly export
- `POST /api/clients` - Manage clients
- `POST /api/clients/{id}/rates` - Manage client rates

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- FastAPI for the excellent web framework
- SQLModel for the ORM
- Tesseract for OCR capabilities
- The Python community for amazing libraries