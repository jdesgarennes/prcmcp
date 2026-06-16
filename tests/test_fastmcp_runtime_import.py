import os
import subprocess
import time


def test_fastmcp_can_import_server_file_without_repo_on_pythonpath():
    env = os.environ.copy()
    # Keep installed dependencies available, but intentionally do not add the
    # repository root. This matches the Kubernetes `fastmcp run app/server.py`
    # runtime shape that previously failed with: No module named 'app'.
    proc = subprocess.Popen(
        [
            "fastmcp",
            "run",
            "app/server.py",
            "--transport",
            "http",
            "--host",
            "127.0.0.1",
            "--port",
            "3999",
            "--path",
            "/mcp/",
        ],
        cwd=".",
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        output = ""
        deadline = time.time() + 8
        while time.time() < deadline:
            line = proc.stdout.readline() if proc.stdout else ""
            output += line
            if "No module named 'app'" in output:
                break
            if "Application startup complete" in output or "Uvicorn running" in output:
                break
            if proc.poll() is not None:
                output += proc.stdout.read() if proc.stdout else ""
                break

        assert "No module named 'app'" not in output
        assert "Application startup complete" in output or "Uvicorn running" in output, output
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
