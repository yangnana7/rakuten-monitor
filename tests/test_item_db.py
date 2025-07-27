"""Unit tests for item_db.py module."""
import sys
from pathlib import Path

# Add parent directory to Python path for module imports
sys.path.append(str(Path(__file__).resolve().parents[1]))

import tempfile
import os


class TestItemDatabase:
    """Test item database operations."""
    
    def setup_method(self):
        """Setup test database for each test."""
        # Create temporary database file
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
    
    def teardown_method(self):
        """Cleanup test database after each test."""
        # Close any remaining connections
        import gc
        gc.collect()
        
        # Try to remove the file, ignore if it fails
        try:
            if os.path.exists(self.db_path):
                os.unlink(self.db_path)
        except (PermissionError, OSError):
            # File is still in use, skip cleanup
            pass
    
    def test_save_item_new_product(self):
        """Test saving a new product to database."""
        # Arrange
        from item_db import ItemDB
        db = ItemDB(self.db_path)
        item_data = {
            "item_code": "shouritu-100089",
            "title": "カチカチくんEX（青） ※8月上旬発送予定",
            "status": "NEW"
        }
        
        # Act
        result = db.save_item(item_data)
        
        # Assert
        assert result is True
        assert db.item_exists("shouritu-100089") is True
    
    def test_save_item_duplicate_product(self):
        """Test saving duplicate product returns False."""
        # Arrange
        from item_db import ItemDB
        db = ItemDB(self.db_path)
        item_data = {
            "item_code": "shouritu-100089",
            "title": "カチカチくんEX（青） ※8月上旬発送予定",
            "status": "NEW"
        }
        
        # Act
        db.save_item(item_data)  # First save
        result = db.save_item(item_data)  # Duplicate save
        
        # Assert
        assert result is False
    
    def test_item_exists_true(self):
        """Test item_exists returns True for existing item."""
        # Arrange
        from item_db import ItemDB
        db = ItemDB(self.db_path)
        item_data = {
            "item_code": "shouritu-100089",
            "title": "カチカチくんEX（青） ※8月上旬発送予定",
            "status": "NEW"
        }
        db.save_item(item_data)
        
        # Act
        result = db.item_exists("shouritu-100089")
        
        # Assert
        assert result is True
    
    def test_item_exists_false(self):
        """Test item_exists returns False for non-existing item."""
        # Arrange
        from item_db import ItemDB
        db = ItemDB(self.db_path)
        
        # Act
        result = db.item_exists("non-existing-item")
        
        # Assert
        assert result is False
    
    def test_get_item_existing(self):
        """Test getting existing item from database."""
        # Arrange
        from item_db import ItemDB
        db = ItemDB(self.db_path)
        item_data = {
            "item_code": "shouritu-100089",
            "title": "カチカチくんEX（青） ※8月上旬発送予定",
            "status": "NEW"
        }
        db.save_item(item_data)
        
        # Act
        result = db.get_item("shouritu-100089")
        
        # Assert
        assert result is not None
        assert result["item_code"] == "shouritu-100089"
        assert result["title"] == "カチカチくんEX（青） ※8月上旬発送予定"
        assert result["status"] == "NEW"
    
    def test_get_item_non_existing(self):
        """Test getting non-existing item returns None."""
        # Arrange
        from item_db import ItemDB
        db = ItemDB(self.db_path)
        
        # Act
        result = db.get_item("non-existing-item")
        
        # Assert
        assert result is None
    
    def test_update_item_status(self):
        """Test updating item status."""
        # Arrange
        from item_db import ItemDB
        db = ItemDB(self.db_path)
        item_data = {
            "item_code": "shouritu-100089",
            "title": "カチカチくんEX（青） ※8月上旬発送予定",
            "status": "NEW"
        }
        db.save_item(item_data)
        
        # Act
        result = db.update_item_status("shouritu-100089", "RESALE")
        
        # Assert
        assert result is True
        updated_item = db.get_item("shouritu-100089")
        assert updated_item["status"] == "RESALE"
    
    def test_update_item(self):
        """Test updating item with data dictionary (expected interface)."""
        # Arrange
        from item_db import ItemDB
        db = ItemDB(self.db_path)
        item_data = {
            "item_code": "shouritu-100089",
            "title": "カチカチくんEX（青） ※8月上旬発送予定",
            "status": "NEW"
        }
        db.save_item(item_data)
        
        # Act
        update_data = {
            "title": "カチカチくんEX（青） ※9月上旬発送予定",
            "status": "RESALE"
        }
        result = db.update_item("shouritu-100089", update_data)
        
        # Assert
        assert result is True
        updated_item = db.get_item("shouritu-100089")
        assert updated_item["title"] == "カチカチくんEX（青） ※9月上旬発送予定"
        assert updated_item["status"] == "RESALE"
    
    def test_update_item_partial(self):
        """Test updating item with partial data."""
        # Arrange
        from item_db import ItemDB
        db = ItemDB(self.db_path)
        item_data = {
            "item_code": "shouritu-100089",
            "title": "カチカチくんEX（青） ※8月上旬発送予定",
            "status": "NEW"
        }
        db.save_item(item_data)
        
        # Act - Only update status
        update_data = {"status": "RESALE"}
        result = db.update_item("shouritu-100089", update_data)
        
        # Assert
        assert result is True
        updated_item = db.get_item("shouritu-100089")
        assert updated_item["title"] == "カチカチくんEX（青） ※8月上旬発送予定"  # Unchanged
        assert updated_item["status"] == "RESALE"  # Updated
    
    def test_update_item_empty_dict(self):
        """Test updating item with empty dictionary returns False."""
        # Arrange
        from item_db import ItemDB
        db = ItemDB(self.db_path)
        item_data = {
            "item_code": "shouritu-100089",
            "title": "カチカチくんEX（青） ※8月上旬発送予定",
            "status": "NEW"
        }
        db.save_item(item_data)
        
        # Act
        result = db.update_item("shouritu-100089", {})
        
        # Assert
        assert result is False
    
    def test_get_all_items(self):
        """Test getting all items from database."""
        # Arrange
        from item_db import ItemDB
        db = ItemDB(self.db_path)
        items = [
            {"item_code": "item-001", "title": "Product 1", "status": "NEW"},
            {"item_code": "item-002", "title": "Product 2", "status": "RESALE"}
        ]
        for item in items:
            db.save_item(item)
        
        # Act
        result = db.get_all_items()
        
        # Assert
        assert len(result) == 2
        assert any(item["item_code"] == "item-001" for item in result)
        assert any(item["item_code"] == "item-002" for item in result)
    
    def test_database_initialization(self):
        """Test database is properly initialized."""
        # Arrange & Act
        from item_db import ItemDB
        db = ItemDB(self.db_path)
        
        # Assert
        assert os.path.exists(self.db_path)
        assert db.get_all_items() == []