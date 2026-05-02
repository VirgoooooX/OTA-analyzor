import math

from fastapi import APIRouter, HTTPException, Response

from app.models import GenerateRequest
from app.services.data_service import get_cleaned_data

router = APIRouter(prefix="/api", tags=["charts"])


@router.post("/fetch_chart_data")
def api_fetch_chart_data(request: GenerateRequest):
    full_df, unique_cps, reports, summary = get_cleaned_data(
        request.files, request.includeFailData, request.channels
    )
    if full_df is None:
        raise HTTPException(status_code=400, detail={"message": "所选文件无有效数据", "reports": reports})

    sources = list(full_df["Source"].unique())
    if len(sources) > 10:
        sources = sources[:10]
        full_df = full_df[full_df["Source"].isin(sources)]

    data_records = full_df.replace({math.nan: None, math.inf: None, -math.inf: None}).to_dict(
        orient="records"
    )

    return {
        "data": data_records,
        "unique_cps": unique_cps,
        "sources": sources,
        "summary": summary,
        "file_reports": reports,
        "available_channels": sorted(full_df["Channel"].dropna().unique().tolist()),
        "available_frequencies": sorted(full_df["Frequency"].dropna().unique().tolist()),
    }


@router.post("/generate")
def api_generate_chart(request: GenerateRequest):
    from app.services.chart_service import generate_chart_image
    try:
        png_bytes, filename = generate_chart_image(
            request.files, request.includeFailData, request.channels
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    headers = {
        "Content-Disposition": f'inline; filename="{filename}"',
        "X-Filename": filename,
        "Access-Control-Expose-Headers": "X-Filename",
    }
    return Response(content=png_bytes, media_type="image/png", headers=headers)
