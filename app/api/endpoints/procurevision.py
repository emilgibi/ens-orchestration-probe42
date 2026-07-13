from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, Query
from app.api import deps
from app.models import User
from app.schemas.requests import CompleteData, VendorAIBriefRequest
from app.schemas.responses import ResponseMessage
from app.core.analysis.orbis_submodules.COMPANY_orbis import orbis_complete_company_data, search_probe42_companies_by_name, generate_vendor_ai_brief

router = APIRouter()


def _response_data(data):
    if isinstance(data, dict):
        return data
    if data is None:
        return {}
    return {"value": data}


@router.post(
    "/get-complete-company-data", response_model=ResponseMessage, description="Run Full Data Fetching (Synchronous)"
)
async def get_complete_company_data(request: CompleteData, session: AsyncSession = Depends(deps.get_session), current_user: User = Depends(deps.get_current_user)):
    try:
        # Pass the validated request data to the analysis function
        request_data = request.model_dump()
        results = await orbis_complete_company_data(
            request_data,
            session
        )
        if results.get("status") != "completed":
            status_code = int(results.get("upstream_status_code") or 502)
            if status_code < 400:
                status_code = 502
            raise HTTPException(
                status_code=status_code,
                detail={
                    "message": results.get("message", "Unable to fetch complete company data"),
                    "data": results,
                },
            )

        return ResponseMessage(
            status=str(results.get("upstream_status_code", 200)),
            data=_response_data(results.get("data")),
            message=results.get(
                "message",
                f"Analysis Pipeline Completed for {request_data.get('identifier', '')}",
            ),
        )

    except HTTPException:
        raise
    except Exception as e:
        # Handle errors gracefully
        raise HTTPException(status_code=500, detail=f"Error submitting analysis: {str(e)}")


@router.get(
    "/probe42/nameSearch",
    response_model=ResponseMessage,
    description="List Probe42 company and LLP matches by name",
)
async def probe42_name_search(
    orgName: str = Query(..., min_length=3),
    current_user: User = Depends(deps.get_current_user),
):
    try:
        results = await search_probe42_companies_by_name(orgName)
        if results.get("status") != "completed":
            status_code = int(results.get("upstream_status_code") or 502)
            if status_code < 400:
                status_code = 502
            raise HTTPException(
                status_code=status_code,
                detail={
                    "message": results.get("message", "Unable to fetch Probe42 name search data"),
                    "data": results,
                },
            )

        return ResponseMessage(
            status=str(results.get("upstream_status_code", 200)),
            data={"results": results.get("data", [])},
            message=results.get("message", "Successful"),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching Probe42 name search data: {str(e)}")

@router.post(
    "/vendor-risk/ai-brief",
    response_model=ResponseMessage,
    description="Generate a Gemini AI risk brief from stored Probe42 data",
)
async def vendor_ai_brief(
    request: VendorAIBriefRequest,
    session: AsyncSession = Depends(deps.get_session),
    current_user: User = Depends(deps.get_current_user),
):
    try:
        results = await generate_vendor_ai_brief(request.model_dump(), session)
        if results.get("status") != "completed":
            status_code = int(results.get("upstream_status_code") or 502)
            if status_code < 400:
                status_code = 502
            raise HTTPException(
                status_code=status_code,
                detail={
                    "message": results.get("message", "Unable to generate AI brief"),
                    "data": results,
                },
            )
        return ResponseMessage(
            status=str(results.get("upstream_status_code", 200)),
            data=_response_data(results.get("data")),
            message=results.get("message", f"AI brief generated for {request.identifier}"),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating AI brief: {str(e)}")