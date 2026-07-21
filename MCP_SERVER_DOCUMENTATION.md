# AP Invoice Intelligence MCP Server Documentation

This document explains the MCP server in this repository, what each tool does, which libraries power the workflow, and where the system can be improved next.

## 1. What This Server Does

The server is an **Accounts Payable invoice intelligence system** built on the **Model Context Protocol (MCP)**.

It is designed to:

* Extract structured data from invoices
* Normalize vendor names
* Detect duplicate invoices
* Calculate payment terms and early payment discounts
* Check invoice completeness
* Save invoice records into a local SQLite database
* Support multiple input formats, including file paths, PDFs, images, URLs, base64 payloads, raw bytes, invoice text, and invoice JSON

The main entrypoint is [main.py](C:/Users/hp/Desktop/hackthon/main.py), which registers all MCP tools and starts the FastMCP server.

---

## 2. High-Level Architecture

The codebase is organized into these layers:

* `main.py` exposes MCP tools
* `app/services/` handles input resolution, PDF parsing, Gemini extraction, fuzzy matching, and parsing helpers
* `app/tools/` contains the business tools used by MCP
* `app/schemas/` defines the invoice data model and request validation
* `app/repositories/` handles database access
* `app/database/` defines SQLAlchemy models and bootstrapping
* `app/core/` contains logging, errors, and response helpers

### Core flow

1. A tool receives an invoice input
2. `InvoiceInputResolver` normalizes the input into a common internal format
3. `GeminiService` extracts structured invoice fields
4. Business tools run validation, vendor matching, duplicate detection, and payment calculation
5. Results are saved into SQLite

---

## 3. Main Dependencies

### Google Gemini

Used in [app/services/gemini_service.py](C:/Users/hp/Desktop/hackthon/app/services/gemini_service.py) for invoice extraction.

Purpose:

* Read invoice text or document content
* Return structured JSON
* Extract line items and monetary fields

Why it matters:

* This is the AI layer that performs the actual invoice understanding

Enhancement ideas:

* Add document-layout-aware prompting
* Add schema-constrained output validation
* Add retries and response repair for malformed JSON
* Add field-level confidence calibration

### pdfplumber

Used in [app/services/pdf_parser.py](C:/Users/hp/Desktop/hackthon/app/services/pdf_parser.py).

Purpose:

* Extract readable text from PDF files

Why it matters:

* It provides a fast text-extraction path before falling back to Gemini file processing

Enhancement ideas:

* Add table extraction for line items
* Add page-level structure detection
* Add OCR fallback for scanned PDFs that have little or no embedded text

### RapidFuzz

Used in [app/services/fuzzy_match.py](C:/Users/hp/Desktop/hackthon/app/services/fuzzy_match.py) and [app/tools/vendor_normalizer.py](C:/Users/hp/Desktop/hackthon/app/tools/vendor_normalizer.py).

Purpose:

* Compare vendor names with fuzzy matching
* Improve vendor normalization and duplicate detection

Enhancement ideas:

* Add alias dictionaries for known vendor variants
* Add domain/email-based vendor confirmation
* Add scoring explainability in tool responses

### SQLAlchemy + SQLite

Used in [app/database/database.py](C:/Users/hp/Desktop/hackthon/app/database/database.py), [app/database/models.py](C:/Users/hp/Desktop/hackthon/app/database/models.py), [app/repositories/](C:/Users/hp/Desktop/hackthon/app/repositories), and [app/database/bootstrap.py](C:/Users/hp/Desktop/hackthon/app/database/bootstrap.py).

Purpose:

* Store vendors, pending vendors, and processed invoices
* Persist extracted invoice results

Enhancement ideas:

* Add migrations with Alembic
* Move to PostgreSQL for multi-user deployments
* Add indexes for report-heavy queries

### Pydantic

Used in [app/schemas/invoice.py](C:/Users/hp/Desktop/hackthon/app/schemas/invoice.py) and [app/schemas/tool_requests.py](C:/Users/hp/Desktop/hackthon/app/schemas/tool_requests.py).

Purpose:

* Validate tool inputs
* Normalize invoice payloads
* Enforce the structured response schema

Enhancement ideas:

* Add stricter field validators for currency formats
* Add auto-normalization for common invoice aliases

---

## 4. MCP Tools

The server exposes the following MCP tools from [main.py](C:/Users/hp/Desktop/hackthon/main.py).

### 4.1 `extract_invoice`

Purpose:

* Extract invoice fields from a file, URL, base64 payload, raw bytes, invoice text, or JSON

Implementation:

