from fastapi import Request
from fastapi.exceptions import RequestValidationError
from pilot.openapi.api_view_model import Result


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    message = "".join(
        ".".join(error.get("loc")) + ":" + error.get("msg") + ";"
        for error in exc.errors()
    )
    return Result.failed(code="E0001", msg=message)
