from fastapi import APIRouter
from pydantic import BaseModel

from app import __version__
from app.settings import get_settings

router = APIRouter()


class Meta(BaseModel):
    version: str
    demo_mode: bool
    session_timeout_min: int
    decimal_separator: str
    tz_display: str


@router.get("/meta", response_model=Meta)
def meta() -> Meta:
    s = get_settings()
    return Meta(
        version=__version__,
        demo_mode=s.demo_mode,
        session_timeout_min=s.session_timeout_min,
        decimal_separator=s.decimal_separator,
        tz_display=s.tz_display,
    )
