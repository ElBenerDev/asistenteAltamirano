import os
import json
import requests
import asyncio
from openai import OpenAI
from dotenv import load_dotenv
from typing import Dict, Optional
from flask import Flask, render_template, request, jsonify, url_for
from aiAssistant import SimpleAssistant
import asyncio
from functools import wraps
import logging
import time
from dotenv import load_dotenv
import asyncio
from flask_cors import CORS
from concurrent.futures import ThreadPoolExecutor
from flask import Blueprint
import atexit
import threading
from functools import partial
from typing import Tuple, Optional
from typing import Dict, Any
from enum import Enum

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Configure Flask app
app = Flask(__name__, 
    static_folder='static',
    template_folder='templates'
)
CORS(app)

assistant = SimpleAssistant()

def async_route(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        logger.debug(f"Starting async route for {f.__name__}")
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(f(*args, **kwargs))
            loop.close()
            logger.debug(f"Async route {f.__name__} completed successfully")
            return result
        except Exception as e:
            logger.error(f"Error in async route {f.__name__}: {str(e)}", exc_info=True)
            return jsonify({"error": str(e)}), 500
    return decorated_function

@app.route('/')
def home():
    logger.debug("Serving home page")
    return render_template('index.html')  # Changed from chat.html to index.html

@app.route('/chat', methods=['POST'])
def chat():
    message = request.json.get('message')
    if not message:
        return jsonify({'error': 'No message provided'}), 400

    # Run the async chat in a sync context
    response = asyncio.run(assistant.chat(message))
    logger.debug(f"Chat response: {response}")
    return jsonify(response)

if __name__ == '__main__':
    logger.info("Starting Flask application")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(assistant.start_conversation())
    logger.info("Initial conversation started")
    app.run(debug=True)

