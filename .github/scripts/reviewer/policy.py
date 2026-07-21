from typing import List, Literal, TypedDict, Optional
from reviewer.evidence import Evidence

ReviewPriority = Literal['INFO', 'WARNING', 'REVIEW_REQUIRED', 'BLOCKING']

class ReviewDecision(TypedDict):
    id: str
    priority: ReviewPriority
    category: str
    compatibility: str
    reason: str
    recommendation: str

def evaluate_review_policy(enriched_evidence: List[Evidence]) -> List[ReviewDecision]:
    """
    Review Policy Engine.
    Evaluates enriched Evidence and assigns developer-facing review priorities.
    It does not mutate the Evidence.
    """
    decisions = []
    
    for ev in enriched_evidence:
        attrs = ev["attributes"]
        ev_type = ev["type"]
        
        priority: ReviewPriority = "INFO"
        category = "Observation"
        compatibility = "N/A"
        reason = ""
        recommendation = ""
        
        if ev_type == "api_signature":
            category = "Public API Modification"
            compat = attrs.get("compatibility", "unknown")
            if compat == "backward_compatible":
                priority = "INFO"
                compatibility = "Backward Compatible"
                reason = "Public API signature changed. Impact analysis confirmed this change is backward compatible."
                recommendation = "No action required. Review downstream consumers if additional changes are introduced."
            elif compat == "breaking":
                priority = "BLOCKING"
                compatibility = "Breaking Change"
                reason = "Public API signature changed in a backward-incompatible way."
                recommendation = "You must update downstream consumers or revert the API change."
            else:
                priority = "REVIEW_REQUIRED"
                compatibility = "Unknown"
                reason = "Public API signature changed, but compatibility could not be proven."
                recommendation = "Review downstream consumers to ensure they are compatible with the new signature."
                
        elif ev_type == "security_sink":
            category = "Security"
            sanitizer = attrs.get("sanitizerDetected", False)
            if not sanitizer:
                priority = "BLOCKING"
                reason = f"Security sink '{attrs.get('sink', 'unknown')}' used without sanitizer."
                recommendation = "Implement a sanitizer before merging."
            else:
                priority = "INFO"
                reason = f"Security sink '{attrs.get('sink', 'unknown')}' detected, but a sanitizer is present."
                recommendation = "Ensure the sanitizer handles all edge cases."
                
        elif ev_type == "code_smell":
            category = "Code Quality"
            priority = "WARNING"
            reason = attrs.get("reason", "Code smell detected.")
            recommendation = "Consider refactoring to improve maintainability."
            
        elif ev_type == "architecture":
            category = "Architecture"
            priority = "BLOCKING"
            reason = attrs.get("reason", "Architecture violation detected.")
            recommendation = "Verify that appropriate dependencies or decorators are applied according to architecture guidelines."
                        
        decisions.append({
            "id": ev["id"],
            "priority": priority,
            "category": category,
            "compatibility": compatibility,
            "reason": reason,
            "recommendation": recommendation
        })
        
    return decisions
