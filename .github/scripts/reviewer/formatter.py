from typing import List
from reviewer.policy import ReviewDecision

def format_review_decisions(decisions: List[ReviewDecision]) -> str:
    """
    Deterministic Formatter.
    Presentation-only layer. Renders evaluated Review Decisions.
    Does not derive severity, priority, or recommendations.
    """
    if not decisions:
        return "No notable architectural or security events detected.\n\n"
        
    output = "## Deterministic Review Decisions\n\n"
    
    for d in decisions:
        output += f"### {d['category']} [{d['priority']}]\n"
        
        if d['compatibility'] != "N/A":
            output += f"**Compatibility:** {d['compatibility']}\n\n"
            
        output += f"**Reason:** {d['reason']}\n\n"
        output += f"**Recommendation:** {d['recommendation']}\n\n"
        output += "---\n\n"
        
    return output
