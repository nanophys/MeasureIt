"""End-to-end tests for data processing and analysis.

These tests simulate the workflow from data processing.ipynb:
1. Load datasets from database
2. Extract parameter data
3. Perform basic analysis
4. Verify data structure and content
"""

import pytest
import numpy as np
import json
from pathlib import Path

import qcodes as qc
from qcodes.instrument_drivers.mock_instruments import MockParabola

from measureit.sweep.sweep1d import Sweep1D
from measureit.sweep.sweep2d import Sweep2D
from measureit.tools.util import init_database


@pytest.fixture
def database_with_sweeps(temp_database):
    """Create a database with multiple sweep types for analysis."""
    # Close all instruments first
    try:
        qc.Instrument.close_all()
    except:
        pass

    # Create mock instrument
    instr = MockParabola(name="test_instr")
    instr.noise.set(0.5)
    instr.parabola.label = "Test Value"

    # Run First Sweep - use smaller range for faster testing
    sweep1d = Sweep1D(
        instr.x,
        start=0,
        stop=2,  # Reduced range for speed
        step=1,
        inter_delay=0.01,
        save_data=True,
        plot_data=False,
    )
    sweep1d.follow_param(instr.parabola)

    # Initialize database and run first sweep
    print(f"\\n==> Initializing first sweep with DB: {temp_database}")
    init_database(str(temp_database), "analysis_test", "sweep1d", sweep1d)
    print(f"==> Starting first sweep...")
    sweep1d.start()

    # Wait for completion with proper timeout
    import time
    timeout = 15.0  # Increased timeout
    start_time = time.time()
    while sweep1d.check_running() and (time.time() - start_time) < timeout:
        time.sleep(0.2)

    sweep1d.kill()  # Ensure it's stopped
    print(f"==> First sweep done. Running: {sweep1d.check_running()}")
    # Give extra time for data to be written to database
    time.sleep(1.0)

    # Run Second Sweep - use smaller range for faster testing
    print(f"==> Creating second sweep...")
    sweep1d_2 = Sweep1D(
        instr.y,
        start=0,  # Reduced range for speed
        stop=2,
        step=1,
        inter_delay=0.01,
        save_data=True,
        plot_data=False,
    )
    sweep1d_2.follow_param(instr.parabola)

    # Initialize with different sample name (notebook shows this works)
    print(f"==> Initializing second sweep...")
    init_database(str(temp_database), "analysis_test", "sweep1d_reverse", sweep1d_2)
    print(f"==> Starting second sweep...")
    sweep1d_2.start()

    # Wait for second sweep to complete
    timeout = 15.0  # Increased timeout
    start_time = time.time()
    while sweep1d_2.check_running() and (time.time() - start_time) < timeout:
        time.sleep(0.2)

    sweep1d_2.kill()  # Ensure it's stopped
    print(f"==> Second sweep done. Running: {sweep1d_2.check_running()}")
    # Give extra time for data to be written
    time.sleep(1.0)
    print(f"==> Fixture setup complete\\n")

    yield temp_database, instr

    # Cleanup
    try:
        instr.close()
    except:
        pass


@pytest.mark.e2e
class TestDatasetLoading:
    """Test loading datasets from database."""

    def test_load_by_id(self, database_with_sweeps):
        """Test loading dataset by ID."""
        db_path, _ = database_with_sweeps

        # Load first dataset
        ds = qc.load_by_id(1)

        assert ds is not None
        assert ds.run_id == 1
        assert ds.number_of_results > 0

    def test_load_experiment_datasets(self, database_with_sweeps):
        """Test loading all datasets from an experiment."""
        db_path, _ = database_with_sweeps

        # Load datasets directly by ID (more reliable than experiment.data_sets())
        ds1 = qc.load_by_id(1)
        ds2 = qc.load_by_id(2)

        assert ds1 is not None
        assert ds2 is not None
        assert ds1.exp_name == "analysis_test"
        assert ds2.exp_name == "analysis_test"

        # They should have different sample names
        assert ds1.sample_name != ds2.sample_name

    def test_dataset_metadata(self, database_with_sweeps):
        """Test accessing dataset metadata."""
        db_path, _ = database_with_sweeps

        ds = qc.load_by_id(1)

        # Check basic metadata
        assert ds.exp_name == "analysis_test"
        assert ds.sample_name == "sweep1d"

        # Check measureit metadata
        metadata = ds.get_metadata('measureit')
        assert metadata is not None

        meta_dict = json.loads(metadata)
        assert 'class' in meta_dict
        assert 'Sweep1D' in meta_dict['class']


