from flask import Flask
from vk_parser import run_parser  # Убедись, что функция существует и импорт работает

app = Flask(__name__)

@app.route('/')
def index():
    return "Flask работает!"

@app.route('/run-parser')
def trigger_parser():
    run_parser()
    return "Парсер запущен!"

# Убедись, что порт берётся из переменной среды, как требует Render
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
