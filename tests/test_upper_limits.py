"""Tests for Upper Tolerable Intake (UL) data structures and loading."""

import pytest
import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from src.data_layer.models import UpperLimits, MicronutrientProfile, UserProfile
from src.data_layer.upper_limits import (
    UpperLimitsLoader, 
    resolve_upper_limits,
    validate_daily_upper_limits,
    ULViolation
)


class TestUpperLimitsModel:
    """Tests for UpperLimits data model."""

    def test_upper_limits_all_none_by_default(self):
        """Test that UpperLimits() has all fields as None by default."""
        ul = UpperLimits()
        
        # All fields should be None (no UL established)
        assert ul.vitamin_a_ug is None
        assert ul.vitamin_c_mg is None
        assert ul.vitamin_d_iu is None
        assert ul.vitamin_e_mg is None
        assert ul.vitamin_k_ug is None
        assert ul.b1_thiamine_mg is None
        assert ul.b2_riboflavin_mg is None
        assert ul.b3_niacin_mg is None
        assert ul.b5_pantothenic_acid_mg is None
        assert ul.b6_pyridoxine_mg is None
        assert ul.b12_cobalamin_ug is None
        assert ul.folate_ug is None
        assert ul.calcium_mg is None
        assert ul.copper_mg is None
        assert ul.iron_mg is None
        assert ul.magnesium_mg is None
        assert ul.manganese_mg is None
        assert ul.phosphorus_mg is None
        assert ul.potassium_mg is None
        assert ul.selenium_ug is None
        assert ul.sodium_mg is None
        assert ul.zinc_mg is None
        assert ul.fiber_g is None
        assert ul.omega_3_g is None
        assert ul.omega_6_g is None

    def test_upper_limits_partial_specification(self):
        """Test that UpperLimits can be partially specified."""
        ul = UpperLimits(
            vitamin_a_ug=3000.0,
            iron_mg=45.0,
            zinc_mg=40.0
        )
        
        # Specified fields have values
        assert ul.vitamin_a_ug == 3000.0
        assert ul.iron_mg == 45.0
        assert ul.zinc_mg == 40.0
        
        # Unspecified fields remain None
        assert ul.vitamin_c_mg is None
        assert ul.calcium_mg is None

    def test_upper_limits_field_names_match_micronutrient_profile(self):
        """Test that UpperLimits field names exactly match MicronutrientProfile."""
        ul_fields = {f.name for f in UpperLimits.__dataclass_fields__.values()}
        micro_fields = {f.name for f in MicronutrientProfile.__dataclass_fields__.values()}
        
        # All MicronutrientProfile fields must exist in UpperLimits
        assert micro_fields == ul_fields, (
            f"Field mismatch. In MicronutrientProfile but not UpperLimits: {micro_fields - ul_fields}. "
            f"In UpperLimits but not MicronutrientProfile: {ul_fields - micro_fields}"
        )


