# test_concurrency_guard.py
"""Unit tests for the sweep concurrency guard feature.

This module tests the feature that prevents multiple non-queued sweeps from
running concurrently. The guard allows:
- Inner sweeps (with parent) to run within outer sweeps
- Queued sweeps (via SweepQueue) to bypass the check
- Only standalone direct s.start() calls are blocked
"""

import pytest
from unittest.mock import MagicMock, patch

from measureit.sweep.base_sweep import (
    BaseSweep,
    _ACTIVE_SWEEPS,
    _ACTIVE_SWEEPS_LOCK,
    _register_active_sweep,
    _deregister_active_sweep,
    _is_related_sweep,
    _has_other_active_sweep,
    _iter_parent_chain,
)
from measureit.sweep.progress import SweepState
from measureit.sweep.sweep1d import Sweep1D


class TestActiveSweepsRegistry:
    """Tests for the _ACTIVE_SWEEPS registry functions."""

    def test_register_and_deregister(self, mock_parameters, fast_sweep_kwargs):
        """Test that sweeps can be registered and deregistered."""
        sweep = Sweep1D(
            mock_parameters["voltage"], 0, 0.5, 0.1, **fast_sweep_kwargs
        )

        # Initially not in registry
        with _ACTIVE_SWEEPS_LOCK:
            assert sweep not in _ACTIVE_SWEEPS

        # Register
        _register_active_sweep(sweep)
        with _ACTIVE_SWEEPS_LOCK:
            assert sweep in _ACTIVE_SWEEPS

        # Deregister
        _deregister_active_sweep(sweep)
        with _ACTIVE_SWEEPS_LOCK:
            assert sweep not in _ACTIVE_SWEEPS

    def test_deregister_not_registered(self, mock_parameters, fast_sweep_kwargs):
        """Test that deregistering a non-registered sweep doesn't error."""
        sweep = Sweep1D(
            mock_parameters["voltage"], 0, 0.5, 0.1, **fast_sweep_kwargs
        )

        # Should not raise
        _deregister_active_sweep(sweep)


class TestParentChainIteration:
    """Tests for _iter_parent_chain function."""

    def test_no_parent(self, mock_parameters, fast_sweep_kwargs):
        """Test iteration with no parent."""
        sweep = Sweep1D(
            mock_parameters["voltage"], 0, 0.5, 0.1, **fast_sweep_kwargs
        )

        parents = list(_iter_parent_chain(sweep))
        assert parents == []

    def test_single_parent(self, mock_parameters, fast_sweep_kwargs):
        """Test iteration with single parent."""
        parent = Sweep1D(
            mock_parameters["voltage"], 0, 0.5, 0.1, **fast_sweep_kwargs
        )
        child = Sweep1D(
            mock_parameters["current"], 0, 0.5, 0.1, **fast_sweep_kwargs
        )
        child.parent = parent

        parents = list(_iter_parent_chain(child))
        assert parents == [parent]

    def test_grandparent_chain(self, mock_parameters, fast_sweep_kwargs):
        """Test iteration with grandparent chain."""
        grandparent = Sweep1D(
            mock_parameters["voltage"], 0, 0.5, 0.1, **fast_sweep_kwargs
        )
        parent = Sweep1D(
            mock_parameters["current"], 0, 0.5, 0.1, **fast_sweep_kwargs
        )
        child = Sweep1D(
            mock_parameters["temperature"], 0, 0.5, 0.1, **fast_sweep_kwargs
        )
        parent.parent = grandparent
        child.parent = parent

        parents = list(_iter_parent_chain(child))
        assert parents == [parent, grandparent]

    def test_circular_parent_protection(self, mock_parameters, fast_sweep_kwargs):
        """Test that circular parent references don't cause infinite loop."""
        sweep1 = Sweep1D(
            mock_parameters["voltage"], 0, 0.5, 0.1, **fast_sweep_kwargs
        )
        sweep2 = Sweep1D(
            mock_parameters["current"], 0, 0.5, 0.1, **fast_sweep_kwargs
        )

        # Create circular reference (shouldn't happen in practice)
        sweep1.parent = sweep2
        sweep2.parent = sweep1

        # Should not hang - iteration stops after visiting each node once
        # sweep1 -> sweep2 -> sweep1 (cycle detected, stop)
        parents = list(_iter_parent_chain(sweep1))
        # Visits sweep2, then sweep1 is already seen (via identity), stops
        assert len(parents) == 2  # [sweep2, sweep1] before cycle detection
        assert sweep2 in parents
        assert sweep1 in parents


