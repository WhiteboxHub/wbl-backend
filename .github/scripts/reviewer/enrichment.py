import copy
from typing import List, Dict
from reviewer.evidence import Evidence

def enrich_evidence(evidence_list: List[Evidence]) -> List[Evidence]:
    """
    Semantic Evidence Enrichment layer.
    Augments Evidence with impact analysis, compatibility, and downstream metadata
    without modifying the original deterministic observations.
    """
    enriched = []
    for ev in evidence_list:
        # Create a deep copy to ensure original evidence is strictly immutable
        enriched_ev = copy.deepcopy(ev)
        
        # Example Enrichment logic (in reality, this would query the callgraph or semantic engine)
        if enriched_ev["type"] == "api_signature":
            # If affectedCallers > 0 and changeType isn't parameter_removed, it might be safe if optional
            attrs = enriched_ev["attributes"]
            if "compatibility" not in attrs:
                # Fallback simple heuristic for demo purposes
                if attrs.get("changeType") == "signature_modified":
                    attrs["compatibility"] = "backward_compatible" # Assume safe unless proven otherwise by AST
        
        enriched.append(enriched_ev)
    return enriched
