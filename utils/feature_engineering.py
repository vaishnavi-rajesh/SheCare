def calculate_bmi(height_cm, weight_kg):
    height_m = height_cm / 100
    bmi = weight_kg / (height_m ** 2)
    return round(bmi, 2)


def calculate_cycle_variation(cycles):
    return max(cycles) - min(cycles)


def convert_acne_severity(severity):
    mapping = {
        "none": 0,
        "mild": 1,
        "moderate": 2,
        "severe": 3
    }
    return mapping.get(severity.lower(), 0)
