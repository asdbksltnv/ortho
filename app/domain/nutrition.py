from dataclasses import dataclass


@dataclass(frozen=True)
class NutritionResult:
    bmi_low: bool | None  # None when weight or height is missing
    weight_loss: bool | None
    reduced_intake: bool | None
    stress_factor: bool | None
    total: int  # configured rule: count of «да» answers
    complete: bool


def compute_nutrition(
    *,
    bmi_value: float | None,
    bmi_threshold: float,
    weight_loss: bool | None,
    reduced_intake: bool | None,
    stress_factor: bool | None,
) -> NutritionResult:
    bmi_low = None if bmi_value is None else bmi_value < bmi_threshold
    answers = [bmi_low, weight_loss, reduced_intake, stress_factor]
    return NutritionResult(
        bmi_low=bmi_low,
        weight_loss=weight_loss,
        reduced_intake=reduced_intake,
        stress_factor=stress_factor,
        total=sum(1 for a in answers if a is True),
        complete=all(a is not None for a in answers),
    )
