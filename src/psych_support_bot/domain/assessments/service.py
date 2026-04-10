from psych_support_bot.domain.assessments.schemas import AssessmentScore, AssessmentType


def severity_for_score(assessment_type: AssessmentType, score: int) -> str:
    bands = {
        "phq9": [
            (4, "minimal"),
            (9, "mild"),
            (14, "moderate"),
            (19, "moderately_severe"),
        ],
        "gad7": [(4, "minimal"), (9, "mild"), (14, "moderate")],
        "isi": [(7, "none"), (14, "subthreshold"), (21, "moderate")],
    }
    for threshold, label in bands[assessment_type]:
        if score <= threshold:
            return label
    return "severe"


def build_assessment_score(
    assessment_type: AssessmentType, score: int
) -> AssessmentScore:
    return AssessmentScore(
        assessment_type=assessment_type,
        score=score,
        severity_band=severity_for_score(assessment_type, score),
    )
