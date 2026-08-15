"""
iteration_engine — Day-14 stall diagnosis (engineering-spec §4.3).
If proposals_sent >= 5 and responses_received == 0, diagnose the bottleneck
(price / portfolio / niche) from the sprint's own data and assign a remedial
micro-course. Deterministic for testability.
"""


def diagnose(sprint):
    proposals = sprint.get("proposals_sent", 0)
    responses = sprint.get("responses_received", 0)
    if proposals < 5 or responses > 0:
        return None

    avg_value = sprint.get("avg_contract_value")
    contracts = sprint.get("contracts_won", 0)
    interviews = sprint.get("interviews_held", 0)

    if avg_value is not None and avg_value > 0 and contracts == 0 and interviews > 0:
        return "price"
    if contracts == 0 and interviews == 0 and proposals >= 5:
        return "portfolio"
    return "niche"
