import subprocess
import os


def run():
    cur_dir = os.path.dirname(os.path.abspath(__file__))
    app_path = os.path.join(cur_dir, "marker_app.py")
    cmd = ["streamlit", "run", app_path]
    subprocess.run(cmd, env={**os.environ, "IN_STREAMLIT": "true"})


if __name__ == "__main__":
    run()