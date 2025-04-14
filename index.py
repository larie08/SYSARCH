from app import app
from flask import Flask, Request

def create_app():
    return app

app = create_app()

def handler(request):
    """Handle incoming requests."""
    with app.request_context(request):
        return app