class TestUpperLimitsLoader:
    """Tests for loading UL reference data."""

    @pytest.fixture
    def sample_ul_reference_data(self):
        """Sample UL reference data matching the schema."""
        return {
            "source": "IOM DRI",
            "note": "Values are DAILY upper limits. Units match MicronutrientProfile.",
            "demographics": {
                "adult_male": {
                    "vitamin_a_ug": 3000,
                    "vitamin_c_mg": 2000,
                    "vitamin_d_iu": 4000,
                    "vitamin_e_mg": 1000,
                    "vitamin_k_ug": None,
                    "b1_thiamine_mg": None,
                    "b2_riboflavin_mg": None,
                    "b3_niacin_mg": 35,
                    "b5_pantothenic_acid_mg": None,
                    "b6_pyridoxine_mg": 100,
                    "b12_cobalamin_ug": None,
                    "folate_ug": 1000,
                    "calcium_mg": 2500,
                    "copper_mg": 10,
                    "iron_mg": 45,
                    "magnesium_mg": 350,
                    "manganese_mg": 11,
                    "phosphorus_mg": 4000,
                    "potassium_mg": None,
                    "selenium_ug": 400,
                    "sodium_mg": None,
                    "zinc_mg": 40,
                    "fiber_g": None,
                    "omega_3_g": None,
                    "omega_6_g": None
                },
                "adult_female": {
                    "vitamin_a_ug": 3000,
                    "vitamin_c_mg": 2000,
                    "iron_mg": 45,
                    "zinc_mg": 40
                }
            }
        }

    @pytest.fixture
    def temp_ul_file(self, sample_ul_reference_data):
        """Create a temporary UL reference file."""
        with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(sample_ul_reference_data, f)
            temp_path = f.name
        yield temp_path
        Path(temp_path).unlink()

    def test_load_reference_ul_adult_male(self, temp_ul_file):
        """Test loading reference ULs for adult_male demographic."""
        loader = UpperLimitsLoader(temp_ul_file)
        ul = loader.load_for_demographic("adult_male")
        
        # Check specific values
        assert ul.vitamin_a_ug == 3000.0
        assert ul.vitamin_c_mg == 2000.0
        assert ul.vitamin_d_iu == 4000.0
        assert ul.iron_mg == 45.0
        assert ul.zinc_mg == 40.0
        assert ul.b3_niacin_mg == 35.0
        
        # Check null values are None
        assert ul.vitamin_k_ug is None
        assert ul.b1_thiamine_mg is None
        assert ul.b12_cobalamin_ug is None
        assert ul.potassium_mg is None
        assert ul.sodium_mg is None

    def test_load_reference_ul_adult_female(self, temp_ul_file):
        """Test loading reference ULs for adult_female demographic."""
        loader = UpperLimitsLoader(temp_ul_file)
        ul = loader.load_for_demographic("adult_female")
        
        # Check specified values
        assert ul.vitamin_a_ug == 3000.0
        assert ul.vitamin_c_mg == 2000.0
        assert ul.iron_mg == 45.0
        assert ul.zinc_mg == 40.0
        
        # Missing fields default to None
        assert ul.vitamin_d_iu is None
        assert ul.calcium_mg is None

    def test_load_reference_ul_unknown_demographic_raises(self, temp_ul_file):
        """Test that loading an unknown demographic raises KeyError."""
        loader = UpperLimitsLoader(temp_ul_file)
        
        with pytest.raises(KeyError, match="unknown_demographic"):
            loader.load_for_demographic("unknown_demographic")

    def test_load_reference_ul_null_fields_are_none(self, temp_ul_file):
        """Test that JSON null values become Python None."""
        loader = UpperLimitsLoader(temp_ul_file)
        ul = loader.load_for_demographic("adult_male")
        
        # Explicitly null in JSON
        assert ul.vitamin_k_ug is None
        assert ul.b1_thiamine_mg is None
        assert ul.b2_riboflavin_mg is None
        assert ul.b5_pantothenic_acid_mg is None
        assert ul.b12_cobalamin_ug is None
        assert ul.potassium_mg is None
        assert ul.sodium_mg is None
        assert ul.fiber_g is None
        assert ul.omega_3_g is None
        assert ul.omega_6_g is None

    def test_load_reference_missing_fields_default_to_none(self, temp_ul_file):
        """Test that missing fields in JSON default to None."""
        loader = UpperLimitsLoader(temp_ul_file)
        ul = loader.load_for_demographic("adult_female")
        
        # adult_female has fewer fields specified
        # Missing fields should be None
        assert ul.vitamin_e_mg is None  # Not in adult_female
        assert ul.b3_niacin_mg is None  # Not in adult_female
        assert ul.calcium_mg is None    # Not in adult_female

    def test_loader_returns_upper_limits_instance(self, temp_ul_file):
        """Test that loader returns an UpperLimits instance."""
        loader = UpperLimitsLoader(temp_ul_file)
        ul = loader.load_for_demographic("adult_male")
        
        assert isinstance(ul, UpperLimits)

    def test_loader_file_not_found_raises(self):
        """Test that loading from non-existent file raises FileNotFoundError."""
        loader = UpperLimitsLoader("/nonexistent/path.json")
        
        with pytest.raises(FileNotFoundError):
            loader.load_for_demographic("adult_male")


class TestUpperLimitsReferenceFile:
    """Tests for the actual reference file at data/reference/ul_by_demographic.json."""

    @pytest.fixture
    def reference_file_path(self):
        """Path to the actual reference file."""
        return "data/reference/ul_by_demographic.json"

    def test_reference_file_exists(self, reference_file_path):
        """Test that the reference file exists."""
        assert Path(reference_file_path).exists(), (
            f"Reference file not found at {reference_file_path}"
        )

    def test_reference_file_has_adult_male(self, reference_file_path):
        """Test that reference file contains adult_male demographic."""
        loader = UpperLimitsLoader(reference_file_path)
        ul = loader.load_for_demographic("adult_male")
        
        # adult_male should have vitamin_a_ug set (common UL)
        assert ul.vitamin_a_ug is not None
        assert ul.vitamin_a_ug > 0

    def test_reference_file_has_adult_female(self, reference_file_path):
        """Test that reference file contains adult_female demographic."""
        loader = UpperLimitsLoader(reference_file_path)
        ul = loader.load_for_demographic("adult_female")
        
        # adult_female should have vitamin_a_ug set
        assert ul.vitamin_a_ug is not None

    def test_reference_file_field_names_valid(self, reference_file_path):
        """Test that all field names in reference file are valid MicronutrientProfile fields."""
        with open(reference_file_path, "r") as f:
            data = json.load(f)
        
        valid_fields = {f.name for f in MicronutrientProfile.__dataclass_fields__.values()}
        
        for demographic, ul_values in data["demographics"].items():
            for field_name in ul_values.keys():
                assert field_name in valid_fields, (
                    f"Invalid field '{field_name}' in demographic '{demographic}'. "
                    f"Must match MicronutrientProfile fields."
                )


