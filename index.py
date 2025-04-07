from flask import Flask
from app import app

def handler(request):
    if request.method == "POST":
        return app(request.environ, lambda x, y: y)
    else:
        return app(request.environ, lambda x, y: y)