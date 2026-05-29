"""Zero-dependency Gemini VLM API Adapter for Photo-to-Pattern."""

from __future__ import annotations

import base64
import json
import logging
import os
import urllib.error
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)


class GeminiVisionError(RuntimeError):
    """Raised when required Gemini semantic vision analysis cannot complete."""


class GeminiAdapter:
    """Lightweight HTTP client for interacting with the Gemini VLM API."""

    def analyze_character(self, image_path: Path, api_key: str) -> dict:
        """Loads the image, encodes it, and sends it to the Gemini API.

        Args:
            image_path: Path to the character image file.
            api_key: The Gemini API Key.

        Returns:
            A parsed dictionary with keys 'parts' and 'details' if successful.
        """
        if not api_key:
            raise GeminiVisionError("Gemini API key is required; local heuristic fallback is disabled.")

        model = _gemini_model()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

        try:
            with open(image_path, "rb") as f:
                image_bytes = f.read()
            image_data = base64.b64encode(image_bytes).decode("utf-8")
        except Exception as e:
            raise GeminiVisionError(f"Failed to read/encode image file {image_path}: {e}") from e

        # Determine the MIME type
        ext = image_path.suffix.lower()
        mime_type = "image/jpeg"
        if ext == ".png":
            mime_type = "image/png"
        elif ext == ".webp":
            mime_type = "image/webp"

        prompt = (
            "Analyze this amigurumi/plush character image using strict semantic part extraction. "
            "Categorize every visible item into exactly one of these six categories: Primary Body, Accents, Appendages, Overlaid Garments, Facial Embroidery, Insets. "
            "Return a JSON object with: "
            "'parts' (structural components; each has 'name', 'category', 'primitive' (sphere/ovoid/cylinder/cone/capsule/flat_panel/curled_tail/inset_ear/eccentric_oval), 'relative_size' (width_ratio, height_ratio, depth_ratio), 'color_hex', 'attachment', 'confidence'), "
            "'details' (surface components; each has 'name', 'category', 'method' (crochet applique, embroidered lines, safety eyes, inset panel), 'placement', 'color_hex', 'confidence'), "
            "and 'material_profiles' (each has 'category', 'color_hex', 'role', 'confidence'). "
            "Output ONLY raw valid JSON, no markdown codeblocks."
        )

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inlineData": {
                                "mimeType": mime_type,
                                "data": image_data
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json"
            }
        }

        try:
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=req_data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            # Send the request with a timeout of 30 seconds
            with urllib.request.urlopen(req, timeout=30) as response:
                resp_bytes = response.read()
                resp_text = resp_bytes.decode("utf-8")
                resp_json = json.loads(resp_text)

                # Extract the text response
                candidates = resp_json.get("candidates", [])
                if not candidates:
                    raise GeminiVisionError(f"No candidates in Gemini response from {model}.")

                content = candidates[0].get("content", {})
                parts = content.get("parts", [])
                if not parts:
                    raise GeminiVisionError(f"No parts in Gemini content response from {model}.")

                text = parts[0].get("text", "")
                if not text:
                    raise GeminiVisionError(f"Empty text block in Gemini response parts from {model}.")

                # Strip markdown blocks just in case they were returned
                text_clean = text.strip()
                if text_clean.startswith("```"):
                    first_newline = text_clean.find("\n")
                    if first_newline != -1:
                        text_clean = text_clean[first_newline:].strip()
                    if text_clean.endswith("```"):
                        text_clean = text_clean[:-3].strip()

                parsed_result = json.loads(text_clean)
                if not isinstance(parsed_result, dict):
                    raise GeminiVisionError("Gemini parsed text is not a JSON dictionary.")
                _validate_semantic_payload(parsed_result)

                return parsed_result

        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")
            except Exception:
                body = ""
            if e.code == 404:
                raise GeminiVisionError(
                    f"Gemini model '{model}' was not found or does not support generateContent. "
                    "Set GEMINI_MODEL to a model listed by the Gemini API, such as gemini-2.0-flash."
                ) from e
            if e.code == 429:
                raise GeminiVisionError(
                    f"Gemini quota/rate limit reached for model '{model}'. "
                    "Check the API project's Gemini billing/quota or retry after quota resets."
                ) from e
            detail = f": {body}" if body else ""
            raise GeminiVisionError(f"HTTP Error in Gemini API call using model '{model}': HTTP {e.code} {e.reason}{detail}") from e
        except urllib.error.URLError as e:
            raise GeminiVisionError(f"URL Error in Gemini API call using model '{model}': {e}") from e
        except Exception as e:
            if isinstance(e, GeminiVisionError):
                raise
            raise GeminiVisionError(f"Unexpected error in Gemini API call: {e}") from e


