# AP Invoice Intelligence - AI Powered MCP Server

## Overview

**AP Invoice Intelligence** is an AI-powered Accounts Payable automation system built using the **Model Context Protocol (MCP)**.

The application extracts invoice information from PDF/image invoices using **Google Gemini AI**, validates invoice completeness, detects duplicate invoices, normalizes vendor names, calculates payment terms, and stores processed invoices in a local SQLite database.

All business operations are exposed as MCP tools that can be accessed from **Claude Desktop**, **Cursor**, **VS Code**, and the **MCP Inspector**.

---

# Features

* AI-powered Invoice Extraction
* OCR fallback for scanned/image invoices
* Vendor Name Normalization
* Duplicate Invoice Detection
* Payment Terms Calculation
* Invoice Completeness Validation
* SQLite Database Storage
* FastMCP Server
* Google Gemini Integration

---

# Tech Stack

## Backend

* Python 3.12+
* FastMCP
* SQLAlchemy
* SQLite

## AI

* Google Gemini 2.5 Flash
* Gemini Vision

## PDF Processing

* pdfplumber

## Utilities

* RapidFuzz
* Pydantic
* python-dotenv

---

# Prerequisites

Install the following before running the project:

* Python 3.12 or later
* Git
* VS Code (recommended)

Verify Python installation:

```bash
python --version
```

---

# Project Structure

```text
hackthon/

│
├── app/
│   ├── database/
│   ├── schemas/
│   ├── services/
│   ├── tools/
│   └── config.py
│
├── tests/
├── sample_invoice.pdf
├── vendor_master.db
├── main.py
├── requirements.txt
├── README.md
└── .env
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
```

Linux/macOS

```bash
python3 -m venv venv
```

---

## 3. Activate Virtual Environment

### Windows PowerShell

```powershell
.\venv\Scripts\Activate.ps1
```

### Windows Command Prompt

```cmd
venv\Scripts\activate
```

### Linux/macOS

```bash
source venv/bin/activate
```

---

## 4. Upgrade pip

```bash
python -m pip install --upgrade pip
```

---

## 5. Install Project Dependencies

```bash
python -m pip install -r requirements.txt
```

> **Note**
>
> Always use:
>
> ```bash
> python -m pip
> ```
>
> instead of `pip` to avoid launcher issues on Windows.

---

## 6. Install Google Gemini SDK

If it is not included in `requirements.txt`, install it manually.

```bash
python -m pip install google-genai
```

Verify installation:

```bash
python -c "from google import genai; print('Google GenAI Installed')"
```

---

## 7. Install MCP CLI

The MCP Inspector requires the CLI dependencies.

```bash
python -m pip install "mcp[cli]"
```

---

## 8. Configure Environment Variables

Create a `.env` file in the project root.

```text
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
```

Obtain your API key from Google AI Studio.

---

## 9. Seed the Database

Run the seed script as a Python module.

```bash
python -m app.database.seed
```

Do **not** run:

```bash
python app/database/seed.py
```

Expected output:

```text
Vendor database already seeded.
```

or

```text
Vendor database seeded successfully.
```

---

# Running the Server

Start the MCP server:

```bash
python main.py
```

---

# Running the MCP Inspector

Open a second terminal.

Activate the virtual environment.

```bash
venv\Scripts\activate
```

Launch the inspector.

```bash
mcp dev main.py
```

When prompted, connect using:

Command

```text
python
```

Arguments

```text
main.py
```

Click **Connect**.

---

# Available MCP Tools

### extract_invoice

Extract invoice information from PDF/image files.

Returns:

* Invoice Number
* Vendor Name
* Invoice Date
* Line Items
* Totals
* Confidence Scores

---

### normalize_vendor

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

### detect_duplicate

Detects duplicate invoices using

* Vendor
* Invoice Number
* Amount
* Invoice Date

---

### calculate_payment_terms

Supports

* Net 30
* Net 45
* Net 60
* Due on Receipt
* 2/10 Net 30
* 1/15 Net 45

Returns

* Due Date
* Discount Deadline
* Days Until Due

---

### check_completeness

Returns

* Completeness Score
* Missing Fields
* Recommended Action

---

# Sample Workflow

1. Upload Invoice PDF
2. Extract Text
3. Gemini AI extracts structured data
4. Normalize Vendor
5. Detect Duplicates
6. Calculate Payment Terms
7. Validate Completeness
8. Save to SQLite
9. Return JSON Response

---

# Troubleshooting

## No module named 'app'

Use

```bash
python -m app.database.seed
```

instead of

```bash
python app/database/seed.py
```

---

## No module named 'google'

Install the Gemini SDK.

```bash
python -m pip install google-genai
```

---

## Error: typer is required

Install the MCP CLI.

```bash
python -m pip install "mcp[cli]"
```

---

## pip launcher error after moving the project

If you moved the project folder, delete the existing `venv` directory and recreate it.

```bash
python -m venv venv
```

Then reinstall all dependencies.

---

## Invalid Gemini API Key

Verify that your `.env` file contains:

```text
GEMINI_API_KEY=YOUR_API_KEY
```

Restart the server after updating the key.

---

# Future Improvements

* PaddleOCR/Tesseract Integration
* Fraud Detection
* GST Validation
* Invoice Approval Workflow
* REST API
* Docker Support
* PostgreSQL/MySQL
* Cloud Storage Integration

---

# License

Developed for educational and hackathon purposes.

---
