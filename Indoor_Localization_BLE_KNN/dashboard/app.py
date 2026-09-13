from flask import Flask, jsonify, render_template
from flask_cors import CORS
from ml_localizer import latest_data, data_lock

app = Flask(__name__)
CORS(app)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/data")
def data():
    with data_lock:
        snapshot = dict(latest_data)
    return jsonify(snapshot)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)