SEMANTIC_CATEGORIES = {
    "Primary Body",
    "Accents",
    "Appendages",
    "Overlaid Garments",
    "Facial Embroidery",
    "Insets",
}


def _gemini_model() -> str:
    return os.environ.get("GEMINI_MODEL", "gemini-2.0-flash").strip() or "gemini-2.0-flash"


def _validate_semantic_payload(payload: dict) -> None:
    if not isinstance(payload.get("parts"), list) or not isinstance(payload.get("details"), list):
        raise GeminiVisionError("Gemini response must contain list fields 'parts' and 'details'.")
    if not payload["parts"]:
        raise GeminiVisionError("Gemini response must include at least one structural part.")
    material_profiles = payload.get("material_profiles")
    if material_profiles is not None and not isinstance(material_profiles, list):
        raise GeminiVisionError("Gemini response field 'material_profiles' must be a list when present.")
    has_primary_body = False
    allowed_primitives = {"sphere", "ovoid", "cylinder", "cone", "capsule", "flat_panel", "curled_tail", "inset_ear", "eccentric_oval"}
    for index, item in enumerate(payload["parts"], start=1):
        if not isinstance(item, dict):
            raise GeminiVisionError(f"parts[{index}] must be an object.")
        _require_string(item, "name", f"parts[{index}]")
        primitive = _require_string(item, "primitive", f"parts[{index}]")
        if primitive not in allowed_primitives:
            raise GeminiVisionError(f"parts[{index}] primitive {primitive!r} is not supported.")
        category = _require_category(item, f"parts[{index}]")
        has_primary_body = has_primary_body or category == "Primary Body"
        _require_relative_size(item, f"parts[{index}]")
        _require_string(item, "attachment", f"parts[{index}]")
        _require_color(item, f"parts[{index}]")
        _require_confidence(item, f"parts[{index}]")
    if not has_primary_body:
        raise GeminiVisionError("Gemini response must include at least one Primary Body part.")
    for index, item in enumerate(payload["details"], start=1):
        if not isinstance(item, dict):
            raise GeminiVisionError(f"details[{index}] must be an object.")
        _require_string(item, "name", f"details[{index}]")
        _require_string(item, "method", f"details[{index}]")
        _require_string(item, "placement", f"details[{index}]")
        _require_category(item, f"details[{index}]")
        _require_color(item, f"details[{index}]")
        _require_confidence(item, f"details[{index}]")


def _require_string(item: dict, key: str, label: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise GeminiVisionError(f"{label} must include non-empty string field {key!r}.")
    return value.strip()


def _require_category(item: dict, label: str) -> str:
    category = item.get("category")
    if category not in SEMANTIC_CATEGORIES:
        raise GeminiVisionError(f"{label} category must be one of {sorted(SEMANTIC_CATEGORIES)}.")
    return str(category)


def _require_color(item: dict, label: str) -> None:
    value = item.get("color_hex")
    if not isinstance(value, str):
        raise GeminiVisionError(f"{label} must include color_hex.")
    cleaned = value.strip().lstrip("#")
    if len(cleaned) != 6:
        raise GeminiVisionError(f"{label} color_hex must be a 6-digit hex color.")
    try:
        int(cleaned, 16)
    except ValueError as exc:
        raise GeminiVisionError(f"{label} color_hex must be valid hexadecimal.") from exc


def _require_confidence(item: dict, label: str) -> None:
    try:
        confidence = float(item.get("confidence"))
    except (TypeError, ValueError) as exc:
        raise GeminiVisionError(f"{label} must include numeric confidence.") from exc
    if not 0.0 <= confidence <= 1.0:
        raise GeminiVisionError(f"{label} confidence must be between 0 and 1.")


def _require_relative_size(item: dict, label: str) -> None:
    value = item.get("relative_size")
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        raw_values = value[:3]
    elif isinstance(value, dict):
        raw_values = (value.get("width_ratio"), value.get("height_ratio"), value.get("depth_ratio"))
    else:
        raise GeminiVisionError(f"{label} must include relative_size as a 3-item list or ratio object.")
    try:
        sizes = tuple(float(item) for item in raw_values)
    except (TypeError, ValueError) as exc:
        raise GeminiVisionError(f"{label} relative_size values must be numeric.") from exc
    if any(size <= 0 for size in sizes):
        raise GeminiVisionError(f"{label} relative_size values must be positive.")
