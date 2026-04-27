import math

class FeatureExtractor:
    """Extracts temporal features from a window of raw metrics."""
    
    @staticmethod
    def extract(samples, ear_threshold, mar_threshold, pitch_delta_threshold, target_fps=10.0):
        if not samples:
            return None
        
        total = len(samples)
        present = [s for s in samples if s.get("face_present") and s.get("usable", True)]
        
        no_face_ratio = (total - len(present)) / float(total) if total > 0 else 1.0
        
        if not present:
            return {
                "no_face_ratio": float(no_face_ratio),
                "face_confidence_mean": 0.0,
                "ear_mean": 0.0, "ear_min": 0.0, "ear_std": 0.0, "low_ear_ratio": 0.0,
                "mar_mean": 0.0, "mar_max": 0.0, "high_mar_ratio": 0.0,
                "pitch_mean": 0.0, "pitch_min": 0.0,
                "head_down_duration": 0.0,
                "perclos": 0.0,
            }
        
        count = len(present)
        ear = [s["ear"] for s in present]
        mar = [s["mar"] for s in present]
        pitch = [s["pitch"] for s in present]
        
        ear_mean = sum(ear) / count
        ear_min = min(ear)
        ear_std = math.sqrt(sum((x - ear_mean) ** 2 for x in ear) / count) if count > 0 else 0.0
        low_ear_ratio = sum(1 for x in ear if x < ear_threshold) / count
        
        mar_mean = sum(mar) / count
        mar_max = max(mar)
        high_mar_ratio = sum(1 for x in mar if x > mar_threshold) / count
        
        pitch_mean = sum(pitch) / count
        pitch_min = min(pitch)
        
        frames_down = sum(1 for x in pitch if x <= pitch_delta_threshold)
        head_down_duration = frames_down / float(target_fps) if target_fps > 0 else 0.0
        
        perclos = low_ear_ratio
        
        face_confidence_mean = sum(s.get("face_confidence", 1.0) for s in present) / count
        
        return {
            "ear_mean": float(ear_mean),
            "ear_min": float(ear_min),
            "ear_std": float(ear_std),
            "low_ear_ratio": float(low_ear_ratio),
            "mar_mean": float(mar_mean),
            "mar_max": float(mar_max),
            "high_mar_ratio": float(high_mar_ratio),
            "pitch_mean": float(pitch_mean),
            "pitch_min": float(pitch_min),
            "head_down_duration": float(head_down_duration),
            "perclos": float(perclos),
            "no_face_ratio": float(no_face_ratio),
            "face_confidence_mean": float(face_confidence_mean)
        }
