from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class BaseRequest(BaseModel):
    # may define additional fields or config shared across requests
    pass


class RefreshTokenRequest(BaseRequest):
    refresh_token: str


class UserUpdatePasswordRequest(BaseRequest):
    password: str


class UserCreateRequest(BaseRequest):
    email: EmailStr
    password: str


class AnalysisRequest(BaseRequest):
    """
    Schema for input data required for Phase 1 Analysis.
    """

    session_id: str

class AnalysisRequestSingle(BaseRequest):
    """
    Schema for input data required for Phase 1 Analysis.
    """
    ens_id: str
    session_id: str

class GraphRequest(BaseRequest):
    """
    Schema for input data required for Phase 1 Analysis.
    """
    ens_id: str
    session_id: str



class BulkAnalysisRequest(BaseRequest):
    """
    Schema for handling multiple analysis requests in bulk.
    """
    # TODO should be deprecated
    requests: list[AnalysisRequest]


class StreamingENSIdRequest(BaseRequest):
    """
    Schema for input data required for streaming request for ens_ids (given as a list of ids in req body)
    """

    ens_id_list: list[str]
    session_id: str


class StreamingSessionIdRequest(BaseRequest):
    """
    Schema for input data required for streaming request for session_ids
    """

    session_id: str



class CompleteData(BaseRequest):
    identifier: str = Field(min_length=3)
    identifier_type: str = Field(min_length=3)
    entity_type: str = Field(min_length=3)

class ProcurementContext(BaseRequest):
    category:         Optional[str] = None   # e.g. "Active Pharmaceutical Ingredients"
    contract_value:   Optional[str] = None   # e.g. "₹2.5 Cr"
    duration:         Optional[str] = None   # e.g. "12 months"
    criticality:      Optional[str] = None   # e.g. "High"
    supplier_name:    Optional[str] = None
    additional_notes: Optional[str] = None


class VendorAIBriefRequest(BaseRequest):
    identifier:           str = Field(..., min_length=3)
    brief_type:           str = Field(default="generic")        # "generic" | "procurement"
    procurement_context:  Optional[ProcurementContext] = None