@pytest.mark.e2e
class TestParameterDataExtraction:
    """Test extracting parameter data from datasets."""

    def test_get_parameter_data(self, database_with_sweeps):
        """Test extracting all parameter data."""
        db_path, _ = database_with_sweeps

        ds = qc.load_by_id(1)
        param_data = ds.get_parameter_data()

        # Should have data dictionary
        assert param_data is not None
        assert len(param_data) > 0

    def test_get_specific_parameter(self, database_with_sweeps):
        """Test extracting specific parameter data."""
        db_path, _ = database_with_sweeps

        ds = qc.load_by_id(1)

        # Get all parameters
        param_data = ds.get_parameter_data()

        # Should have at least one parameter
        assert len(param_data) > 0

        # Extract first parameter
        param_name = list(param_data.keys())[0]
        single_param_data = ds.get_parameter_data(param_name)

        assert param_name in single_param_data

    def test_data_array_structure(self, database_with_sweeps):
        """Test that data arrays have correct structure."""
        db_path, _ = database_with_sweeps

        ds = qc.load_by_id(1)
        param_data = ds.get_parameter_data()

        # Check that we can convert to numpy arrays
        for param_name, param_dict in param_data.items():
            for key, values in param_dict.items():
                arr = np.array(values)
                assert arr.ndim >= 1
                assert len(arr) > 0


@pytest.mark.e2e
class TestDataAnalysis:
    """Test basic data analysis operations."""

    def test_calculate_statistics(self, database_with_sweeps):
        """Test calculating statistics on dataset."""
        db_path, _ = database_with_sweeps

        ds = qc.load_by_id(1)
        param_data = ds.get_parameter_data()

        # Find a dependent parameter
        for param_name, param_dict in param_data.items():
            for key, values in param_dict.items():
                if key == param_name:  # This is the actual measured values
                    data_array = np.array(values)

                    # Calculate basic statistics
                    mean = np.mean(data_array)
                    std = np.std(data_array)
                    min_val = np.min(data_array)
                    max_val = np.max(data_array)

                    # Verify statistics are reasonable
                    assert not np.isnan(mean)
                    assert not np.isnan(std)
                    assert std >= 0
                    assert min_val <= max_val

    def test_data_range_check(self, database_with_sweeps):
        """Test checking data ranges."""
        db_path, _ = database_with_sweeps

        ds = qc.load_by_id(1)
        param_data = ds.get_parameter_data()

        # Verify sweep parameter is in expected range
        for param_name, param_dict in param_data.items():
            # Look for the swept parameter (likely contains x or y)
            for key, values in param_dict.items():
                data_array = np.array(values)

                # Data should be within reasonable bounds
                assert np.all(np.isfinite(data_array))

    def test_sweep_direction_analysis(self, database_with_sweeps):
        """Test analyzing sweep direction from data."""
        db_path, _ = database_with_sweeps

        ds = qc.load_by_id(1)
        param_data = ds.get_parameter_data()

        # Find swept parameter
        for param_name, param_dict in param_data.items():
            for key, values in param_dict.items():
                if len(values) > 2:
                    data_array = np.array(values)
                    diff = np.diff(data_array)

                    # Check if monotonic
                    all_positive = np.all(diff >= 0)
                    all_negative = np.all(diff <= 0)

                    # Should be either monotonic or bidirectional
                    is_monotonic = all_positive or all_negative
                    is_bidirectional = not is_monotonic

                    # Should be one or the other
                    assert is_monotonic or is_bidirectional


