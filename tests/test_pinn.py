import pytest
import torch
from models.pinn_predictor import PINNPredictor

def test_pinn_predictor_initialization():
    model = PINNPredictor(input_dim=6, hidden_dim=32, output_dim=6)
    assert model.network[0].in_features == 6
    assert model.network[2].in_features == 32
    assert model.network[4].out_features == 6

def test_pinn_predictor_forward():
    model = PINNPredictor()
    # Mock input: batch_size=1, state_dim=6
    mock_state = torch.randn(1, 6)
    mock_t_delta = torch.tensor([[1.0]])
    
    # Forward requires both state and t_delta
    output = model(mock_state, mock_t_delta)
    
    assert output.shape == (1, 6)

def test_pinn_predictor_physics_loss():
    model = PINNPredictor()
    # Mock data
    pred_state = torch.randn(2, 6)
    target_state = torch.randn(2, 6)
    t_delta = torch.tensor([[1.0], [2.0]])
    environment_params = torch.randn(2, 3) # Mock 3 environmental features like solar flux
    
    loss = model.physics_loss(pred_state, target_state, t_delta, environment_params)
    
    assert isinstance(loss, torch.Tensor)
    assert loss.item() > 0 # Loss should be positive
