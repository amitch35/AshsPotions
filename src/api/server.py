from fastapi import FastAPI, exceptions
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from src.api import audit, carts, catalog, bottler, barrels, admin
import json
import logging
import sys
from starlette.middleware.cors import CORSMiddleware

description = """
Ash's Potions is a totally radical potion site where we forge all your alchemical concoctions.
"""

app = FastAPI(
    title="Ash's Potions",
    description=description,
    version="0.4.16",
    terms_of_service="http://example.com/terms/",
    contact={
        "name": "Ash Mitchell",
        "email": "amitch35@calpoly.edu",
    },
)

origins = ["https://potion-exchange.vercel.app"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(audit.router)
app.include_router(carts.router)
app.include_router(catalog.router)
app.include_router(bottler.router)
app.include_router(barrels.router)
app.include_router(admin.router)

@app.exception_handler(exceptions.RequestValidationError)
@app.exception_handler(ValidationError)
async def validation_exception_handler(request, exc):
    logging.error(f"The client sent invalid data!: {exc}")
    exc_json = json.loads(exc.json())
    response = {"message": [], "data": None}
    for error in exc_json:
        response['message'].append(f"{error['loc']}: {error['msg']}")

    return JSONResponse(response, status_code=422)

@app.get("/")
async def root():
    return {"message": "Welcome to Ash's Potions."}
