import os
from threading import Lock

from flask import Flask, Response, jsonify, render_template, request, stream_with_context

from agent.tools.react_agent import ReactAgent
from rag.knowledge_base import KnowledgeBaseService
from rag.rag_service import RAGSummarizeService


app = Flask(__name__, template_folder="templates", static_folder="static")
agent = None
agent_lock = Lock()
knowledge_base_service = None
knowledge_base_lock = Lock()
rag_service = None
rag_service_lock = Lock()


def get_agent() -> ReactAgent:
    global agent
    if agent is None:
        with agent_lock:
            if agent is None:
                agent = ReactAgent()
    return agent


def get_knowledge_base_service() -> KnowledgeBaseService:
    global knowledge_base_service
    if knowledge_base_service is None:
        with knowledge_base_lock:
            if knowledge_base_service is None:
                knowledge_base_service = KnowledgeBaseService()
    return knowledge_base_service


def get_rag_service() -> RAGSummarizeService:
    global rag_service
    if rag_service is None:
        with rag_service_lock:
            if rag_service is None:
                rag_service = RAGSummarizeService()
    return rag_service


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


@app.post("/api/rag/query")
def rag_query():
    payload = request.get_json(silent=True) or {}
    prompt = (payload.get("prompt") or "").strip()

    if not prompt:
        return jsonify({"error": "prompt is required"}), 400

    try:
        result = get_rag_service().answer_with_references(prompt)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    return jsonify(result)


@app.post("/api/knowledge/upload")
def upload_knowledge():
    upload_file = request.files.get("file")
    if upload_file is None:
        return jsonify({"error": "file is required"}), 400

    file_name = (upload_file.filename or "").strip()
    if not file_name:
        return jsonify({"error": "filename is required"}), 400

    if not file_name.lower().endswith(".txt"):
        return jsonify({"error": "only .txt file is supported"}), 400

    try:
        text = upload_file.read().decode("utf-8")
    except UnicodeDecodeError:
        return jsonify({"error": "file must be utf-8 encoded text"}), 400

    if not text.strip():
        return jsonify({"error": "file content is empty"}), 400

    operator = (request.form.get("operator") or "web").strip() or "web"

    try:
        result = get_knowledge_base_service().upload_by_str(text, file_name, operator=operator)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    return jsonify({"result": result})


if __name__ == "__main__":
    host = os.environ.get("APP_HOST", "127.0.0.1")
    port = int(os.environ.get("APP_PORT", "7860"))
    debug = os.environ.get("APP_DEBUG", "0") == "1"
    app.run(host=host, port=port, debug=debug, threaded=True)
