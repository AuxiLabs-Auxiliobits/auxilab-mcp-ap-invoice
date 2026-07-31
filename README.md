# AP Invoice Intelligence MCP Server

AP Invoice Intelligence is a portable Accounts Payable MCP server for extracting invoice data, checking duplicates, normalizing vendor names, calculating payment terms, and validating completeness.

The project now supports two clear operating modes:

- Text PDFs use local extraction and do not require an API key.
- Scanned PDFs and images require a vision provider.

## Project Overview

This repository exposes invoice-processing capabilities through the Model Context Protocol (MCP). The core tools are:

- `extract_invoice`
- `normalize_vendor`
- `detect_duplicate`
- `calculate_payment_terms`
- `check_completeness`

The server stores processed records in local SQLite and starts with a single command.

## Architecture

```text
MCP Client / MCP Inspector
        |
        v
main.py
        |
        v
InvoiceProcessor
        |
        v
ExtractionRouter
    |                 |
    |                 +--> VisionProvider
    |                       |
    |                       +--> GeminiProvider
    |                       +--> OpenAIProvider
    |                       +--> AnthropicProvider
    |
    +--> LocalInvoiceExtractor
          |
          +--> pdfplumber + regex + Python parsing

Downstream processing remains unchanged:

Extracted JSON
        |
        +--> Duplicate detection
        +--> Vendor normalization
        +--> Payment terms calculation
        +--> Completeness validation
        +--> SQLite persistence
```

## Startup Behavior

Running `python main.py` will:

1. Load environment variables from `.env`
2. Initialize the SQLite tables if they do not already exist
3. Seed the vendor master if the database is empty
4. Start the MCP server over stdio

No separate database seed command is required.

## Installation

### 1. Clone the repository

```bash
git clone <repository-url>
cd hackthon
```

### 2. Create and activate a virtual environment

Windows:

```bash
python -m venv venv
.\venv\Scripts\Activate.ps1
```

Linux / macOS:

```bash
python -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install -r requirements.txt
```

Optional provider SDKs can be installed only if you plan to use them:

```bash
python -m pip install google-genai openai anthropic
```

### 4. Start the server

```bash
python main.py
```

## One-Command Startup

A new developer can now:

1. Clone the repository
2. Install dependencies
3. Run `python main.py`

That single startup command initializes SQLite automatically and starts the MCP server.

## Environment Variables

Copy `.env.example` to `.env` and edit values as needed.

```ini
VISION_PROVIDER=none
GEMINI_API_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
```

### `VISION_PROVIDER`

Controls which vision backend is used for scanned invoices and images.

- `gemini`
- `openai`
- `anthropic`
- `none`

### API keys

- `GEMINI_API_KEY` is required only when `VISION_PROVIDER=gemini`
- `OPENAI_API_KEY` is required only when `VISION_PROVIDER=openai`
- `ANTHROPIC_API_KEY` is required only when `VISION_PROVIDER=anthropic`

If `VISION_PROVIDER=none`, text PDFs still work locally without any API key.

## How Local Extraction Works

Text-based PDFs are routed to the local extractor when selectable text is present.

The local path uses:

- `pdfplumber` to extract text from PDF pages
- regex and Python parsing to identify invoice fields
- no LLM
- no API key

The local extractor attempts to populate the same JSON schema as the vision path and returns `null` for anything it cannot find.

Fields handled by local extraction include:

- Invoice Number
- Vendor Name
- Invoice Date
- Due Date
- PO Number
- Currency
- Subtotal
- Tax
- Total
- Payment Terms

If a field is not visible in the document, it is returned as `null`.

## How Scanned Invoices Work

If a PDF does not contain selectable text, the router treats it as scanned and sends it to the configured vision provider.

Images always use the vision provider.

Scanned invoice support requires one of:

- Gemini
- OpenAI
- Anthropic

If `VISION_PROVIDER=none`, scanned PDFs and images fail with a clear error message. Text PDFs still work locally.

## VISION_PROVIDER Configuration

### `VISION_PROVIDER=gemini`

Use Gemini for scanned PDFs and images.

- Requires `GEMINI_API_KEY`
- Lazily imports the Gemini SDK only when selected

### `VISION_PROVIDER=openai`

Use OpenAI for scanned PDFs and images.

- Requires `OPENAI_API_KEY`
- Lazily imports the OpenAI SDK only when selected

### `VISION_PROVIDER=anthropic`

Use Anthropic for scanned PDFs and images.

- Requires `ANTHROPIC_API_KEY`
- Lazily imports the Anthropic SDK only when selected

### `VISION_PROVIDER=none`

Disable vision processing.

- Text PDFs still work locally
- Scanned PDFs and images raise a meaningful exception
- No API key is required for text-only invoices

## Gemini Mode

Gemini mode processes scanned PDFs and images through Gemini Vision.

Use this mode when you want:

- cloud-based vision extraction
- OCR-like handling for image-only invoices
- minimal local setup beyond the API key

Example:

```ini
VISION_PROVIDER=gemini
GEMINI_API_KEY=your_key_here
```

## OpenAI Mode

OpenAI mode processes scanned PDFs and images through OpenAI vision models.

Example:

