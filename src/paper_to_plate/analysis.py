"""Independent Bradford ratio calculation, not an AI-generated success score."""
import csv
import io
import math
from statistics import mean, stdev


def analyze_bradford(text: str) -> dict:
    data = list(csv.DictReader(io.StringIO(text)))
    if not data or len(data) > 384:
        raise ValueError("Provide a CSV with 1–384 well records.")
    required = {"well", "role", "a590", "a450"}
    if not required.issubset(data[0]):
        raise ValueError("CSV requires well, role, a590 and a450 columns.")
    if len({r["well"].strip() for r in data}) != len(data):
        raise ValueError("Each well must appear once.")

    def number(row, key, positive=False):
        try:
            value = float(row[key])
        except (KeyError, ValueError, TypeError) as exc:
            raise ValueError(f"{row.get('well', 'Well')}: {key} must be numeric.") from exc
        if not math.isfinite(value) or (positive and value <= 0):
            raise ValueError(f"{row['well']}: invalid {key}.")
        return value

    for row in data:
        row["role"] = row["role"].strip().lower()
        if row["role"] not in ("blank", "standard", "sample"):
            raise ValueError("Roles must be blank, standard or sample.")
        row["a590"] = number(row, "a590")
        row["a450"] = number(row, "a450")
    blanks = [r for r in data if r["role"] == "blank"]
    if not blanks:
        raise ValueError("At least one water-only blank is required.")
    b590, b450 = mean(r["a590"] for r in blanks), mean(r["a450"] for r in blanks)
    for row in data:
        if row["role"] == "blank":
            row["ratio"] = None
            continue
        denominator = row["a450"] - b450
        if denominator <= 1e-8:
            raise ValueError(f"{row['well']}: blank-corrected A450 must be positive and nonzero.")
        row["ratio"] = (row["a590"] - b590) / denominator
        if row["role"] == "standard":
            row["protein_ug"] = number(row, "protein_ug")
            if row["protein_ug"] < 0:
                raise ValueError("Standard protein mass cannot be negative.")
    standards = [r for r in data if r["role"] == "standard"]
    if len({r["protein_ug"] for r in standards}) < 3 or not any(r["protein_ug"] == 0 for r in standards):
        raise ValueError("Use at least three distinct standard masses, including a zero-protein dye standard.")
    xs, ys = [r["protein_ug"] for r in standards], [r["ratio"] for r in standards]
    mx, my = mean(xs), mean(ys)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    if slope <= 0:
        raise ValueError("The calibration slope must be positive; inspect the assay and raw data.")
    intercept = my - slope * mx
    residual = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys))
    total = sum((y - my) ** 2 for y in ys)
    samples = []
    for row in data:
        if row["role"] != "sample":
            continue
        dilution = number(row, "dilution_factor", positive=True)
        sample_volume = number(row, "sample_volume_ul", positive=True)
        mass = (row["ratio"] - intercept) / slope
        concentration = mass / (sample_volume / 1000) * dilution
        record = {"well": row["well"], "sample_id": row.get("sample_id") or row["well"], "protein_ug": mass, "original_ug_ml": concentration, "within_calibration": min(xs) <= mass <= max(xs), "dilution_factor": dilution}
        if row.get("expected_ug_ml", "").strip():
            expected = number(row, "expected_ug_ml", positive=True)
            record["recovery_percent"] = 100 * concentration / expected
        samples.append(record)
    grouped = []
    for key in dict.fromkeys(r["sample_id"] for r in samples):
        group = [r for r in samples if r["sample_id"] == key]
        values = [r["original_ug_ml"] for r in group]
        average = mean(values)
        grouped.append({"sample_id": key, "n": len(values), "mean_original_ug_ml": average, "cv_percent": 100 * stdev(values) / abs(average) if len(values) > 1 and average else None, "all_within_calibration": all(r["within_calibration"] for r in group)})
    return {"method": "Bradford A590/A450 ratio", "blank_a590": b590, "blank_a450": b450, "slope": slope, "intercept": intercept, "r_squared": 1 - residual / total if total else None, "standards": standards, "samples": samples, "groups": grouped, "acceptance": "No universal pass threshold applied. Compare with independently chosen assay criteria.", "source": "Operator-imported measurements"}
