from app import app
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure app for production
app.wsgi_app = ProxyFix(app.wsgi_app)

if __name__ == '__main__':
    app.run()

def handler(request, context):
    return app.wsgi_app(request, context)