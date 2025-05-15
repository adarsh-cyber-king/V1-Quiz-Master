import os
import logging
from flask import Flask, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from werkzeug.exceptions import HTTPException
import traceback
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

# Initialize SQLAlchemy
db = SQLAlchemy(model_class=Base)
csrf = CSRFProtect()
login_manager = LoginManager()

def create_app():
    app = Flask(__name__)

    # Configure Secret Key and Database
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///quiz_master.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Initialize extensions
    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)

    # Configure Login Manager
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'

    from models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register Blueprints
    from routes import auth_bp, admin_bp, user_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(user_bp)

    # Custom template not found handler
    from jinja2 import TemplateNotFound
    

    @app.errorhandler(TemplateNotFound)
    def handle_template_not_found(error):
        template_path = os.path.join('templates', str(error.name))
        os.makedirs(os.path.dirname(template_path), exist_ok=True)

        # Create basic template extending base.html
        with open(template_path, 'w') as f:
            f.write("""{% extends 'base.html' %}
{% block content %}
<div class="container mx-auto p-4">
    <h1 class="text-2xl font-bold mb-4">{{ title|default('Page Title') }}</h1>

    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            {% for category, message in messages %}
                <div class="alert alert-{{ category }} mb-4">{{ message }}</div>
            {% endfor %}
        {% endif %}
    {% endwith %}

    <!-- Auto-generated form -->
    {% if form %}
        <form method="POST" class="max-w-md">
            {{ form.csrf_token }}
            {% for field in form if field.name != 'csrf_token' %}
                <div class="mb-4">
                    {{ field.label(class="block text-gray-700 text-sm font-bold mb-2") }}
                    {{ field(class="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight") }}
                    {% if field.errors %}
                        {% for error in field.errors %}
                            <p class="text-red-500 text-xs italic">{{ error }}</p>
                        {% endfor %}
                    {% endif %}
                </div>
            {% endfor %}
            <button type="submit" class="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded">
                Submit
            </button>
        </form>
    {% endif %}
</div>
{% endblock %}""")

        # Reload the template
        return app.jinja_env.get_template(error.name)

    with app.app_context():
        # Import models and create tables
        from models import User, Subject, Chapter, Quiz, Question, Score
        db.create_all()

        # Register error handlers
        @app.errorhandler(404)
        def not_found_error(error):
            if request.is_json:
                return jsonify({"error": "Resource not found"}), 404
            return render_template('error.html', error=404, message="Page not found"), 404

        @app.errorhandler(403)
        def forbidden_error(error):
            if request.is_json:
                return jsonify({"error": "Access forbidden"}), 403
            return render_template('error.html', error=403, message="Access forbidden"), 403

        @app.errorhandler(500)
        def internal_error(error):
            db.session.rollback()
            if request.is_json:
                return jsonify({"error": "Internal server error"}), 500
            return render_template('error.html', error=500, message="Internal server error"), 500

        @app.errorhandler(SQLAlchemyError)
        def database_error(error):
            db.session.rollback()
            app.logger.error(f"Database error: {str(error)}\n{traceback.format_exc()}")
            if request.is_json:
                return jsonify({"error": "Database error occurred"}), 500
            return render_template('error.html', error=500, message="Database error occurred"), 500

        @app.errorhandler(Exception)
        def unhandled_exception(error):
            app.logger.error(f"Unhandled exception: {str(error)}\n{traceback.format_exc()}")
            if request.is_json:
                return jsonify({"error": "An unexpected error occurred"}), 500
            return render_template('error.html', error=500, message="An unexpected error occurred"), 500

        # Create an admin user if none exists
        if not User.query.filter_by(is_admin=True).first():
            from models import User
            admin = User(
                email='admin@quizmaster.com',
                username='admin',
                full_name='Admin User',
                is_admin=True
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()

    # Configure logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        logger.error(f"Page not found: {error}")
        return render_template('error.html', error=404, message="Page not found"), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        logger.error(f"Server error: {error}")
        return render_template('error.html', error=500, message="Internal server error"), 500

    @app.errorhandler(Exception)
    def unhandled_exception(error):
        db.session.rollback()
        logger.error(f"Unhandled exception: {error}")
        return render_template('error.html', error=500, message="An unexpected error occurred"), 500

    return app