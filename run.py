#!/usr/bin/env python3
"""EST Synthesizer — Server entry-point.

Reads ``HOST`` / ``PORT`` from ``.env`` (via ``backend.app.config``)
and starts uvicorn with those values.
"""

import uvicorn
from backend.app.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "backend.app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
    )
