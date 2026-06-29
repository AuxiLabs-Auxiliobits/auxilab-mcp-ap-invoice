# AP Invoice Intelligence - AI Powered MCP Server

## Overview

**AP Invoice Intelligence** is an AI-powered Accounts Payable automation system built as an **MCP (Model Context Protocol) Server**.

The system automatically extracts invoice information using **Google Gemini AI**, validates invoice completeness, detects duplicate invoices, normalizes vendor names, calculates payment terms, and stores processed invoices in a local SQLite database.

All capabilities are exposed as MCP tools, allowing AI assistants such as Claude Desktop, Cursor, VS Code, and the MCP Inspector to invoke them directly.

---

# Features

* AI-powered Invoice Extraction using Google Gemini
* PDF Text Extraction using pdfplumber
* Automatic OCR fallback for scanned/image invoices using Gemini Vision
* Structured Invoice JSON Output with Confidence Scores
* Vendor Name Normalization
* Duplicate Invoice Detection
* Payment Terms Calculation
* Invoice Completeness Validation
* SQLite Database Storage
* MCP Server exposing business tools
* Compatible with MCP Inspector and MCP Clients

---

# Tech Stack

## Backend

* Python 3.12
* FastMCP
* Google Gemini API
* SQLAlchemy
* SQLite

## AI

* Gemini 2.5 Flash
* Gemini Vision

## PDF Processing

* pdfplumber

## Database

* SQLite

## Utilities

* RapidFuzz
* Pydantic
* python-dotenv

---

# Project Structure

```
hackthon/

│
├── app/
│   ├── database/
│   │   ├── database.py
│   │   ├── models.py
│   │   └── seed.py
│   │
│   ├── schemas/
│   │   └── invoice.py
│   │
│   ├── services/
│   │   ├── gemini_service.py
│   │   ├── invoice_processor.py
│   │   └── pdf_parser.py
│   │
│   ├── tools/
│   │   ├── duplicate_detector.py
│   │   ├── vendor_normalizer.py
│   │   ├── payment_terms.py
│   │   └── completeness_checker.py
│   │
│   └── config.py
│
├── tests/
│
├── sample_invoice.pdf
├── vendor_master.db
├── main.py
├── requirements.txt
├── README.md
└── .env
```

---

# System Workflow

```
Invoice PDF / Image

        │

        ▼

PDF Parser (pdfplumber)

        │

        ▼

Gemini AI Extraction

        │

        ▼

Structured Invoice JSON

        │

 ┌──────────────┬──────────────┬──────────────┐
 ▼              ▼              ▼              ▼

Vendor      Duplicate     Payment Terms   Completeness
Normalize    Detection      Calculation     Checker

        │

        ▼

SQLite Database

        │

        ▼

FastMCP Server

        │

        ▼

Claude / Cursor / VS Code / MCP Inspector
```

---

# Installation

## 1. Clone Repository

```bash
git clone <repository-url>

cd hackthon
```

---

## 2. Create Virtual Environment

Windows

```bash
python -m venv venv

venv\Scripts\activate
```

Linux / macOS

```bash
python3 -m venv venv

source venv/bin/activate
```

---

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 4. Create Environment File

Create a file named

```
.env
```

Add

```
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
```

---

## 5. Seed Vendor Database

```bash
python app/database/seed.py
```

---

# Running the MCP Server

Start the server

```bash
python main.py
```

or

```bash
python -m main
```

---

# Running with MCP Inspector

Activate the virtual environment

```bash
venv\Scripts\activate
```

Start Inspector

```bash
mcp dev main.py
```

The Inspector opens automatically in your browser.

Connect using

```
Command:
python

Arguments:
main.py
```

Click **Connect** to access all MCP tools.

---

# Available MCP Tools

## 1. extract_invoice

Extract invoice information from PDF or image.

Input

```
sample_invoice.pdf
```

Returns

* Invoice Number
* Vendor
* Dates
* Totals
* Line Items
* Duplicate Detection

---

## 2. normalize_vendor

Normalizes vendor names against the Vendor Master.

Example

```
MSFT Corp.
```

Returns

```
Microsoft Corporation
```

---

## 3. detect_duplicate

Detects duplicate invoices using invoice number, vendor, amount, and invoice date.

Returns

* Duplicate Status
* Match Type
* Confidence

---

## 4. calculate_payment_terms

Calculates

* Due Date
* Discount Deadline
* Early Payment Discount
* Days Until Due

Supports

* Net 30
* Net 45
* Net 60
* Due on Receipt
* 2/10 Net 30
* 1/15 Net 45

---

## 5. check_completeness

Checks invoice completeness.

Returns

* Completeness Score
* Missing Fields
* Recommended Action

---

# Database

SQLite stores

* Processed Invoices
* Vendor Master

No external database installation is required.

---

# Sample Workflow

1. Upload Invoice PDF

↓

2. Extract Text

↓

3. Gemini AI extracts structured data

↓

4. Vendor Normalization

↓

5. Duplicate Detection

↓

6. Payment Terms Calculation

↓

7. Completeness Validation

↓

8. Save Invoice

↓

9. Return JSON Response

---

# Example Output

```json
{
    "invoice_number": {
        "value": "INV-3337",
        "confidence": 0.99
    },
    "vendor_name": {
        "value": "Microsoft Corporation",
        "confidence": 0.99
    },
    "grand_total": {
        "value": 1180.0,
        "confidence": 0.99
    }
}
```

---

# Future Improvements

* OCR using PaddleOCR/Tesseract
* Fraud Detection
* GST Validation
* Invoice Approval Workflow
* Multi-language Invoice Support
* PostgreSQL / MySQL Support
* Vendor Embedding Search
* REST API Integration
* Docker Deployment
* Cloud Storage Integration

---

# License

This project was developed for educational and hackathon purposes.

---

# Author

**Ashish Sharma**

Backend Developer

Built with Python, Gemini AI, SQLAlchemy, SQLite, FastMCP, and RapidFuzz.
