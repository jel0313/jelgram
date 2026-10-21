"""現在時刻(20-3)。

`datetime.now()` を直接呼ぶと、テストで時刻を固定できない。
依存関数で受け取るようにしておけば、テストでは決まった時刻に差し替えられる。
日時は必ず UTC(タイムゾーン付き)で扱う(21-1)。
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends


def utcnow() -> datetime:
    return datetime.now(UTC)


NowDep = Annotated[datetime, Depends(utcnow)]
