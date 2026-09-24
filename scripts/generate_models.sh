#!/bin/bash
# =============================================================================
# Generate Pydantic models from JSON schemas
# =============================================================================
# Usage: ./scripts/generate_models.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
SCHEMAS_DIR="$ROOT_DIR/schemas"
OUTPUT_DIR="$ROOT_DIR/services/shared/src/shared/models"

echo "=== Finance AI V3 Model Generator ==="
echo "Schemas directory: $SCHEMAS_DIR"
echo "Output directory: $OUTPUT_DIR"

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Check for required tools
if ! command -v datamodel-code-generator &> /dev/null; then
    echo "Installing datamodel-code-generator..."
    pip install datamodel-code-generator
fi

# Generate models from each schema
echo ""
echo "Generating models..."

# Market data models
datamodel-code-generator \
    --input "$SCHEMAS_DIR/01-market-data.json" \
    --input-file-type json \
    --output "$OUTPUT_DIR/market_data.py" \
    --output-model-type pydantic_v2.BaseModel \
    --target-python-version 3.12 \
    --base-class pydantic.BaseModel \
    --use-default-utilities \
    --enable-version-injection \
    --quiet

echo "  - market_data.py (Tick, Bar, IndexValue, MacroIndicator)"

# News article models
datamodel-code-generator \
    --input "$SCHEMAS_DIR/02-news-article.json" \
    --input-file-type json \
    --output "$OUTPUT_DIR/news_article.py" \
    --output-model-type pydantic_v2.BaseModel \
    --target-python-version 3.12 \
    --base-class pydantic.BaseModel \
    --use-default-utilities \
    --enable-version-injection \
    --quiet

echo "  - news_article.py (NewsArticle)"

# KAP announcement models
datamodel-code-generator \
    --input "$SCHEMAS_DIR/03-kap-announcement.json" \
    --input-file-type json \
    --output "$OUTPUT_DIR/kap_announcement.py" \
    --output-model-type pydantic_v2.BaseModel \
    --target-python-version 3.12 \
    --base-class pydantic.BaseModel \
    --use-default-utilities \
    --enable-version-injection \
    --quiet

echo "  - kap_announcement.py (KAPAnnouncement)"

# Create __init__.py
cat > "$OUTPUT_DIR/__init__.py" << 'EOF'
# AUTO-GENERATED. DO NOT EDIT.
# Modify schemas/*.json and re-run: make generate-models

from .market_data import (
    Bar,
    IndexValue,
    MacroIndicator,
    MarketData,
    Tick,
)
from .news_article import NewsArticle
from .kap_announcement import KAPAnnouncement

__all__ = [
    "Bar",
    "IndexValue",
    "MacroIndicator",
    "MarketData",
    "NewsArticle",
    "KAPAnnouncement",
    "Tick",
]
EOF

echo ""
echo "=== Model generation complete ==="
echo "Output: $OUTPUT_DIR"
