#!/bin/bash
# Clean script for Rakuten Monitor project
# Removes Python cache files and bytecode

echo "Cleaning Python cache files..."

# Remove __pycache__ directories
find . -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true

# Remove .pyc files
find . -name '*.pyc' -type f -delete 2>/dev/null || true

# Remove .pyo files
find . -name '*.pyo' -type f -delete 2>/dev/null || true

# Remove pytest cache
rm -rf .pytest_cache 2>/dev/null || true

# Remove coverage files
rm -rf htmlcov 2>/dev/null || true
rm -f .coverage 2>/dev/null || true

echo "Clean completed."