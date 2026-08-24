import logging
import time
from fastapi import Request

logger = logging.getLogger("rxos.access")
error_logger = logging.getLogger("rxos.error")


async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = round((time.time() - start) * 1000, 2)

    log_data = {
        "method": request.method,
        "path": request.url.path,
        "status": response.status_code,
        "duration_ms": duration,
        "client": request.client.host if request.client else "unknown",
    }

    if response.status_code >= 500:
        error_logger.error(f"Request failed: {log_data}")
    elif response.status_code >= 400:
        logger.warning(f"Client error: {log_data}")
    else:
        logger.info(f"Request: {log_data}")

    return response
