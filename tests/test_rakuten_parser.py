"""Unit tests for rakuten_parser.py module."""
import sys
from pathlib import Path

# Add parent directory to Python path for module imports
sys.path.append(str(Path(__file__).resolve().parents[1]))

import pytest
import os


class TestParseItemInfo:
    """Test parse_item_info function for rakuten product parsing."""
    
    def setup_method(self):
        """Setup method to reset parser state before each test."""
        from rakuten_parser import reset_known_items
        reset_known_items()
    
    def read_fixture(self, filename):
        """Helper method to read fixture files."""
        fixture_path = Path(__file__).parent / "fixtures" / filename
        with open(fixture_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def test_parse_new_product(self):
        """Test parsing new product HTML with new item_code."""
        # Arrange
        from rakuten_parser import parse_item_info
        html = self.read_fixture("new_product.html")
        
        # Act
        result = parse_item_info(html)
        
        # Assert
        assert result["item_code"] == "shouritu-100089"
        assert result["title"] == "カチカチくんEX（青） ※8月上旬発送予定"
        assert result["status"] == "NEW"
    
    def test_parse_resale_product(self):
        """Test parsing resale product HTML with existing item_code but different shipping date."""
        # Arrange
        from rakuten_parser import parse_item_info
        html = self.read_fixture("resale_product_august.html")
        
        # Act
        result = parse_item_info(html)
        
        # Assert
        assert result["item_code"] == "shouritu-100089"
        assert "8月上旬発送予定" in result["title"]
        assert result["status"] == "RESALE"
    
    def test_parse_unchanged_product(self):
        """Test parsing unchanged product HTML."""
        # Arrange
        from rakuten_parser import parse_item_info
        
        # First, register the item as "known" by parsing it once
        html_new = self.read_fixture("new_product.html")
        parse_item_info(html_new)  # This registers the item as known
        
        # Then parse the unchanged product (same shipping date)
        html_unchanged = self.read_fixture("unchanged_product.html")
        
        # Act
        result = parse_item_info(html_unchanged)
        
        # Assert
        assert result["item_code"] == "shouritu-100089"
        assert result["status"] == "UNCHANGED"
    
    def test_parse_item_info_returns_dict(self):
        """Test that parse_item_info returns a dictionary."""
        # Arrange
        from rakuten_parser import parse_item_info
        html = self.read_fixture("new_product.html")
        
        # Act
        result = parse_item_info(html)
        
        # Assert
        assert isinstance(result, dict)
        assert "item_code" in result
        assert "title" in result
        assert "status" in result
    
    def test_parse_item_info_with_shipping_date_detection(self):
        """Test that shipping date is properly detected in title."""
        # Arrange
        from rakuten_parser import parse_item_info
        html = self.read_fixture("new_product.html")
        
        # Act
        result = parse_item_info(html)
        
        # Assert
        assert "発送予定" in result["title"]
        assert "8月上旬" in result["title"]