class TestResolveUpperLimits:
    """Tests for resolving ULs with user overrides."""

    @pytest.fixture
    def sample_ul_reference_data(self):
        """Sample UL reference data matching the schema."""
        return {
            "source": "IOM DRI",
            "note": "Values are DAILY upper limits.",
            "demographics": {
                "adult_male": {
                    "vitamin_a_ug": 3000,
                    "vitamin_c_mg": 2000,
                    "vitamin_d_iu": 4000,
                    "iron_mg": 45,
                    "zinc_mg": 40,
                    "vitamin_k_ug": None,
                    "potassium_mg": None
                },
                "adult_female": {
                    "vitamin_a_ug": 3000,
                    "vitamin_c_mg": 2000,
                    "iron_mg": 45
                }
            }
        }

    @pytest.fixture
    def temp_ul_file(self, sample_ul_reference_data):
        """Create a temporary UL reference file."""
        with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(sample_ul_reference_data, f)
            temp_path = f.name
        yield temp_path
        Path(temp_path).unlink()

    def test_no_overrides_uses_reference_uls(self, temp_ul_file):
        """Test that with no overrides, reference ULs are used unchanged."""
        loader = UpperLimitsLoader(temp_ul_file)
        
        # No overrides (None or empty dict)
        ul = resolve_upper_limits(
            loader=loader,
            demographic="adult_male",
            overrides=None
        )
        
        # All values from reference
        assert ul.vitamin_a_ug == 3000.0
        assert ul.vitamin_c_mg == 2000.0
        assert ul.vitamin_d_iu == 4000.0
        assert ul.iron_mg == 45.0
        assert ul.zinc_mg == 40.0
        assert ul.vitamin_k_ug is None  # No UL in reference

    def test_no_overrides_empty_dict_uses_reference_uls(self, temp_ul_file):
        """Test that with empty overrides dict, reference ULs are used."""
        loader = UpperLimitsLoader(temp_ul_file)
        
        ul = resolve_upper_limits(
            loader=loader,
            demographic="adult_male",
            overrides={}
        )
        
        # All values from reference
        assert ul.vitamin_a_ug == 3000.0
        assert ul.iron_mg == 45.0

    def test_partial_overrides_replace_specified_nutrients(self, temp_ul_file):
        """Test that overrides replace only specified nutrients."""
        loader = UpperLimitsLoader(temp_ul_file)
        
        # Override vitamin_a_ug and iron_mg only
        ul = resolve_upper_limits(
            loader=loader,
            demographic="adult_male",
            overrides={
                "vitamin_a_ug": 2000,  # Lower than reference (3000)
                "iron_mg": 30          # Lower than reference (45)
            }
        )
        
        # Overridden values
        assert ul.vitamin_a_ug == 2000.0  # Overridden
        assert ul.iron_mg == 30.0         # Overridden
        
        # Non-overridden values from reference
        assert ul.vitamin_c_mg == 2000.0  # From reference
        assert ul.vitamin_d_iu == 4000.0  # From reference
        assert ul.zinc_mg == 40.0         # From reference

    def test_override_can_increase_limit(self, temp_ul_file):
        """Test that overrides can increase limits (clinician decision)."""
        loader = UpperLimitsLoader(temp_ul_file)
        
        ul = resolve_upper_limits(
            loader=loader,
            demographic="adult_male",
            overrides={
                "vitamin_d_iu": 10000  # Higher than reference (4000)
            }
        )
        
        assert ul.vitamin_d_iu == 10000.0  # Overridden to higher value

    def test_null_override_is_ignored(self, temp_ul_file):
        """Test that null/None override values are ignored (reference used)."""
        loader = UpperLimitsLoader(temp_ul_file)
        
        ul = resolve_upper_limits(
            loader=loader,
            demographic="adult_male",
            overrides={
                "vitamin_a_ug": None  # Null override - should be ignored
            }
        )
        
        # Null override ignored, reference value used
        assert ul.vitamin_a_ug == 3000.0

    def test_invalid_field_name_ignored(self, temp_ul_file):
        """Test that invalid field names in overrides are ignored safely."""
        loader = UpperLimitsLoader(temp_ul_file)
        
        # This should not raise, just ignore the invalid field
        ul = resolve_upper_limits(
            loader=loader,
            demographic="adult_male",
            overrides={
                "vitamin_a_ug": 2000,       # Valid
                "invalid_nutrient_xyz": 100  # Invalid - ignored
            }
        )
        
        # Valid override applied
        assert ul.vitamin_a_ug == 2000.0
        # No attribute for invalid field
        assert not hasattr(ul, "invalid_nutrient_xyz")

    def test_override_float_conversion(self, temp_ul_file):
        """Test that integer overrides are converted to float."""
        loader = UpperLimitsLoader(temp_ul_file)
        
        ul = resolve_upper_limits(
            loader=loader,
            demographic="adult_male",
            overrides={"iron_mg": 35}  # int
        )
        
        assert ul.iron_mg == 35.0
        assert isinstance(ul.iron_mg, float)

    def test_resolve_returns_upper_limits_instance(self, temp_ul_file):
        """Test that resolve returns an UpperLimits instance."""
        loader = UpperLimitsLoader(temp_ul_file)
        
        ul = resolve_upper_limits(
            loader=loader,
            demographic="adult_male",
            overrides={"vitamin_a_ug": 2500}
        )
        
        assert isinstance(ul, UpperLimits)

    def test_override_on_null_reference(self, temp_ul_file):
        """Test that override can set a limit where reference has None."""
        loader = UpperLimitsLoader(temp_ul_file)
        
        # vitamin_k_ug is None in reference
        ul = resolve_upper_limits(
            loader=loader,
            demographic="adult_male",
            overrides={
                "vitamin_k_ug": 500  # Set limit where none existed
            }
        )
        
        assert ul.vitamin_k_ug == 500.0

    def test_different_demographic_with_overrides(self, temp_ul_file):
        """Test overrides work correctly with different demographics."""
        loader = UpperLimitsLoader(temp_ul_file)
        
        ul = resolve_upper_limits(
            loader=loader,
            demographic="adult_female",
            overrides={"vitamin_a_ug": 2500}
        )
        
        # Overridden
        assert ul.vitamin_a_ug == 2500.0
        # From adult_female reference
        assert ul.vitamin_c_mg == 2000.0
        assert ul.iron_mg == 45.0
        # Not in adult_female reference, defaults to None
        assert ul.vitamin_d_iu is None


