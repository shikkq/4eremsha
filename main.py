from flask import Flask

app = Flask(__name__)

@app.route("/")
def index():
    return "Index OK", 200

@app.route("/run-parser")
def run_parser():
    return "Парсер endpoint работает", 200

if __name__ == "__main__":
    app.run()
