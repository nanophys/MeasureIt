"""Unit tests for utility functions."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from measureit.tools.util import (
    ParameterException,
    safe_set,
    safe_get,
    _value_parser,
    _name_parser,
    get_measureit_home,
)


class TestParameterException:
    """Test ParameterException class."""

    def test_create_exception(self):
        """Test creating a ParameterException."""
        exc = ParameterException("Test error")

        assert exc.message == "Test error"
        assert exc.set is False

    def test_create_exception_with_set_flag(self):
        """Test creating a ParameterException with set flag."""
        exc = ParameterException("Set error", set=True)

        assert exc.message == "Set error"
        assert exc.set is True

    def test_exception_str(self):
        """Test string representation of exception."""
        exc = ParameterException("Test error")

        assert str(exc) == "Test error"


class TestSafeSet:
    """Test safe_set function."""

    def test_safe_set_success(self, mock_parameter):
        """Test safe_set with successful set."""
        param = mock_parameter("voltage", initial_value=0.0)

        result = safe_set(param, 1.0)

        assert param.get() == 1.0

    def test_safe_set_retry_on_failure(self, mock_parameter):
        """Test safe_set retries on failure."""
        param = mock_parameter("voltage", initial_value=0.0)

        # Mock set to fail first time, succeed second time
        call_count = [0]

        original_set = param.set

        def failing_set(value):
            call_count[0] += 1
            if call_count[0] == 1:
                raise ValueError("First attempt fails")
            return original_set(value)

        param.set = failing_set

        with patch("time.sleep"):  # Skip sleep during test
            result = safe_set(param, 1.0)

        assert call_count[0] == 2  # Should have tried twice

    def test_safe_set_raises_after_retries(self, mock_parameter):
        """Test safe_set raises ParameterException after retries."""
        param = mock_parameter("voltage", initial_value=0.0)

        # Mock set to always fail
        def always_fail(value):
            raise ValueError("Always fails")

        param.set = always_fail

        with patch("time.sleep"):
            with pytest.raises(ParameterException, match="Couldn't set"):
                safe_set(param, 1.0)


class TestSafeGet:
    """Test safe_get function."""

    def test_safe_get_success(self, mock_parameter):
        """Test safe_get with successful get."""
        param = mock_parameter("voltage", initial_value=2.5)

        result = safe_get(param)

        assert result == 2.5

    def test_safe_get_retry_on_failure(self, mock_parameter):
        """Test safe_get retries on failure."""
        param = mock_parameter("voltage", initial_value=1.0)

        call_count = [0]
        original_get = param.get

        def failing_get():
            call_count[0] += 1
            if call_count[0] == 1:
                raise ValueError("First attempt fails")
            return original_get()

        param.get = failing_get

        with patch("time.sleep"):
            result = safe_get(param)

        assert call_count[0] == 2
        assert result == 1.0

    def test_safe_get_raises_after_retries(self, mock_parameter):
        """Test safe_get raises ParameterException after retries."""
        param = mock_parameter("voltage")

        def always_fail():
            raise ValueError("Always fails")

        param.get = always_fail

        with patch("time.sleep"):
            with pytest.raises(ParameterException, match="Could not get"):
                safe_get(param)


class TestValueParser:
    """Test _value_parser function."""

    def test_parse_simple_number(self):
        """Test parsing a simple number."""
        result = _value_parser("5")
        assert result == 5.0

    def test_parse_decimal(self):
        """Test parsing a decimal."""
        result = _value_parser("3.14")
        assert result == 3.14

    def test_parse_negative(self):
        """Test parsing negative number."""
        result = _value_parser("-2.5")
        assert result == -2.5

    def test_parse_milli(self):
        """Test parsing with milli prefix."""
        result = _value_parser("5m")
        assert result == 5e-3

    def test_parse_micro(self):
        """Test parsing with micro prefix."""
        result = _value_parser("10u")
        assert result == pytest.approx(10e-6)

    def test_parse_nano(self):
        """Test parsing with nano prefix."""
        result = _value_parser("100n")
        assert result == pytest.approx(100e-9)

    def test_parse_kilo(self):
        """Test parsing with kilo prefix."""
        result = _value_parser("2k")
        assert result == 2e3

    def test_parse_mega(self):
        """Test parsing with mega prefix."""
        result = _value_parser("3M")
        assert result == 3e6

    def test_parse_giga(self):
        """Test parsing with giga prefix."""
        result = _value_parser("1G")
        assert result == 1e9

    def test_parse_with_space(self):
        """Test parsing with space before unit."""
        result = _value_parser("5 m")
        assert result == 5e-3

    def test_parse_leading_dot(self):
        """Test parsing number starting with dot."""
        result = _value_parser(".5")
        assert result == 0.5

    def test_parse_empty_raises(self):
        """Test that empty string raises exception."""
        with pytest.raises(ParameterException, match="No value given"):
            _value_parser("")

    def test_parse_invalid_raises(self):
        """Test that invalid input raises exception."""
        with pytest.raises(ParameterException, match="Could not parse"):
            _value_parser("abc")


class TestNameParser:
    """Test _name_parser function."""

    def test_parse_valid_name(self):
        """Test parsing a valid name."""
        result = _name_parser("MyInstrument")
        assert result == "MyInstrument"

    def test_parse_name_with_numbers(self):
        """Test parsing name with numbers."""
        result = _name_parser("SR830_1")
        assert result == "SR830_1"

    def test_parse_name_with_underscore(self):
        """Test parsing name with underscores."""
        result = _name_parser("lock_in_amplifier")
        assert result == "lock_in_amplifier"

    def test_parse_empty_name_raises(self):
        """Test that empty name raises ValueError."""
        with pytest.raises(ValueError, match="Must provide an instrument name"):
            _name_parser("")

    def test_parse_name_with_space_raises(self):
        """Test that name with space raises ValueError."""
        with pytest.raises(ValueError, match="No spaces allowed"):
            _name_parser("My Instrument")

    def test_parse_name_starting_with_number_raises(self):
        """Test that name starting with number raises ValueError."""
        with pytest.raises(ValueError, match="First character must be a letter"):
            _name_parser("1Instrument")

    def test_parse_name_strips_whitespace(self):
        """Test that parser strips leading/trailing whitespace."""
        result = _name_parser("  MyInstrument  ")
        assert result == "MyInstrument"


class TestGetMeasureitHome:
    """Test get_measureit_home function."""

    def test_get_measureit_home_returns_string(self):
        """Test that get_measureit_home returns a string."""
        result = get_measureit_home()
        assert isinstance(result, str)

    def test_get_measureit_home_returns_path(self):
        """Test that result is a valid path."""
        result = get_measureit_home()
        path = Path(result)
        # Should be a valid path (might not exist yet)
        assert isinstance(path, Path)


@pytest.mark.integration
class TestUtilIntegration:
    """Integration tests for utility functions."""

    def test_safe_operations_with_mock_param(self, mock_parameter):
        """Test safe_set and safe_get together."""
        param = mock_parameter("voltage", initial_value=0.0)

        # Set value
        safe_set(param, 5.0)

        # Get value
        result = safe_get(param)

        assert result == 5.0

    def test_value_parser_with_various_inputs(self):
        """Test value parser with multiple inputs."""
        test_cases = [
            ("1", 1.0),
            ("1.5", 1.5),
            ("100m", 0.1),
            ("10u", 10e-6),
            ("2k", 2000.0),
            ("-5", -5.0),
        ]

        for input_val, expected in test_cases:
            result = _value_parser(input_val)
            assert result == pytest.approx(expected)

    def test_name_parser_valid_names(self):
        """Test name parser with various valid names."""
        valid_names = [
            "Instrument1",
            "SR830",
            "lock_in",
            "DAQ_card_2",
            "TemperatureController",
        ]

        for name in valid_names:
            result = _name_parser(name)
            assert result == name
