FROM drugflow_marker:v4
ENV PATH /opt/conda/bin:$PATH
# 激活新环境
SHELL ["conda", "run", "-n", "myenv", "/bin/bash", "-c"]

COPY requirements-otel.txt /tmp/requirements-otel.txt

# RUN conda run -n myenv conda install -y -c conda-forge cairo pango gdk-pixbuf libffi

RUN pip install -r /tmp/requirements-otel.txt -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple
RUN pip install "mammoth>=1.11.0" -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple
RUN pip install boto3 -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple

WORKDIR /app

COPY ./ /app/
