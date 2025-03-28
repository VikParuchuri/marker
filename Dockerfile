FROM python:3.10-bookworm

SHELL [ "/bin/bash", "-c" ]

ENV SHELL=/bin/bash
ENV POETRY_HOME=/etc/poetry
ENV PATH="$POETRY_HOME/venv/bin:$PATH"

RUN apt update && apt upgrade -y
RUN apt install libgl1 -y

RUN apt install python3-pip pipx -y
RUN apt autoremove -y
RUN apt autoclean -y
RUN curl -sSL https://install.python-poetry.org | POETRY_HOME=/etc/poetry python3 -

WORKDIR /usr/src/marker
COPY marker marker
COPY pyproject.toml .
RUN poetry env use $(which python3)
RUN poetry install --verbose -v

COPY marker_server.py .

EXPOSE 80
CMD ["poetry", "run", "python", "marker_server.py", "--port","80"]