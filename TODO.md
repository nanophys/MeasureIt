# MeasureIt PyQtGraph Migration TODO

## Overview
This document tracks the migration from matplotlib to pyqtgraph for the MeasureIt plotter system to improve real-time plotting performance.

## Migration Phases

### Phase 1: Environment Setup
- [x] Add pyqtgraph dependency to pyproject.toml
- [x] Create backup of current plotter_thread.py (saved as plotter_thread_matplotlib.py)
- [ ] Verify conda env qcodes has required packages
- [x] Document current matplotlib API surface

### Phase 2: PyQtGraph Implementation
- [x] Replace plotter_thread.py with PyQtGraph implementation
- [x] Implement core plotting functionality using GraphicsLayoutWidget
- [x] Replace matplotlib Line2D with pyqtgraph PlotDataItems
- [x] Implement keyboard event handling for Qt
- [x] Add real-time data updates using setData()

### Phase 3: Feature Parity
- [x] Multi-plot grid layout (equivalent to matplotlib GridSpec)
- [x] Bidirectional sweep visualization (forward=blue, backward=red)
- [x] Keyboard shortcuts (ESC=stop, Enter=resume, Space=flip direction)
- [x] Auto-scaling and proper axis labeling
- [x] Break handling (NaN value insertion for sweep direction changes)
- [x] Figure management (creation, reset, clear, close handling)

### Phase 4: Integration
- [x] Replace matplotlib plotter with PyQtGraph in base_sweep.py
- [x] Ensure thread safety with PyQtGraph in QThread
- [x] Test signal/slot connections between runner and plotter threads
- [x] Migrate heatmap_thread.py to PyQtGraph ImageView
- [x] Update Sweep2D data flow to use get_plot_data instead of axes
- [ ] Verify compatibility with all sweep types (0D, 1D, 2D, SimulSweep)

### Phase 5: Testing & Validation
- [ ] Unit tests for plotter functionality
- [ ] Integration tests with MockParabola instrument
- [ ] Performance benchmarking vs matplotlib
- [ ] Memory leak testing for long-running sweeps
- [ ] Cross-platform testing (Windows/Linux/macOS)

## Test Plan

### Test Environment
- **Environment**: conda environment `qcodes`
- **Test Instrument**: MockParabola from qcodes.instrument_drivers.mock_instruments
- **Hardware**: Development machine with PyQt5 support

### Test Categories

#### 1. Basic Functionality Tests
**Test 1.1: Plot Creation**
```python
# Test that plots are created correctly for multiple parameters
sweep = Sweep1D(instr.x, 0, 10, 0.1)
sweep.follow_param(instr.parabola, instr.noise)
# Expected: 3 subplots (set_param vs time, parabola vs x, noise vs x)
```

**Test 1.2: Real-time Updates**
```python
# Test that plots update in real-time during sweep
# Expected: Smooth plotting without lag, data appears immediately
```

**Test 1.3: Keyboard Controls**
```python
# Test keyboard shortcuts work correctly
# ESC: Stop sweep
# Enter: Resume sweep
# Space: Flip direction (bidirectional sweeps)
```

#### 2. Sweep Type Tests
**Test 2.1: Sweep0D (Time-based)**
```python
sweep = Sweep0D(inter_delay=0.05, max_time=10)
sweep.follow_param(instr.parabola, instr.noise)
# Expected: Parameters plotted vs time, continuous updates
```

**Test 2.2: Sweep1D (Parameter sweep)**
```python
sweep = Sweep1D(instr.x, 0, 5, 0.1, bidirectional=True)
sweep.follow_param(instr.parabola)
# Expected: Forward sweep (blue), backward sweep (red)
```

**Test 2.3: Sweep2D (2D mapping)**
```python
sweep = Sweep2D([instr.x, 0, 5, 0.1], [instr.y, 0, 5, 0.1])
sweep.follow_param(instr.parabola)
# Expected: Line plots for each inner sweep + heatmap
```

#### 3. Performance Tests
**Test 3.1: Update Rate**
- Target: >100 FPS for 1000 data points
- Measurement: Time between data updates
- Comparison: PyQtGraph vs matplotlib performance

**Test 3.2: Large Dataset Handling**
- Test: 30,000+ data points
- Expected: Smooth operation, no UI freezing
- Memory usage should remain stable

**Test 3.3: Long-running Sweeps**
- Test: 30+ minute continuous operation
- Monitor: Memory leaks, performance degradation
- Expected: Stable performance throughout

#### 4. Edge Case Tests
**Test 4.1: NaN Handling**
```python
# Test break insertion (direction changes)
# Expected: Gaps in plotted lines, no crashes
```

**Test 4.2: Thread Safety**
- High-frequency data updates (>50Hz)
- Multiple simultaneous parameter updates
- Expected: No race conditions, clean UI updates

**Test 4.3: Error Recovery**
- Invalid data values
- Instrument disconnection during sweep
- Expected: Graceful error handling, no crashes

#### 5. Compatibility Tests
**Test 5.1: All Sweep Classes**
- [ ] Sweep0D compatibility
- [ ] Sweep1D compatibility
- [ ] Sweep2D compatibility
- [ ] SimulSweep compatibility
- [ ] SweepQueue compatibility

**Test 5.2: GUI Integration**
- Test with MeasureIt GUI (GUI_Measureit.py)
- Expected: Seamless integration, no API breaks

### Success Criteria
1. **Performance**: 10x improvement in plot update rate
2. **Stability**: No memory leaks in 1+ hour tests
3. **Feature Parity**: All matplotlib features working in PyQtGraph
4. **Compatibility**: All existing sweep types function correctly
5. **User Experience**: Responsive UI, smooth real-time plotting

### Rollback Plan
- Keep matplotlib plotter as fallback option
- Feature flag allows instant switching back
- No breaking changes to existing API
- Document any limitations of PyQtGraph implementation

### Notes
- Test on conda env `qcodes` as specified
- Use examples/content/quick start.ipynb for integration testing
- Performance benchmarks should be reproducible
- Document any PyQtGraph-specific configuration needed

## Implementation Notes

### Key PyQtGraph Concepts
- **GraphicsLayoutWidget**: Replaces matplotlib Figure
- **PlotWidget**: Individual plot areas
- **PlotDataItem**: Replaces matplotlib Line2D
- **setData()**: Fast real-time data updates
- **KeyPressEvent**: Qt-native keyboard handling

### Performance Optimizations
- Use PlotDataItem.setData() instead of clearing/redrawing
- Enable OpenGL acceleration if available
- Optimize data structures for large datasets
- Consider downsampling for very large datasets

### Migration Risks
- Qt event handling differences from matplotlib
- Different coordinate systems or scaling behavior
- PyQtGraph widget lifecycle management
- Thread safety considerations with Qt graphics