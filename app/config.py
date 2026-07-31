from dotenv import load_dotenv
import os

load_dotenv()

VISION_PROVIDER = os.getenv("VISION_PROVIDER", "none").strip().lower()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash")
OPENAI_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", "gpt-4.1-mini")
ANTHROPIC_MODEL_NAME = os.getenv("ANTHROPIC_MODEL_NAME", "claude-3-5-sonnet-latest")

# Backward compatibility for any existing imports.
MODEL_NAME = GEMINI_MODEL_NAME