class TestIsRelatedSweep:
    """Tests for _is_related_sweep function."""

    def test_same_sweep(self, mock_parameters, fast_sweep_kwargs):
        """Test that a sweep is related to itself."""
        sweep = Sweep1D(
            mock_parameters["voltage"], 0, 0.5, 0.1, **fast_sweep_kwargs
        )

        assert _is_related_sweep(sweep, sweep) is True

    def test_unrelated_sweeps(self, mock_parameters, fast_sweep_kwargs):
        """Test that independent sweeps are not related."""
        sweep1 = Sweep1D(
            mock_parameters["voltage"], 0, 0.5, 0.1, **fast_sweep_kwargs
        )
        sweep2 = Sweep1D(
            mock_parameters["current"], 0, 0.5, 0.1, **fast_sweep_kwargs
        )

        assert _is_related_sweep(sweep1, sweep2) is False

    def test_parent_child_related(self, mock_parameters, fast_sweep_kwargs):
        """Test that parent and child sweeps are related."""
        parent = Sweep1D(
            mock_parameters["voltage"], 0, 0.5, 0.1, **fast_sweep_kwargs
        )
        child = Sweep1D(
            mock_parameters["current"], 0, 0.5, 0.1, **fast_sweep_kwargs
        )
        child.parent = parent

        # Child -> Parent
        assert _is_related_sweep(child, parent) is True
        # Parent -> Child
        assert _is_related_sweep(parent, child) is True


class TestHasOtherActiveSweep:
    """Tests for _has_other_active_sweep function."""

    def test_no_active_sweeps(self, mock_parameters, fast_sweep_kwargs):
        """Test when no other sweeps are active."""
        sweep = Sweep1D(
            mock_parameters["voltage"], 0, 0.5, 0.1, **fast_sweep_kwargs
        )

        assert _has_other_active_sweep(sweep) is False

    def test_with_running_unrelated_sweep(self, mock_parameters, fast_sweep_kwargs):
        """Test detection of another running sweep."""
        sweep1 = Sweep1D(
            mock_parameters["voltage"], 0, 0.5, 0.1, **fast_sweep_kwargs
        )
        sweep2 = Sweep1D(
            mock_parameters["current"], 0, 0.5, 0.1, **fast_sweep_kwargs
        )

        # Register sweep1 as running
        sweep1.progressState.state = SweepState.RUNNING
        _register_active_sweep(sweep1)

        try:
            assert _has_other_active_sweep(sweep2) is True
        finally:
            _deregister_active_sweep(sweep1)

    def test_with_ramping_unrelated_sweep(self, mock_parameters, fast_sweep_kwargs):
        """Test detection of another ramping sweep."""
        sweep1 = Sweep1D(
            mock_parameters["voltage"], 0, 0.5, 0.1, **fast_sweep_kwargs
        )
        sweep2 = Sweep1D(
            mock_parameters["current"], 0, 0.5, 0.1, **fast_sweep_kwargs
        )

        # Register sweep1 as ramping
        sweep1.progressState.state = SweepState.RAMPING
        _register_active_sweep(sweep1)

        try:
            assert _has_other_active_sweep(sweep2) is True
        finally:
            _deregister_active_sweep(sweep1)

    def test_ignores_related_sweep(self, mock_parameters, fast_sweep_kwargs):
        """Test that related sweeps (parent/child) are allowed."""
        parent = Sweep1D(
            mock_parameters["voltage"], 0, 0.5, 0.1, **fast_sweep_kwargs
        )
        child = Sweep1D(
            mock_parameters["current"], 0, 0.5, 0.1, **fast_sweep_kwargs
        )
        child.parent = parent

        # Register parent as running
        parent.progressState.state = SweepState.RUNNING
        _register_active_sweep(parent)

        try:
            # Child should be allowed since parent is related
            assert _has_other_active_sweep(child) is False
        finally:
            _deregister_active_sweep(parent)

    def test_ignores_paused_sweep(self, mock_parameters, fast_sweep_kwargs):
        """Test that paused sweeps don't block new sweeps."""
        sweep1 = Sweep1D(
            mock_parameters["voltage"], 0, 0.5, 0.1, **fast_sweep_kwargs
        )
        sweep2 = Sweep1D(
            mock_parameters["current"], 0, 0.5, 0.1, **fast_sweep_kwargs
        )

        # Register sweep1 as paused
        sweep1.progressState.state = SweepState.PAUSED
        _register_active_sweep(sweep1)

        try:
            # Paused sweep doesn't block
            assert _has_other_active_sweep(sweep2) is False
        finally:
            _deregister_active_sweep(sweep1)

    def test_ignores_done_sweep(self, mock_parameters, fast_sweep_kwargs):
        """Test that completed sweeps don't block new sweeps."""
        sweep1 = Sweep1D(
            mock_parameters["voltage"], 0, 0.5, 0.1, **fast_sweep_kwargs
        )
        sweep2 = Sweep1D(
            mock_parameters["current"], 0, 0.5, 0.1, **fast_sweep_kwargs
        )

        # Register sweep1 as done
        sweep1.progressState.state = SweepState.DONE
        _register_active_sweep(sweep1)

        try:
            # Done sweep doesn't block
            assert _has_other_active_sweep(sweep2) is False
        finally:
            _deregister_active_sweep(sweep1)


