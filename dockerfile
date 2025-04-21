FROM drugflow_marker:base

RUN pip install marker-pdf==1.6.2 -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple
# 删除marker-pdf自动安装的torch等依赖，释放空间
RUN pip install torch==2.3.1 torchvision==0.18.1 torchaudio==2.3.1 --index-url https://download.pytorch.org/whl/cu118

RUN pip install python-docx python-pptx -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple

