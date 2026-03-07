import pytest
import io
import sys
from evaluate_mvp import run_mvp_evaluation

def test_run_mvp_evaluation(monkeypatch):
    """
    Test that the main evaluation script runs successfully without crashing 
    and produces standard output for the baseline and PINN models.
    """
    # Capture standard output
    captured_output = io.StringIO()
    monkeypatch.setattr(sys, 'stdout', captured_output)
    
    # Run the evaluation
    run_mvp_evaluation()
    
    # Check output
    output = captured_output.getvalue()
    
    assert "Initializing SSA Startup Data Refinery MVP..." in output
    assert "Evaluating SGP4 Baseline" in output
    assert "Evaluating Physics-Informed Neural Network (PINN)" in output
    assert "Evaluation Complete" in output