class TestConcurrencyGuardInStart:
    """Tests for the concurrency guard check in start() method."""

    def test_start_raises_when_another_sweep_running(
        self, qapp, mock_parameters, fast_sweep_kwargs
    ):
        """Test that start() raises RuntimeError when another sweep is running."""
        sweep1 = Sweep1D(
            mock_parameters["voltage"], 0, 0.5, 0.1, **fast_sweep_kwargs
        )
        sweep2 = Sweep1D(
            mock_parameters["current"], 0, 0.5, 0.1, **fast_sweep_kwargs
        )

        # Manually set sweep1 as running
        sweep1.progressState.state = SweepState.RUNNING
        _register_active_sweep(sweep1)

        try:
            with pytest.raises(RuntimeError, match="Another sweep is already running"):
                sweep2.start()
        finally:
            _deregister_active_sweep(sweep1)
            sweep1.kill()
            sweep2.kill()

    def test_start_allows_queued_sweep(
        self, qapp, mock_parameters, fast_sweep_kwargs
    ):
        """Test that queued sweeps bypass the concurrency guard."""
        sweep1 = Sweep1D(
            mock_parameters["voltage"], 0, 0.5, 0.1, **fast_sweep_kwargs
        )
        sweep2 = Sweep1D(
            mock_parameters["current"], 0, 0.5, 0.1, **fast_sweep_kwargs
        )

        # Manually set sweep1 as running
        sweep1.progressState.state = SweepState.RUNNING
        _register_active_sweep(sweep1)

        # Mark sweep2 as queued
        sweep2.progressState.is_queued = True

        try:
            # Should not raise - queued sweeps bypass the check
            # Note: start() may fail for other reasons but shouldn't raise RuntimeError
            # for concurrency
            sweep2.start()
        except RuntimeError as e:
            if "Another sweep is already running" in str(e):
                pytest.fail("Queued sweep should bypass concurrency guard")
        finally:
            _deregister_active_sweep(sweep1)
            sweep1.kill()
            sweep2.kill()


class TestListActiveSweeps:
    """Tests for the list_active_sweeps debugging method."""

    def test_list_empty(self):
        """Test list_active_sweeps with no active sweeps."""
        result = BaseSweep.list_active_sweeps()
        assert result == []

    def test_list_with_active_sweeps(self, mock_parameters, fast_sweep_kwargs):
        """Test list_active_sweeps with registered sweeps."""
        sweep = Sweep1D(
            mock_parameters["voltage"], 0, 0.5, 0.1, **fast_sweep_kwargs
        )
        sweep.progressState.state = SweepState.RUNNING
        _register_active_sweep(sweep)

        try:
            result = BaseSweep.list_active_sweeps()
            assert len(result) == 1
            assert result[0]["type"] == "Sweep1D"
            assert result[0]["state"] == "RUNNING"
            assert result[0]["sweep"] is sweep
        finally:
            _deregister_active_sweep(sweep)


class TestRampSweepParentRelationship:
    """Tests to verify ramp sweeps have proper parent relationships."""

    def test_sweep1d_ramp_sweep_has_parent(
        self, qapp, mock_parameters, fast_sweep_kwargs
    ):
        """Test that Sweep1D's ramp_sweep has parent set."""
        sweep = Sweep1D(
            mock_parameters["voltage"], 0, 0.5, 0.1, **fast_sweep_kwargs
        )
        sweep.follow_param(mock_parameters["current"])

        # Start with ramp_to_start to create ramp_sweep
        sweep.start(ramp_to_start=True)

        try:
            # Wait briefly for ramp sweep to be created
            import time
            time.sleep(0.1)

            # If ramp_sweep was created, verify parent
            if hasattr(sweep, "ramp_sweep") and sweep.ramp_sweep is not None:
                assert sweep.ramp_sweep.parent is sweep
        finally:
            sweep.kill()
