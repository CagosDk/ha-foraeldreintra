from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/")
def index():
    return "ForældreIntra Scraper is running"

@app.route("/lektier")
def lektier():
    return jsonify({
        "status": "ok",
        "data": "Test data"
    })

if __name__ == "__main__":
    print("Starting Flask server...")
    app.run(host="0.0.0.0", port=8080)
