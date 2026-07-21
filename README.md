# AP Invoice Intelligence - AI Powered MCP Server

## Overview

**AP Invoice Intelligence** is an AI-powered Accounts Payable automation system built using the **Model Context Protocol (MCP)**.

The application extracts invoice information from PDF/image/text/JSON invoices using a **local pdfplumber path for readable PDFs and text files**, plus a **configurable vision provider** for scanned documents when OCR is needed. It validates invoice completeness, detects duplicate invoices, normalizes vendor names, calculates payment terms, and stores processed invoices in a local SQLite database.

The latest extraction workflow now also captures detailed monetary adjustments on invoices, including discounts, shipping, freight, handling, insurance, packaging, tax/GST, and any additional named charges.

All business operations are exposed as MCP tools that can be accessed from **Claude Desktop**, **Cursor**, **VS Code**, and the **MCP Inspector**.

For a full breakdown of the server architecture, tools, libraries, and improvement ideas, see [MCP_SERVER_DOCUMENTATION.md](C:/Users/hp/Desktop/hackthon/MCP_SERVER_DOCUMENTATION.md).

---

# Features

* Local invoice extraction from readable PDFs and text files with no API key required
* AI-powered OCR fallback for scanned/image invoices
* Structured extraction of invoice header fields, totals, and line items
* Detailed monetary adjustment extraction
* Tax/GST extraction without assuming zero when other charges exist
* Discount extraction with both percentage and amount when explicitly shown
* Shipping, freight, handling, insurance, and packaging charge extraction
* Additional charge extraction as a named list of charge items
* Confidence scores preserved for every extracted field
* Vendor name normalization
* Duplicate invoice detection
* Payment terms calculation
* Invoice completeness validation
* SQLite database storage
* FastMCP server integration
* Configurable vision provider support for Gemini, Anthropic, or OpenAI

---

# Tech Stack

## Backend

* Python 3.12+
* FastMCP
* SQLAlchemy
* SQLite

## AI

* pdfplumber for local text extraction
* Optional vision providers: Gemini, Anthropic, or OpenAI

## Input Resolution

* Local file paths
* `file://` URIs
* HTTP/HTTPS URLs
* Uploaded file payloads
* Base64 PDF/image data
* Raw PDF/image bytes
* Invoice text
* Invoice JSON payloads

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

## 6. Install Optional Vision SDKs

You only need these if you want OCR for scanned PDFs or images.

```bash
python -m pip install google-genai anthropic openai
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
VISION_PROVIDER=
GEMINI_API_KEY=
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
```

Leave `VISION_PROVIDER` blank for local-only extraction. Set it to `gemini`, `anthropic`, or `openai` when you want OCR fallback.

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

Extract invoice information from invoice files or structured payloads.

Returns:

* Invoice Number
* Vendor Name
* Invoice Date
* Due Date
* Subtotal
* Tax / GST
* Discount Percentage
* Discount Amount
* Shipping Charges
* Freight Charges
* Handling Charges
* Insurance Charges
* Packaging Charges
* Other Charges
* Grand Total
* Line Items
* Confidence Scores

---

### process_invoice

Runs the full invoice pipeline.

Performs:

* Input resolution
* Gemini extraction
* Vendor normalization
* Duplicate detection
* Payment terms calculation
* Completeness validation
* Invoice persistence

Returns:

* Extracted invoice JSON
* Normalized vendor result
* Duplicate check result
* Payment terms result
* Completeness result
* Save result
* Step-by-step pipeline status

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

### list_pending_vendors

Lists vendors waiting for approval.

---

### approve_vendor

Approves a pending vendor and moves it into vendor master.

---

### reject_vendor

Rejects and removes a pending vendor.

---

# Sample Workflow

1. Upload Invoice PDF or text invoice
2. Readable PDFs and text files are parsed locally with `pdfplumber`
3. If the document is scanned, the configured vision provider performs OCR
4. Structured data is extracted, including discounts and charge adjustments
5. Normalize Vendor
6. Detect Duplicates
7. Calculate Payment Terms
8. Validate Completeness
9. Save to SQLite
10. Return JSON Response

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

## No vision provider configured

Readable PDFs and text files still work locally.

If you pass a scanned PDF or image, set `VISION_PROVIDER` and the matching API key for the provider you want to use.

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
VISION_PROVIDER=gemini
GEMINI_API_KEY=YOUR_API_KEY
```

Restart the server after updating the key.

---

# Future Improvements

* PaddleOCR/Tesseract Integration
* Fraud Detection
* Invoice Approval Workflow
* REST API
* Docker Support
* PostgreSQL/MySQL
* Cloud Storage Integration

---

# License

Developed for educational and hackathon purposes.

---
