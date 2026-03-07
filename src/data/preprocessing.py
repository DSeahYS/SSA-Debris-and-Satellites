import numpy as np

def extract_features(satellite):
    """
    Extracts relevant features from a parsed Satrec object for machine learning models.
    
    Args:
        satellite (sgp4.api.Satrec): Parsed satellite record.
        
    Returns:
        np.ndarray: A vector containing extracted features like B*, mean motion, etc.
    """
    # Features from TLE parameters
    bstar = satellite.bstar
    inclo = satellite.inclo # Inclination
    nodeo = satellite.nodeo # Right ascension of ascending node
    ecco = satellite.ecco   # Eccentricity
    argpo = satellite.argpo # Argument of perigee
    mo = satellite.mo       # Mean anomaly
    no_kozai = satellite.no_kozai # Mean motion
    
    features = np.array([
        bstar, inclo, nodeo, ecco, argpo, mo, no_kozai
    ])
    return features

def prepare_training_data(historical_states, hidden_days=7):
    """
    Prepares training data by hiding the last N days.
    
    Args:
        historical_states (list or array): Series of state vectors over time.
        hidden_days (int): Number of final days to reserve as the test/target set.
        
    Returns:
        tuple: (train_data, target_data)
    """
    # Assuming historical_states is an array where each row is a time step
    # and we have 1 sample per day for simplicity in this mock.
    if len(historical_states) <= hidden_days:
        raise ValueError("Not enough historical data to hide days.")
        
    train_data = historical_states[:-hidden_days]
    target_data = historical_states[-hidden_days:]
    
    return train_data, target_data
