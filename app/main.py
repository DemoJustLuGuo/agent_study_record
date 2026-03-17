import os
from threading import Lock

from flask import Flask, Response, jsonify, render_template, request, stream_with_context

from agent.tools.react_agent import ReactAgent


app = Flask(__name__, template_folder="templates", static_folder="static")
agent = None
agent_lock = Lock()


def get_agent() -> ReactAgent:
    global agent
    if agent is None:
        with agent_lock:
            if agent is None:
                agent = ReactAgent()
    return agent


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/api/chat")
def chat():
    payload = request.get_json(silent=True) or {}
    prompt = (payload.get("prompt") or "").strip()

    if not prompt:
        return jsonify({"error": "prompt is required"}), 400

    def generate():
        try:
            runtime_agent = get_agent()
            for chunk in runtime_agent.execute_stream(prompt):
                yield chunk
        except Exception as exc:
            yield f"\n[ERROR] {str(exc)}"

    return Response(
        stream_with_context(generate()),
        mimetype="text/plain; charset=utf-8",
    )


if __name__ == "__main__":
    host = os.environ.get("APP_HOST", "127.0.0.1")
    port = int(os.environ.get("APP_PORT", "7860"))
    debug = os.environ.get("APP_DEBUG", "0") == "1"
    app.run(host=host, port=port, debug=debug, threaded=True)
