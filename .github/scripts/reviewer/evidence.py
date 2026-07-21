from typing import TypedDict, Optional, Any, Literal, Dict

EvidenceType = Literal['api_signature', 'security_sink', 'architecture', 'code_smell']
EvidenceSource = Literal['ast', 'semantic', 'git', 'security', 'impact']
Severity = Literal['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']

class ApiSignatureAttributes(TypedDict, total=False):
    changeType: Literal['required_parameter_added', 'optional_parameter_added', 'parameter_removed', 'return_type_changed', 'signature_modified']
    compatibility: Optional[Literal['breaking', 'backward_compatible']]
    affectedCallers: Optional[int]
    impactScore: Optional[int]
    reason: Optional[str]

class SecurityAttributes(TypedDict, total=False):
    sink: str
    sanitizerDetected: bool
    source: Optional[str]
    reason: Optional[str]

class CodeSmellAttributes(TypedDict, total=False):
    smellType: str
    lines: int
    reason: Optional[str]

class Evidence(TypedDict):
    schemaVersion: int
    id: str
    type: EvidenceType
    source: EvidenceSource
    severity: Severity
    attributes: Dict[str, Any]
    evidence: str # Legacy UI field
