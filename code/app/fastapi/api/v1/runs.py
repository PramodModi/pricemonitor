import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.database import get_db
from app.fastapi.api.dependencies import verify_internal_token
from app.fastapi.schemas.run import RunOut, RunListOut, RunFailureItem
from app.repositories.scheduler_run_repo import SchedulerRunRepository
from app.core.models import PriceHistory, Product

router = APIRouter(
    prefix="/runs",
    tags=["runs"],
    dependencies=[Depends(verify_internal_token)],
)


@router.get("", response_model=RunListOut)
def list_runs(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> RunListOut:
    """List recent scheduler runs. Requires Bearer token."""
    repo = SchedulerRunRepository(db)
    total, runs = repo.list_recent(limit=limit, offset=offset)
    return RunListOut(
        total=total,
        limit=limit,
        offset=offset,
        runs=[RunOut.model_validate(r) for r in runs],
    )


@router.get("/{run_id}", response_model=RunOut)
def get_run(
    run_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> RunOut:
    """Get one scheduler run with failure details. Requires Bearer token."""
    repo = SchedulerRunRepository(db)
    run = repo.get_by_id(run_id)
    if run is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "RUN_NOT_FOUND", "message": "Run not found."},
        )

    failures_raw = db.execute(
        select(PriceHistory, Product.url, Product.name)
        .join(Product, PriceHistory.product_id == Product.product_id)
        .where(
            PriceHistory.run_id == run_id,
            PriceHistory.scrape_status.in_(["failed", "blocked"]),
        )
    ).all()

    failures = [
        RunFailureItem(
            product_id=row.PriceHistory.product_id,
            product_name=row.name,
            url=row.url,
            scrape_status=row.PriceHistory.scrape_status,
            checked_at=row.PriceHistory.checked_at,
        )
        for row in failures_raw
    ]

    out = RunOut.model_validate(run)
    out.failures = failures
    return out