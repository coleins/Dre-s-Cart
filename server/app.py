from flask import Flask
from flask_cors import CORS

app = Flask(__name__)

CORS(app)

@app.route('/')
def index():
    return '<h1>Flask is running!</h1>'

if __name__ == '__main__':
    app.run(port=5555, debug=True)