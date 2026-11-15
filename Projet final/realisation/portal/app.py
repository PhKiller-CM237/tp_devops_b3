import os
import socket

from flask import Flask, jsonify, render_template

app = Flask(__name__)


@app.route("/")
def index():
    return render_template(
        "index.html",
        name=socket.gethostname(),
        odoo_url=os.getenv("ODOO_URL", "https://www.odoo.com/"),
        pgadmin_url=os.getenv("PGADMIN_URL", "https://www.pgadmin.org/"),
        version=os.getenv("APP_VERSION", "dev"),
    )


@app.route("/health")
def health():
    return jsonify(status="ok")


@app.route("/api/info")
def info():
    return jsonify(
        app="legeni-academy",
        version=os.getenv("APP_VERSION", "dev"),
        hostname=socket.gethostname(),
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
