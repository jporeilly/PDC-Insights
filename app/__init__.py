"""Catalog Insights application package.

The web layer is FastAPI (see app/main.py — the port of the old Flask
factory); create_app() is re-exported here so `from app import create_app`
keeps working for the tests and the ASGI entrypoint.
"""
from .main import create_app  # noqa: F401