* Uses `InvoiceProcessor.extract_with_details`
* Uses `InvoiceInputResolver` to detect input type
* Uses `GeminiService` for extraction

Output includes:

* Invoice data
* Resolved input summary

Best use cases:

* When the caller only wants structured invoice data
* When debugging input parsing and extraction quality

Enhancements:

* Add page-level extraction traces
* Add a field-by-field extraction log
* Add OCR confidence summaries

### 4.2 `normalize_vendor`

Purpose:

* Normalize vendor names against the vendor master
* Queue unknown vendors for approval

Implementation:

* Uses [app/tools/vendor_normalizer.py](C:/Users/hp/Desktop/hackthon/app/tools/vendor_normalizer.py)
* Uses fuzzy scoring from [app/services/fuzzy_match.py](C:/Users/hp/Desktop/hackthon/app/services/fuzzy_match.py)
* Uses vendor storage from [app/repositories/vendor_repository.py](C:/Users/hp/Desktop/hackthon/app/repositories/vendor_repository.py)

Enhancements:

* Add vendor alias maps
* Add company suffix stripping rules
* Add human review hints for uncertain matches

### 4.3 `detect_duplicate`

Purpose:

* Check whether an invoice is an exact or near duplicate

Implementation:

* Uses [app/tools/duplicate_detector.py](C:/Users/hp/Desktop/hackthon/app/tools/duplicate_detector.py)
* Compares invoice number, vendor name similarity, amount variance, and invoice date window

Enhancements:

* Compare PO number, currency, and line-item signatures
* Add duplicate grouping and duplicate history explanations
* Add per-vendor duplicate thresholds

### 4.4 `calculate_payment_terms`

Purpose:

* Calculate due dates and early payment discounts from invoice terms

Implementation:

* Uses [app/tools/payment_terms.py](C:/Users/hp/Desktop/hackthon/app/tools/payment_terms.py)
* Supports `Due on Receipt`, `Net X`, and discount terms such as `2/10 Net 30`

Enhancements:

* Support more term formats such as `Net 15 EOM`
* Add business-day calendar support
* Add currency-aware discount reporting

### 4.5 `check_completeness`

Purpose:

* Determine whether the extracted invoice is complete enough for processing

Implementation:

* Uses [app/tools/completeness_checker.py](C:/Users/hp/Desktop/hackthon/app/tools/completeness_checker.py)
* Checks required fields such as invoice number, vendor name, invoice date, due date, subtotal, tax, and grand total

Enhancements:

* Make required fields configurable by vendor or region
* Add weighted completeness scoring
* Include missing monetary adjustment fields in the score

### 4.6 `process_invoice`

Purpose:

* Run the full end-to-end invoice pipeline

Pipeline steps:

1. Resolve the input
2. Extract invoice data with Gemini
3. Normalize the vendor
4. Detect duplicates
5. Calculate payment terms
6. Check completeness
7. Queue unknown vendors if needed
8. Save the invoice

Implementation:

* Uses [app/services/invoice_processor.py](C:/Users/hp/Desktop/hackthon/app/services/invoice_processor.py)

Enhancements:

* Add transactional rollback if any critical step fails
* Add richer step timing metrics
* Add a final decision object such as `approve`, `hold`, or `return_to_vendor`

### 4.7 `list_pending_vendors`

Purpose:

* Show vendors waiting for approval

Implementation:

* Uses [app/tools/vendor_onboarding.py](C:/Users/hp/Desktop/hackthon/app/tools/vendor_onboarding.py)

Enhancements:

* Add filters by date, country, or source invoice
* Add search and pagination

### 4.8 `approve_vendor`

Purpose:

* Move a pending vendor into the vendor master

Implementation:

* Uses [app/tools/vendor_onboarding.py](C:/Users/hp/Desktop/hackthon/app/tools/vendor_onboarding.py)

Enhancements:

* Add audit logs for approvals
* Add approval reason tracking

### 4.9 `reject_vendor`

Purpose:

* Remove a pending vendor entry

Implementation:

* Uses [app/tools/vendor_onboarding.py](C:/Users/hp/Desktop/hackthon/app/tools/vendor_onboarding.py)

Enhancements:

* Add rejection notes
* Add soft-delete instead of hard-delete

---

## 5. Invoice Extraction Model

The extracted invoice schema is defined in [app/schemas/invoice.py](C:/Users/hp/Desktop/hackthon/app/schemas/invoice.py).

It currently supports:

* Invoice number
* Vendor name
* Invoice date
* Due date
* Subtotal
* Tax
* Grand total
* Discount percentage
* Discount amount
* Shipping charges
* Freight charges
* Handling charges
* Insurance charges
* Packaging charges
* Other charges
* Line items

