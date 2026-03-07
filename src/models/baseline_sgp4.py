import numpy as np
from sgp4.api import WGS84

class SGP4Baseline:
    """
    A baseline model using standard SGP4 propagation to predict future states.
    """
    def __init__(self, satellite):
        """
        Args:
            satellite (sgp4.api.Satrec): Parsed satellite object.
        """
        self.satellite = satellite
        
    def predict(self, jd, fr):
        """
        Predicts the state vector (position and velocity) at a given Julian Date.
        
        Args:
            jd (float): Julian Date (integer part).
            fr (float): Julian Date (fractional part).
            
        Returns:
            tuple: (error_code, position_vector, velocity_vector)
        """
        e, r, v = self.satellite.sgp4(jd, fr)
        if e != 0:
            return e, None, None
            
        return e, np.array(r), np.array(v)

    def predict_window(self, start_jd, start_fr, days, steps_per_day=24):
        """
        Predicts states over a continuous window.
        """
        predictions = []
        fractional_step = 1.0 / steps_per_day
        
        current_jd = start_jd
        current_fr = start_fr
        
        for _ in range(int(days * steps_per_day)):
            e, r, v = self.predict(current_jd, current_fr)
            if e != 0:
                break
                
            predictions.append((current_jd + current_fr, r, v))
            
            # Increment time
            current_fr += fractional_step
            if current_fr >= 1.0:
                current_jd += 1
                current_fr -= 1.0
                
        return predictions
