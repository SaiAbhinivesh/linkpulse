from datetime import date, datetime

from pydantic import BaseModel, HttpUrl


class LinkCreate(BaseModel):
    long_url: HttpUrl


class LinkOut(BaseModel):
    code: str
    long_url: str
    short_url: str
    created_at: datetime


class LinkList(BaseModel):
    items: list[LinkOut]
    total: int
    limit: int
    offset: int


class DayCount(BaseModel):
    day: date
    count: int


class LinkStats(BaseModel):
    code: str
    total_clicks: int
    daily: list[DayCount]
