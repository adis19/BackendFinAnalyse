# Bank Reports API

A FastAPI-based backend service for collecting and analyzing financial reports from Kyrgyzstan banks.

## Features

- Collects financial reports from multiple banks:
  - KICB Bank
  - Optima Bank
  - DemirBank
- Searches reports by date range
- RESTful API for retrieving the collected data
- Easily extensible to add more banks

## Setup

1. Clone the repository
2. Create a virtual environment:
```
python -m venv venv
```
3. Activate the virtual environment:
```
# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```
4. Install dependencies:
```
pip install -r requirements.txt
```

## Running the application

```
uvicorn main:app --reload
```

The API will be available at http://localhost:8000

## API Documentation

After starting the application, you can access:
- API docs: http://localhost:8000/docs
- OpenAPI spec: http://localhost:8000/openapi.json

## API Endpoints

### GET /reports

Get bank financial reports between specified dates.

**Parameters:**
- `start_date`: Start date for report search (YYYY-MM-DD)
- `end_date`: (Optional) End date for report search (YYYY-MM-DD)
- `bank_id`: (Optional) Bank ID (1=KICB, 2=Optima, 3=DemirBank, None=All banks)

**Example:**
```
GET /reports?start_date=2023-01-01&end_date=2023-12-31&bank_id=1
```

## Project Structure

```
.
├── app/
│   ├── __init__.py
│   └── parsers/
│       ├── __init__.py
│       ├── base_parser.py
│       ├── bank_kicb.py
│       ├── bank_optima.py
│       ├── bank_demirbank.py
│       └── parser_service.py
├── main.py
├── requirements.txt
└── README.md
``` 