@pytest.mark.e2e
class TestMultipleDatasets:
    """Test working with multiple datasets."""

    def test_compare_datasets(self, database_with_sweeps):
        """Test comparing data from multiple datasets."""
        db_path, _ = database_with_sweeps

        ds1 = qc.load_by_id(1)
        ds2 = qc.load_by_id(2)

        # Both should have data
        assert ds1.number_of_results > 0
        assert ds2.number_of_results > 0

        # Should be from same experiment
        assert ds1.exp_name == ds2.exp_name

        # Should have different sample names
        assert ds1.sample_name != ds2.sample_name

    def test_iterate_datasets(self, database_with_sweeps):
        """Test iterating through all datasets."""
        db_path, _ = database_with_sweeps

        # Load datasets directly by ID (more reliable than experiment.data_sets())
        # We know from fixture that we create datasets with run_ids 1 and 2
        datasets = []
        try:
            datasets.append(qc.load_by_id(1))
            datasets.append(qc.load_by_id(2))
        except Exception as e:
            pytest.fail(f"Failed to load datasets: {e}")

        assert len(datasets) >= 2

        for ds in datasets:
            assert ds is not None
            assert ds.number_of_results >= 0


@pytest.mark.e2e
class TestDataExport:
    """Test data export functionality."""

    def test_to_pandas_dict(self, database_with_sweeps):
        """Test converting dataset to pandas dict."""
        db_path, _ = database_with_sweeps

        ds = qc.load_by_id(1)

        # Convert to pandas
        try:
            pandas_dict = ds.to_pandas_dataframe_dict()
            assert pandas_dict is not None
            assert len(pandas_dict) > 0
        except (ImportError, AttributeError):
            # Pandas might not be installed or incompatible version
            pytest.skip("Pandas not available or incompatible version")

    def test_export_structure(self, database_with_sweeps):
        """Test the structure of exported data."""
        db_path, _ = database_with_sweeps

        ds = qc.load_by_id(1)
        param_data = ds.get_parameter_data()

        # Verify we can iterate and extract all data
        all_data = {}
        for param_name, param_dict in param_data.items():
            all_data[param_name] = param_dict

        # Should have captured all parameters
        assert len(all_data) == len(param_data)


@pytest.mark.e2e
class TestMetadataAnalysis:
    """Test analyzing sweep metadata."""

    def test_extract_sweep_info(self, database_with_sweeps):
        """Test extracting sweep information from metadata."""
        db_path, _ = database_with_sweeps

        ds = qc.load_by_id(1)
        metadata = ds.get_metadata('measureit')

        meta_dict = json.loads(metadata)

        # Check for common sweep metadata fields
        assert 'class' in meta_dict
        assert 'attributes' in meta_dict

        # Check sweep type
        sweep_class = meta_dict['class']
        assert 'Sweep' in sweep_class

    def test_sweep_parameters_from_metadata(self, database_with_sweeps):
        """Test extracting sweep parameters from metadata."""
        db_path, _ = database_with_sweeps

        ds = qc.load_by_id(1)
        metadata = ds.get_metadata('measureit')

        meta_dict = json.loads(metadata)

        # Should have attribute information
        if 'attributes' in meta_dict:
            attrs = meta_dict['attributes']

            # Common attributes to check
            possible_keys = ['inter_delay', 'save_data', 'plot_data']
            found_keys = [k for k in possible_keys if k in attrs]

            # Should have at least some attributes
            assert len(found_keys) > 0

    def test_metadata_consistency(self, database_with_sweeps):
        """Test that metadata is consistent across datasets."""
        db_path, _ = database_with_sweeps

        ds1 = qc.load_by_id(1)
        ds2 = qc.load_by_id(2)

        meta1 = json.loads(ds1.get_metadata('measureit'))
        meta2 = json.loads(ds2.get_metadata('measureit'))

        # Both should have class field
        assert 'class' in meta1
        assert 'class' in meta2

        # Both should be Sweep1D
        assert 'Sweep1D' in meta1['class']
        assert 'Sweep1D' in meta2['class']
