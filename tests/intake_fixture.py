"""One synthetic total-knee-arthroplasty patient. Every value is made up."""

import copy
from typing import Any

PSYCHO = {
    "behavior": "Адекватное",
    "appearance": "Опрятный",
    "mood": "Ровное",
    "emotions": "Адекватные",
    "understanding": "Понимает в полном объёме",
    "criticism": "Сохранена",
}


def tka_intake() -> dict[str, Any]:
    return copy.deepcopy(
        {
            "history": {
                "onset_date": "2022-05-01",
                "mechanism": "",
                "duration": "3 года",
                "prior_treatment": "НПВС, физиотерапия",
                "course": "прогрессирующее",
                "hospitalization_count": 1,
            },
            "complaints": {
                "segment": "knee",
                "pain_vas": 6,
                "limitation": True,
                "deformity": True,
                "swelling": False,
                "weight_bearing": "с дополнительной опорой",
                "other": "",
            },
            "allergy": {"has": False, "description": ""},
            "past": {
                "denies": False,
                "items": [{"text": "Гипертоническая болезнь", "year": 2015}],
                "epidemiological": [],
                "epidemiological_other": "",
            },
            "medications": [
                {
                    "name": "Препарат А",
                    "dose": "5 мг",
                    "frequency": "1 раз в сутки",
                    "is_anticoagulant": False,
                }
            ],
            "medications_none": False,
            "social": {
                "alcohol": "не употребляет",
                "alcohol_amount": "",
                "tobacco": "не курит",
                "drugs": "Отрицает",
                "economic": "удовлетворительная",
                "physical_activity": "с опорой",
            },
            "psycho": PSYCHO,
            "vitals": {
                "bp": "130/80",
                "pulse": 78,
                "rr": 16,
                "spo2": 97,
                "temp": 36.6,
                "weight": 92,
                "height": 170,
            },
            "general": {
                "severity": "удовлетворительное",
                "consciousness": "ясное",
                "position": "активное",
            },
            "systems": {
                "skin": {"normal": False, "text": "Кожные покровы чистые"},
                "cvs": {"normal": False, "text": "Тоны сердца ритмичные"},
                "resp": {"normal": False, "text": "Дыхание везикулярное"},
                "msk": {"normal": False, "text": "Деформация правого коленного сустава"},
                "gu": {"normal": False, "text": "Мочеиспускание свободное"},
                "gi": {"normal": False, "text": "Живот мягкий, безболезненный"},
                "neuro": {"normal": True, "text": ""},
            },
            "local_status": {
                "segment": "knee",
                "inspection": ["деформация"],
                "inspection_text": "",
                "palpation": "болезненность по суставной щели",
                "rom": [
                    {"movement": "сгибание", "degrees": 100},
                    {"movement": "разгибание", "degrees": -5},
                ],
                "stability": [{"test": "Лахмана", "result": "отрицательный"}],
                "neurovascular": {
                    "pulsation": "сохранена",
                    "sensation": "сохранена",
                    "motor": "сохранены",
                },
                "other": "",
            },
            "columbia": {f"q{i}": False for i in (1, 2, 7)},
            "nutrition": {"weight_loss": False, "reduced_intake": False, "stress_factor": False},
            "caprini": {"factors": ["elective_major_arthroplasty"]},
            "diagnosis": {
                "main": {"code": "TEST.1", "text": "Тестовый основной диагноз"},
                "competing": {"code": "", "text": ""},
                "complication": {"code": "", "text": ""},
                "background": {"code": "", "text": ""},
                "comorbid": [{"code": "TEST.2", "text": "Тестовая сопутствующая патология"}],
            },
            "plan": {
                "checked": [],
                "diet": "Тестовая диета",
                "special_diet": "",
                "labs": ["HBsAg (HBV)", "anti-HCV", "RW", "ВИЧ", "ОАК", "Группа крови и резус"],
                "instrumental": ["Рентгенография коленного сустава"],
                "consults": ["Анестезиолог", "Терапевт"],
                "medications": [
                    {"name": "Препарат Б", "note": "тест", "kind": "антибиотикопрофилактика"},
                    {"name": "Препарат В", "note": "", "kind": "профилактика ВТЭ"},
                ],
                "recommendations": "",
            },
            "preop": {
                "economic_assessment": "достаточная",
                "social_needs": "уход дома",
                "psychological_needs": "нет",
                "discharge_needs": ["костыли", "перевязки"],
                "vitals": {
                    "bp": "125/80",
                    "pulse": 74,
                    "rr": 16,
                    "spo2": 98,
                    "temp": 36.5,
                    "weight": 91,
                    "height": 170,
                },
                "general_condition": "",
                "local_status": "",
                "imaging": "рентгенография: сужение суставной щели",
                "failed_conservative": "без эффекта",
            },
        }
    )
