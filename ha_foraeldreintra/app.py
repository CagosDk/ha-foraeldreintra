from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/lektier")
def lektier():
    return jsonify({
        "status": "running",
        "message": "Addon works"
    })

@app.route("/")
def index():
    return "ForældreIntra Scraper is running"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
