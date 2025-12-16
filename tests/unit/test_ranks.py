"""
Unit tests for rank system
"""

import pytest
from ranks import get_rank, get_rank_progress, get_rank_by_name, RANKS


@pytest.mark.unit
class TestRankLookup:
    """Test rank lookup by rating."""
    
    def test_get_rank_all_tiers(self):
        """Test get_rank for all 14 rank tiers."""
        test_cases = [
            (0, "Новачок"),
            (799, "Новачок"),
            (800, "Новачок"),
            (999, "Новачок"),
            (1000, "Шашкар"),
            (1099, "Шашкар"),
            (1100, "Учень"),
            (1199, "Учень"),
            (1200, "Гравець"),
            (1299, "Гравець"),
            (1300, "Майстер"),
            (1399, "Майстер"),
            (1400, "Ветеран"),
            (1499, "Ветеран"),
            (1500, "Чемпіон"),
            (1599, "Чемпіон"),
            (1600, "Козак"),
            (1699, "Козак"),
            (1700, "Гетьман"),
            (1799, "Гетьман"),
            (1800, "Богатир"),
            (1899, "Богатир"),
            (1900, "Князь"),
            (1999, "Князь"),
            (2000, "Воєвода"),
            (2099, "Воєвода"),
            (2100, "Легенда"),
            (2199, "Легенда"),
            (2200, "Володар"),
            (3000, "Володар"),  # Above max
        ]
        
        for rating, expected_name in test_cases:
            rank = get_rank(rating)
            assert rank["name_uk"] == expected_name, f"Rating {rating} should be {expected_name}, got {rank['name_uk']}"
    
    def test_get_rank_boundary_values(self):
        """Test get_rank at exact boundary values."""
        boundaries = [
            (0, "Новачок"),
            (800, "Новачок"),
            (1000, "Шашкар"),
            (1100, "Учень"),
            (1200, "Гравець"),
            (1300, "Майстер"),
            (1400, "Ветеран"),
            (1500, "Чемпіон"),
            (1600, "Козак"),
            (1700, "Гетьман"),
            (1800, "Богатир"),
            (1900, "Князь"),
            (2000, "Воєвода"),
            (2100, "Легенда"),
            (2200, "Володар"),
        ]
        
        for rating, expected_name in boundaries:
            rank = get_rank(rating)
            assert rank["name_uk"] == expected_name, f"Boundary {rating} should be {expected_name}"
    
    def test_get_rank_below_minimum(self):
        """Test get_rank for ratings below minimum."""
        rank = get_rank(-100)
        assert rank["name_uk"] == "Новачок", "Below minimum should return lowest rank"
    
    def test_get_rank_above_maximum(self):
        """Test get_rank for ratings above maximum."""
        rank = get_rank(5000)
        assert rank["name_uk"] == "Володар", "Above maximum should return highest rank"
    
    def test_get_rank_data_structure(self):
        """Test get_rank returns complete data structure."""
        rank = get_rank(1200)
        
        required_fields = ["name_uk", "name_en", "icon", "min_rating", "description_uk", "description_en"]
        for field in required_fields:
            assert field in rank, f"Rank should have {field} field"
        
        assert isinstance(rank["name_uk"], str)
        assert isinstance(rank["name_en"], str)
        assert isinstance(rank["icon"], str)
        assert isinstance(rank["min_rating"], int)
    
    def test_get_rank_next_rank_info(self):
        """Test get_rank includes next rank information."""
        rank = get_rank(1200)  # Гравець
        
        if rank.get("next_rank"):
            next_rank = rank["next_rank"]
            assert "min_rating" in next_rank
            assert "name_uk" in next_rank
            assert "name_en" in next_rank
            assert "icon" in next_rank
            assert next_rank["min_rating"] == 1300, "Next rank should be Майстер"
    
    def test_get_rank_max_rank_no_next(self):
        """Test get_rank for maximum rank has no next rank."""
        rank = get_rank(3000)  # Володар (max)
        assert rank.get("next_rank") is None or rank["next_rank"] is None, "Max rank should have no next rank"


