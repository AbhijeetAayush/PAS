from __future__ import annotations

from api.main import create_app

app = create_app()

try:
    from mangum import Mangum

    handler = Mangum(app, lifespan="off")
except ModuleNotFoundError:  # local runs that have not installed the Lambda adapter yet
    handler = None