### Why this matters

This schema is the contract between Gemini and the rest of the system. If the schema is incomplete, the downstream tools will miss real invoice data.

### Enhancement ideas

* Add line-item tax columns
* Add per-charge confidence thresholds
* Add richer charge metadata such as taxability and category
* Add support for multi-currency invoices

---

## 6. Input Handling

Input resolution is handled by [app/services/invoice_inputs.py](C:/Users/hp/Desktop/hackthon/app/services/invoice_inputs.py).

Supported input types:

* Local file paths
* `file://` URIs
* HTTP/HTTPS URLs
* Uploaded file payloads
* Base64-encoded PDF/image data
* Raw bytes and byte arrays
* Invoice text
* Invoice JSON

### Purpose

This layer makes the server flexible enough to handle different client integrations without changing the extraction pipeline.

### Enhancement ideas

* Add MIME-based routing for more file types
* Add automatic image preprocessing
* Add source provenance metadata in tool responses

---

## 7. Storage Layer

### Database models

Defined in [app/database/models.py](C:/Users/hp/Desktop/hackthon/app/database/models.py).

Tables:

* `vendors`
* `pending_vendors`
* `processed_invoices`

### Repositories

* [app/repositories/vendor_repository.py](C:/Users/hp/Desktop/hackthon/app/repositories/vendor_repository.py)
* [app/repositories/invoice_repository.py](C:/Users/hp/Desktop/hackthon/app/repositories/invoice_repository.py)

### Purpose

* Persist vendor master data
* Persist pending vendor approvals
* Persist extracted invoices and duplicate detection history

### Enhancement ideas

* Add migrations
* Add invoice revision history
* Add field-level audit logging

---

## 8. Supporting Utilities

### `FuzzyMatcher`

File: [app/services/fuzzy_match.py](C:/Users/hp/Desktop/hackthon/app/services/fuzzy_match.py)

Purpose:

* Normalize text
* Compare vendor names
* Support duplicate detection and vendor matching

### `Number Parser`

File: [app/services/number_parser.py](C:/Users/hp/Desktop/hackthon/app/services/number_parser.py)

Purpose:

* Convert numeric strings like `10%`, `$1,234.50`, and `(123.45)` into floats

Why it matters:

* Prevents save-time failures when Gemini returns human-formatted values

### `PDFParser`

File: [app/services/pdf_parser.py](C:/Users/hp/Desktop/hackthon/app/services/pdf_parser.py)

Purpose:

* Extract text from PDF files before Gemini processing

### `DateNormalizer`

File: [app/services/date_normalizer.py](C:/Users/hp/Desktop/hackthon/app/services/date_normalizer.py)

Purpose:

* Convert invoice dates into a consistent ISO format

---

## 9. Error Handling and Responses

### Errors

Defined in [app/core/errors.py](C:/Users/hp/Desktop/hackthon/app/core/errors.py).

Purpose:

* Convert Python exceptions into structured application errors

### Responses

Defined in [app/core/responses.py](C:/Users/hp/Desktop/hackthon/app/core/responses.py).

Purpose:

* Standardize success and error payloads returned by MCP tools

### Logging

Defined in [app/core/logging.py](C:/Users/hp/Desktop/hackthon/app/core/logging.py).

Purpose:

* Write logs to console and rotating log files

---

## 10. Current Strengths

* Flexible invoice input support
* AI extraction backed by Gemini
* Structured Pydantic validation
* Vendor matching and onboarding workflow
* Duplicate detection
* Payment term calculation
* SQLite persistence
* Clear MCP tool boundaries

---

## 11. Recommended Enhancements

If you want to improve the server further, the best next steps are:

1. Add automated tests for each MCP tool
2. Add invoice-specific extraction fixtures for different vendors and layouts
3. Add OCR fallback for scanned PDFs
4. Add a richer schema for charge breakdowns and line-item taxes
5. Add migration support with Alembic
6. Add a REST API wrapper for non-MCP consumers
7. Add export features for CSV/Excel
8. Add approval workflow dashboards
9. Add stronger vendor alias resolution
10. Add confidence-based review rules

---

## 12. Short Summary

This MCP server is an invoice-processing pipeline that combines:

* **Google Gemini** for extraction
* **pdfplumber** for PDF text extraction
* **RapidFuzz** for vendor matching
* **Pydantic** for schema validation
* **SQLAlchemy + SQLite** for persistence

Its purpose is to turn messy invoice inputs into clean, structured AP data that can be validated, normalized, deduplicated, and stored.

