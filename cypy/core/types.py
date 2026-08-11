import sys as _sys
from typing import Any as _Any, Dict as _Dict, List as _List, TypeAlias as _TA

if _sys.version_info >= (3, 11):
    from typing import Never as _Never
    Never: _TA = _Never
else:
    from typing import NoReturn as _NoReturn
    Never: _TA = _NoReturn

AnyDict: _TA = _Dict[str, _Any]
APIKey: _TA = str
BBox: _TA = _List[int]       # [x1, y1, x2, y2]
BBoxList: _TA = _List[BBox]
