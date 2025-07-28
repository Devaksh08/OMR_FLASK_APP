import os
from flask import Flask

def create_app():
    """Create and configure an instance of the Flask application."""
    app = Flask(__name__)
    
    app.config['SECRET_KEY'] = 'a-super-secret-key-that-you-should-change'
    
    app.config['UPLOAD_FOLDER'] = 'static/uploads'

    upload_path = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])
    os.makedirs(upload_path, exist_ok=True)
    
    from .routes import main
    app.register_blueprint(main)
    
    return app