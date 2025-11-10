from flask import Flask
from flask import render_template
from dotenv import load_dotenv
import os

load_dotenv()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

    @app.route('/')
    def index():
        return {'message': 'Welcome to PMV API'}

    return app