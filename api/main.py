import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from api.cache import cache_url, get_cached_url
from api.codes import generate_code
from api.config import settings
from api.db import get_db
from api.events import flush_producer, publish_click
from api.models import DailyClick, Link
from api.rate_limit import rate_limit_create
from api.schemas import DayCount, LinkCreate, LinkList, LinkOut, LinkStats
from api.timing import timed

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("linkpulse")


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    flush_producer()


app = FastAPI(title="LinkPulse", lifespan=lifespan)
MAX_CODE_ATTEMPTS = 5


def to_out(link: Link) -> LinkOut:
    return LinkOut(
        code=link.code,
        long_url=link.long_url,
        short_url=f"{settings.base_url}/{link.code}",
        created_at=link.created_at,
    )


@app.get("/health")
def health():
    return {"status": "ok", "version": settings.app_version}


@app.get("/ready")
def ready(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return {"status": "ready"}


@app.post(
    "/links",
    response_model=LinkOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit_create)],
)
def create_link(payload: LinkCreate, db: Session = Depends(get_db)):
    for _ in range(MAX_CODE_ATTEMPTS):
        link = Link(code=generate_code(), long_url=str(payload.long_url))
        db.add(link)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        db.refresh(link)
        return to_out(link)
    raise HTTPException(status_code=500, detail="Could not generate a unique code")


@app.get("/links", response_model=LinkList)
def list_links(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    total = db.scalar(select(func.count()).select_from(Link))
    rows = db.scalars(
        select(Link).order_by(Link.created_at.desc(), Link.id.desc()).limit(limit).offset(offset)
    ).all()
    return LinkList(items=[to_out(r) for r in rows], total=total, limit=limit, offset=offset)


@app.get("/links/{code}/stats", response_model=LinkStats)
def link_stats(code: str, db: Session = Depends(get_db)):
    link = db.scalar(select(Link).where(Link.code == code))
    if link is None:
        raise HTTPException(status_code=404, detail="Link not found")

    rows = db.scalars(
        select(DailyClick).where(DailyClick.code == code).order_by(DailyClick.day)
    ).all()
    return LinkStats(
        code=code,
        total_clicks=sum(r.count for r in rows),
        daily=[DayCount(day=r.day, count=r.count) for r in rows],
    )


@app.get("/{code}")
@timed
def follow_link(code: str, request: Request, db: Session = Depends(get_db)):
    long_url = get_cached_url(code)
    if long_url is not None:
        logger.info("cache hit for %s", code)
    else:
        logger.info("cache miss for %s", code)
        link = db.scalar(select(Link).where(Link.code == code))
        if link is None:
            raise HTTPException(status_code=404, detail="Link not found")
        long_url = link.long_url
        cache_url(code, long_url)

    publish_click(code, request.headers.get("user-agent"))
    return RedirectResponse(long_url, status_code=307)
