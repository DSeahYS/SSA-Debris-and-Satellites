import torch
import numpy as np

from data.ingestion import load_sample_tle, parse_tle
from data.preprocessing import extract_features
from models.baseline_sgp4 import SGP4Baseline
from models.pinn_predictor import initialize_model

def evaluate_baseline(satellite, start_jd=None, start_fr=None, days_to_predict=7, steps_per_day=24):
    """
    Evaluates the SGP4 baseline on the mocked data.
    """
    baseline = SGP4Baseline(satellite)
    if start_jd is None:
        start_jd = satellite.jdsatepoch
        start_fr = satellite.jdsatepochF
        
    predictions = baseline.predict_window(start_jd, start_fr, days=days_to_predict, steps_per_day=steps_per_day)
    print(f"[Baseline SGP4] Predicted {len(predictions)} state vectors over {days_to_predict} days.")
    return predictions

def evaluate_pinn(satellite, days_to_predict=7, steps_per_day=24):
    """
    Evaluates the PINN mock.
    """
    model = initialize_model()
    model.eval()
    
    features = extract_features(satellite)
    curr_features = torch.tensor(features, dtype=torch.float32).unsqueeze(0)
    
    predictions = []
    
    with torch.no_grad():
        for step in range(days_to_predict * steps_per_day): 
            t_delta = torch.tensor([[step * (24/steps_per_day) * 3600.0]], dtype=torch.float32)
            combined_input = torch.cat([curr_features, t_delta], dim=1)
            pred_state = model.network(combined_input)
            predictions.append(pred_state.numpy())
            
    return predictions

def run_mvp_evaluation():
    print("Initializing SSA Startup Data Refinery MVP...")
    
    # 1. Load mock historical TLE
    tle = load_sample_tle()
    satellite = parse_tle(tle)
    
    # Define evaluation window (simulate hiding the last week)
    days_to_predict = 7
    steps_per_day = 24 # Hourly predictions
    jd_start = satellite.jdsatepoch
    fr_start = satellite.jdsatepochF
    
    # 2. Evaluate SGP4 Baseline
    print("--- Evaluating SGP4 Baseline ---")
    predictions_sgp4 = evaluate_baseline(satellite, jd_start, fr_start, days_to_predict, steps_per_day)
    print(f"[Baseline SGP4] Predicted {len(predictions_sgp4)} state vectors over {days_to_predict} days.")
    
    # 3. Evaluate Physics-Informed Neural Network (Mock)
    print("--- Evaluating Physics-Informed Neural Network (PINN) ---")
    predictions_pinn = evaluate_pinn(satellite, days_to_predict, steps_per_day)
    print(f"[PINN Predictor] Performed {len(predictions_pinn)} mock predictions over {days_to_predict} days.")
    
    # 4. In the future, compare these predictions against the actual historical labels 
    # to prove the AI is better than SGP4.
    print("Evaluation Complete. The PINN prototype is scaffolded and ready for real historical Space-Track training data.")

if __name__ == "__main__":
    run_mvp_evaluation()
