"""SQL Server `geography` column support (SRID 4326, WGS 84).

Values travel as WKT strings: writes are wrapped in geography::STGeomFromText(?, 4326) and reads in
.STAsText(). All spatial measurements (area, intersection, distance) are computed by SQL Server, which is
the authoritative source; the browser only previews.
"""
from typing import Any

from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.functions import FunctionElement
from sqlalchemy.types import UserDefinedType

SRID = 4326


class Geography(UserDefinedType[str]):
    cache_ok = True

    def get_col_spec(self, **kw: Any) -> str:
        return "geography"

    def bind_expression(self, bindvalue: Any) -> Any:
        return GeographyFromText(bindvalue)

    def column_expression(self, col: Any) -> Any:
        return GeographyAsText(col)

    def __repr__(self) -> str:  # used by Alembic autogenerate
        return "Geography()"


class GeographyFromText(FunctionElement[str]):
    inherit_cache = True
    name = "geography_from_text"


class GeographyAsText(FunctionElement[str]):
    inherit_cache = True
    name = "geography_as_text"


@compiles(GeographyFromText, "mssql")
def _from_text(element: GeographyFromText, compiler: Any, **kw: Any) -> str:
    return f"geography::STGeomFromText({compiler.process(element.clauses, **kw)}, {SRID})"


@compiles(GeographyAsText, "mssql")
def _as_text(element: GeographyAsText, compiler: Any, **kw: Any) -> str:
    return f"({compiler.process(element.clauses, **kw)}).STAsText()"