class TestValidateDailyUpperLimits:
    """Tests for daily UL validation."""

    def test_day_under_all_uls_passes(self):
        """Test that a day under all ULs returns no violations."""
        # Daily intake under all limits
        daily_micros = MicronutrientProfile(
            vitamin_a_ug=2000.0,   # Under UL of 3000
            vitamin_c_mg=1500.0,  # Under UL of 2000
            iron_mg=30.0,         # Under UL of 45
            zinc_mg=25.0          # Under UL of 40
        )
        
        upper_limits = UpperLimits(
            vitamin_a_ug=3000.0,
            vitamin_c_mg=2000.0,
            iron_mg=45.0,
            zinc_mg=40.0,
            vitamin_k_ug=None  # No UL
        )
        
        violations = validate_daily_upper_limits(daily_micros, upper_limits)
        
        assert violations == []

    def test_day_exactly_at_ul_passes(self):
        """Test that intake exactly at UL is valid (not exceeded)."""
        daily_micros = MicronutrientProfile(
            vitamin_a_ug=3000.0,  # Exactly at UL
            iron_mg=45.0          # Exactly at UL
        )
        
        upper_limits = UpperLimits(
            vitamin_a_ug=3000.0,
            iron_mg=45.0
        )
        
        violations = validate_daily_upper_limits(daily_micros, upper_limits)
        
        assert violations == []

    def test_day_exceeding_single_ul_fails(self):
        """Test that exceeding a single UL returns a violation."""
        daily_micros = MicronutrientProfile(
            vitamin_a_ug=3500.0,  # EXCEEDS UL of 3000
            vitamin_c_mg=1500.0,  # Under UL
            iron_mg=30.0          # Under UL
        )
        
        upper_limits = UpperLimits(
            vitamin_a_ug=3000.0,
            vitamin_c_mg=2000.0,
            iron_mg=45.0
        )
        
        violations = validate_daily_upper_limits(daily_micros, upper_limits)
        
        assert len(violations) == 1
        assert violations[0].nutrient == "vitamin_a_ug"
        assert violations[0].actual == 3500.0
        assert violations[0].limit == 3000.0

    def test_day_exceeding_multiple_uls_fails(self):
        """Test that exceeding multiple ULs returns multiple violations."""
        daily_micros = MicronutrientProfile(
            vitamin_a_ug=4000.0,  # EXCEEDS UL of 3000
            vitamin_c_mg=2500.0,  # EXCEEDS UL of 2000
            iron_mg=50.0,         # EXCEEDS UL of 45
            zinc_mg=30.0          # Under UL
        )
        
        upper_limits = UpperLimits(
            vitamin_a_ug=3000.0,
            vitamin_c_mg=2000.0,
            iron_mg=45.0,
            zinc_mg=40.0
        )
        
        violations = validate_daily_upper_limits(daily_micros, upper_limits)
        
        assert len(violations) == 3
        nutrient_names = {v.nutrient for v in violations}
        assert nutrient_names == {"vitamin_a_ug", "vitamin_c_mg", "iron_mg"}

    def test_nutrients_with_null_ul_ignored(self):
        """Test that nutrients with null UL are not checked."""
        daily_micros = MicronutrientProfile(
            vitamin_a_ug=2000.0,
            vitamin_k_ug=10000.0,  # Very high, but UL is None
            potassium_mg=5000.0,   # Very high, but UL is None
            iron_mg=30.0
        )
        
        upper_limits = UpperLimits(
            vitamin_a_ug=3000.0,
            vitamin_k_ug=None,     # No UL - skip validation
            potassium_mg=None,    # No UL - skip validation
            iron_mg=45.0
        )
        
        violations = validate_daily_upper_limits(daily_micros, upper_limits)
        
        # No violations - null ULs are skipped
        assert violations == []

    def test_zero_intake_passes(self):
        """Test that zero intake passes validation."""
        daily_micros = MicronutrientProfile(
            vitamin_a_ug=0.0,
            iron_mg=0.0
        )
        
        upper_limits = UpperLimits(
            vitamin_a_ug=3000.0,
            iron_mg=45.0
        )
        
        violations = validate_daily_upper_limits(daily_micros, upper_limits)
        
        assert violations == []

    def test_empty_upper_limits_passes(self):
        """Test that all-null UpperLimits returns no violations."""
        daily_micros = MicronutrientProfile(
            vitamin_a_ug=10000.0,  # Very high
            iron_mg=100.0          # Very high
        )
        
        # All ULs are None
        upper_limits = UpperLimits()
        
        violations = validate_daily_upper_limits(daily_micros, upper_limits)
        
        # No violations since all ULs are None
        assert violations == []

    def test_violation_contains_correct_info(self):
        """Test that ULViolation contains correct details."""
        daily_micros = MicronutrientProfile(
            iron_mg=60.0  # Exceeds UL of 45
        )
        
        upper_limits = UpperLimits(
            iron_mg=45.0
        )
        
        violations = validate_daily_upper_limits(daily_micros, upper_limits)
        
        assert len(violations) == 1
        v = violations[0]
        assert v.nutrient == "iron_mg"
        assert v.actual == 60.0
        assert v.limit == 45.0
        assert v.excess == 15.0  # 60 - 45

    def test_ul_violation_dataclass_attributes(self):
        """Test ULViolation dataclass has expected attributes."""
        violation = ULViolation(
            nutrient="vitamin_a_ug",
            actual=3500.0,
            limit=3000.0,
            excess=500.0
        )
        
        assert violation.nutrient == "vitamin_a_ug"
        assert violation.actual == 3500.0
        assert violation.limit == 3000.0
        assert violation.excess == 500.0

    def test_validates_all_micronutrient_fields(self):
        """Test that validation checks all micronutrient fields."""
        # Create intake that exceeds limit for a less common nutrient
        daily_micros = MicronutrientProfile(
            b6_pyridoxine_mg=150.0  # Exceeds typical UL of 100
        )
        
        upper_limits = UpperLimits(
            b6_pyridoxine_mg=100.0
        )
        
        violations = validate_daily_upper_limits(daily_micros, upper_limits)
        
        assert len(violations) == 1
        assert violations[0].nutrient == "b6_pyridoxine_mg"