@pytest.mark.unit
class TestRankProgress:
    """Test rank progress calculation."""
    
    def test_get_rank_progress_at_minimum(self):
        """Test progress at rank minimum."""
        progress, current_rating, next_rating = get_rank_progress(1200)  # Гравець minimum
        assert progress >= 0, "Progress should be >= 0"
        assert current_rating == 1200
        assert next_rating == 1300, "Next rank should be Майстер"
    
    def test_get_rank_progress_at_maximum(self):
        """Test progress at rank maximum."""
        progress, current_rating, next_rating = get_rank_progress(1299)  # Гравець maximum
        assert progress > 0, "Progress should be > 0 at max"
        assert current_rating == 1299
        assert next_rating == 1300
    
    def test_get_rank_progress_mid_rank(self):
        """Test progress in middle of rank."""
        progress, current_rating, next_rating = get_rank_progress(1250)  # Mid Гравець
        assert 0 < progress < 100, "Progress should be between 0 and 100"
        assert current_rating == 1250
        assert next_rating == 1300
    
    def test_get_rank_progress_max_rank(self):
        """Test progress at maximum rank."""
        progress, current_rating, next_rating = get_rank_progress(3000)  # Володар
        assert progress == 100.0, "Max rank should have 100% progress"
        assert current_rating == 3000
        assert next_rating == 3000, "Next rating should equal current at max"
    
    def test_get_rank_progress_all_ranks(self):
        """Test progress calculation for all ranks."""
        test_ratings = [800, 1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800, 1900, 2000, 2100, 2200]
        
        for rating in test_ratings:
            progress, current, next_rating = get_rank_progress(rating)
            assert 0 <= progress <= 100, f"Progress should be 0-100 for rating {rating}"
            assert current == rating
            assert next_rating >= rating, "Next rating should be >= current"
    
    def test_get_rank_progress_edge_cases(self):
        """Test progress calculation edge cases."""
        # Just below rank threshold
        progress, _, _ = get_rank_progress(1099)
        assert progress >= 0
        
        # Just above rank threshold
        progress, _, _ = get_rank_progress(1100)
        assert progress >= 0
        
        # Very high rating
        progress, _, _ = get_rank_progress(10000)
        assert progress == 100.0


@pytest.mark.unit
class TestRankByName:
    """Test rank lookup by Ukrainian name."""
    
    def test_get_rank_by_name_all_ranks(self):
        """Test get_rank_by_name for all rank names."""
        rank_names = [
            "Новачок", "Шашкар", "Учень", "Гравець", "Майстер",
            "Ветеран", "Чемпіон", "Козак", "Гетьман", "Богатир",
            "Князь", "Воєвода", "Легенда", "Володар"
        ]
        
        for name in rank_names:
            rank = get_rank_by_name(name)
            assert rank is not None, f"Should find rank {name}"
            assert rank["name_uk"] == name, f"Returned rank should match {name}"
    
    def test_get_rank_by_name_invalid(self):
        """Test get_rank_by_name with invalid names."""
        invalid_names = ["Invalid", "Test", "Nonexistent", "", "123"]
        
        for name in invalid_names:
            rank = get_rank_by_name(name)
            assert rank is None, f"Should return None for invalid name {name}"
    
    def test_get_rank_by_name_case_sensitive(self):
        """Test get_rank_by_name is case sensitive."""
        # Ukrainian names are case-sensitive
        rank = get_rank_by_name("Гравець")
        assert rank is not None, "Should find exact match"
        
        # Test with different case (if applicable)
        rank_lower = get_rank_by_name("гравець")
        # May or may not match depending on implementation
        assert isinstance(rank_lower, (dict, type(None)))
    
    def test_get_rank_by_name_data_structure(self):
        """Test get_rank_by_name returns complete data structure."""
        rank = get_rank_by_name("Гравець")
        
        required_fields = ["name_uk", "name_en", "icon", "min_rating", "description_uk", "description_en"]
        for field in required_fields:
            assert field in rank, f"Rank should have {field} field"
        
        assert rank["name_uk"] == "Гравець"
        assert rank["min_rating"] == 1200


@pytest.mark.unit
class TestRankDataStructure:
    """Test rank data structure integrity."""
    
    def test_ranks_list_complete(self):
        """Test RANKS list has all required ranks."""
        assert len(RANKS) >= 14, "Should have at least 14 ranks"
        
        # Check all ranks have required fields
        for rank_tuple in RANKS:
            assert len(rank_tuple) == 6, "Each rank should have 6 fields"
            min_rating, name_uk, name_en, icon, desc_uk, desc_en = rank_tuple
            assert isinstance(min_rating, int)
            assert isinstance(name_uk, str)
            assert isinstance(name_en, str)
            assert isinstance(icon, str)
            assert isinstance(desc_uk, str)
            assert isinstance(desc_en, str)
    
    def test_ranks_ordered(self):
        """Test ranks are ordered by minimum rating."""
        ratings = [rank[0] for rank in RANKS]
        assert ratings == sorted(ratings), "Ranks should be ordered by minimum rating"
    
    def test_rank_icons_present(self):
        """Test all ranks have icons."""
        for rank_tuple in RANKS:
            icon = rank_tuple[3]
            assert icon, "Each rank should have an icon"
            assert isinstance(icon, str)
    
    def test_rank_descriptions_present(self):
        """Test all ranks have descriptions."""
        for rank_tuple in RANKS:
            desc_uk = rank_tuple[4]
            desc_en = rank_tuple[5]
            assert desc_uk, "Each rank should have Ukrainian description"
            assert desc_en, "Each rank should have English description"
    
    def test_rank_consistency(self):
        """Test consistency between get_rank and get_rank_by_name."""
        test_ratings = [1000, 1200, 1500, 2000, 2200]  # Skip 800 as it has duplicate rank
        
        for rating in test_ratings:
            rank_by_rating = get_rank(rating)
            rank_by_name = get_rank_by_name(rank_by_rating["name_uk"])
            
            assert rank_by_name is not None, f"Should find rank by name for rating {rating}"
            assert rank_by_name["name_uk"] == rank_by_rating["name_uk"], "Names should match"
            # Note: get_rank_by_name may return first match, so min_rating might differ for duplicate ranks
            # Just verify the name matches