```ini
VISION_PROVIDER=openai
OPENAI_API_KEY=your_key_here
```

## Anthropic Mode

Anthropic mode processes scanned PDFs and images through Anthropic vision models.

Example:

```ini
VISION_PROVIDER=anthropic
ANTHROPIC_API_KEY=your_key_here
```

## No API Key Mode

Set:

```ini
VISION_PROVIDER=none
```

This mode is intended for text-based invoices only.

What works:

- Text PDFs with selectable text
- Local extraction
- Duplicate detection
- Vendor normalization
- Payment terms calculation
- Completeness validation

What does not work:

- Scanned PDFs
- Image-only invoices

## Example MCP Tool Usage

The MCP server exposes the following tools:

- `extract_invoice`
- `normalize_vendor`
- `detect_duplicate`
- `calculate_payment_terms`
- `check_completeness`

### Example: `extract_invoice`

Input:

```text
path/to/invoice.pdf
```

Example response:

```json
{
  "invoice": {
    "invoice_number": {
      "value": "INV-100245",
      "confidence": 0.95
    },
    "vendor_name": {
      "value": "ACME Corporation",
      "confidence": 0.95
    },
    "invoice_date": {
      "value": "2026-07-31",
      "confidence": 0.95
    },
    "due_date": {
      "value": "2026-08-30",
      "confidence": 0.95
    },
    "subtotal": {
      "value": 1000.0,
      "confidence": 0.95
    },
    "discount_percentage": {
      "value": null,
      "confidence": 0.0
    },
    "discount_amount": {
      "value": null,
      "confidence": 0.0
    },
    "tax": {
      "value": 180.0,
      "confidence": 0.95
    },
    "shipping_charges": {
      "value": null,
      "confidence": 0.0
    },
    "freight_charges": {
      "value": null,
      "confidence": 0.0
    },
    "handling_charges": {
      "value": null,
      "confidence": 0.0
    },
    "insurance_charges": {
      "value": null,
      "confidence": 0.0
    },
    "packaging_charges": {
      "value": null,
      "confidence": 0.0
    },
    "other_charges": [],
    "grand_total": {
      "value": 1180.0,
      "confidence": 0.95
    },
    "line_items": []
  },
  "duplicate": {
    "is_duplicate": false,
    "match_type": "Unique Invoice",
    "confidence": 1.0
  }
}
```

### Example: `normalize_vendor`

Input:

```text
MSFT Corp.
```

Example output:

```json
{
  "recognized": true,
  "input_vendor": "MSFT Corp.",
  "matched_vendor": "MSFT Corp.",
  "canonical_vendor": "Microsoft Corporation",
  "email": "accounts@microsoft.com",
  "country": "USA",
  "confidence": 100.0
}
```

## Example Workflow

```text
Text PDF
  -> LocalInvoiceExtractor
  -> Duplicate detection
  -> Vendor normalization
  -> Payment terms calculation
  -> Completeness validation
  -> SQLite save

Scanned PDF
  -> VisionProvider
  -> Duplicate detection
  -> Vendor normalization
  -> Payment terms calculation
  -> Completeness validation
  -> SQLite save
```

## Project Structure

```text
hackthon/
├── app/
│   ├── config.py
│   ├── database/
│   │   ├── database.py
│   │   ├── models.py
│   │   └── seed.py
│   ├── schemas/
│   │   └── invoice.py
│   ├── services/
│   │   ├── extraction_router.py
│   │   ├── gemini_service.py
│   │   ├── invoice_processor.py
│   │   ├── local_invoice_extractor.py
│   │   ├── pdf_parser.py
│   │   └── vision_provider.py
│   └── tools/
│       ├── completeness_checker.py
│       ├── duplicate_detector.py
│       ├── payment_terms.py
│       └── vendor_normalizer.py
├── main.py
├── requirements.txt
├── README.md
└── .env.example
```

## Troubleshooting

### `No module named 'app'`

Run the server from the project root:

```bash
python main.py
```

### `No module named 'google'`

This usually means `VISION_PROVIDER=gemini` is set but the Gemini SDK is not installed.

Install it only if needed:

```bash
python -m pip install google-genai
```

### `No module named 'openai'`

Install the OpenAI SDK only if `VISION_PROVIDER=openai`:

```bash
python -m pip install openai
```

### `No module named 'anthropic'`

Install the Anthropic SDK only if `VISION_PROVIDER=anthropic`:

```bash
python -m pip install anthropic
```

### `No vision provider configured`

This means `VISION_PROVIDER=none` and you tried to process a scanned PDF or image.

Text PDFs still work locally without any API key.

### `Invalid Gemini API Key`

Check that `.env` contains a valid `GEMINI_API_KEY` and that `VISION_PROVIDER=gemini`.

### Vendor database already seeded

This is expected on startup when the SQLite database already exists.

## Known Limitations

- Local extraction is best for text-based PDFs and depends on the document layout.
- Scanned PDFs and images require a configured vision provider.
- The local extractor returns `null` instead of guessing when a field is not visible.
- The current project keeps a lightweight SQLite backend for portability.
- Provider SDKs are optional, but the matching package must be installed when that provider is selected.

## License

Developed for educational and hackathon purposes.
