# BSB Checker API

A FastAPI-based API service that provides lookup capabilities for Australian Bank-State-Branch (BSB) numbers. The API fetches the latest BSB data from the official source and allows querying BSB details.

## Overview

The BSB Checker API is designed to:

1. Download and process the official BSB database from [AusPayNet](https://bsb.auspaynet.com.au)
2. Store the BSB data in a SQLite database
3. Provide an API endpoint to query BSB details
4. Allow manual triggering of database updates

This application is useful for validating BSB numbers and retrieving associated bank and branch information for Australian financial institutions.

## Features

- **BSB Lookup**: Query detailed information for any valid Australian BSB number
- **Automatic Database Updates**: Database is automatically updated on startup
- **Manual Updates**: Trigger a manual update of the BSB database via API
- **Comprehensive Data**: Returns full details including bank name, branch, address, and supported payment systems

## Requirements

- Python 3.8+
- Dependencies listed in `requirements.txt`

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/msftcse-quokka/hve-demo.git
   cd hve-demo
   ```

2. Install the required dependencies:
   ```bash
   pip install -r bsb_checker_app/requirements.txt
   ```

## Running the Application

To start the application, run:

```bash
uvicorn bsb_checker_app.main:app --reload
```

The API will be available at: http://localhost:8000

On first run, the application will automatically download and process the BSB database.

## API Endpoints

### Get BSB Details

```
GET /bsb/{bsb_number}
```

Get details for a specific BSB number in the format XXX-XXX.

Example request:
```bash
curl http://localhost:8000/bsb/012-040
```

Example response:
```json
{
  "bsb": "012-040",
  "bankName": "Australia and New Zealand Banking Group Limited",
  "branchName": "Martin Place",
  "street": "20 Martin Place",
  "suburb": "Sydney",
  "state": "NSW",
  "postCode": "2000",
  "supportedPaymentSystem": "DE PE CS NB"
}
```

### Update BSB Database

```
POST /update-bsb
```

Trigger a manual update of the BSB database. The update runs in the background.

Example request:
```bash
curl -X POST http://localhost:8000/update-bsb
```

Example response:
```json
{
  "message": "BSB database update initiated in the background."
}
```

## Testing

Run the tests using pytest:

```bash
cd hve-demo
pytest bsb_checker_app/test_main.py
```

The test suite uses an in-memory SQLite database for testing to ensure isolation from the production database.

## Demo Requests

The `demo_requests` directory contains sample REST client requests that can be used with VS Code REST Client or similar tools:

- `get_bsb_number.rest` - Example of querying a BSB number
- `update_database.rest` - Example of triggering a database update

## Architecture

The application is built using:

- **FastAPI**: A modern, fast web framework for building APIs
- **SQLAlchemy**: SQL toolkit and Object-Relational Mapping (ORM) for database operations
- **Pandas**: Data manipulation library used for processing CSV data
- **SQLite**: Lightweight database for storing BSB information

## Data Source

The BSB data is sourced from the official AusPayNet BSB database:
https://bsb.auspaynet.com.au/Public/BSB_DB.NSF/getBSBFullCSV?OpenAgent

## License

[Add your license information here]

## Contributing

[Add contribution guidelines if applicable]