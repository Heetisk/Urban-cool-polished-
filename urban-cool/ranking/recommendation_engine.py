"""
Recommendation Engine - Generates intervention recommendations based on priority scores.

Risk Levels:
  0.8-1.0 -> Critical  -> Tree planting + Cool roofs + Green roofs
  0.6-0.8 -> High      -> Tree planting + Cool roofs
  0.4-0.6 -> Moderate  -> Tree planting
  0.0-0.4 -> Low       -> Maintain current green cover
"""


def classify_risk(score):
    """Classify priority score into risk level."""
    if score >= 0.8:
        return "critical"
    elif score >= 0.6:
        return "high"
    elif score >= 0.4:
        return "moderate"
    return "low"


def get_recommendation(score, ndvi, builtup_density):
    """Generate intervention recommendation based on cell characteristics."""
    risk = classify_risk(score)

    if risk == "critical":
        actions = []
        if builtup_density > 0.7:
            actions.append("Cool roofs")
        if ndvi < 0.3:
            actions.append("Tree planting")
        else:
            actions.append("Expand green cover")
        if not actions:
            actions = ["Tree planting", "Cool roofs", "Green roofs"]
        return {
            "risk_level": risk,
            "actions": actions,
            "summary": f"Immediate action required: {', '.join(actions)}",
        }

    if risk == "high":
        actions = []
        if ndvi < 0.35:
            actions.append("Tree planting")
        if builtup_density > 0.6:
            actions.append("Cool roofs")
        if not actions:
            actions = ["Tree planting", "Cool roofs"]
        return {
            "risk_level": risk,
            "actions": actions,
            "summary": f"High priority: {', '.join(actions)}",
        }

    if risk == "moderate":
        if ndvi < 0.4:
            action = "Tree planting to increase canopy cover"
        else:
            action = "Maintain and monitor green infrastructure"
        return {
            "risk_level": risk,
            "actions": ["Tree planting"],
            "summary": f"Moderate priority: {action}",
        }

    return {
        "risk_level": risk,
        "actions": ["Maintain"],
        "summary": "Low priority: Maintain current green cover",
    }


def enrich_rankings(rankings):
    """Add risk level and recommendations to rankings."""
    for r in rankings:
        rec = get_recommendation(
            r["priority_score"],
            r.get("ndvi", 0),
            r.get("builtup_density", 0),
        )
        r["risk_level"] = rec["risk_level"]
        r["recommendation"] = rec["summary"]
        r["actions"] = rec["actions"]

    return rankings
