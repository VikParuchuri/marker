import subprocess
import os
import sys


def streamlit_app_cli(app_name: str = "streamlit_app.py"):
    argv = sys.argv[1:]
    cur_dir = os.path.dirname(os.path.abspath(__file__))
    app_path = os.path.join(cur_dir, app_name)
    cmd = [
        "streamlit",
        "run",
        app_path,
        "--server.fileWatcherType",
        "none",
        "--server.headless",
        "true",
    ]
    if argv:
        cmd += ["--"] + argv
    subprocess.run(cmd, env={**os.environ, "IN_STREAMLIT": "true"})


def extraction_app_cli():
    streamlit_app_cli("extraction_app.py")
