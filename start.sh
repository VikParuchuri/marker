docker stop gpt_marker
docker rm gpt_marker

docker run -d -p 8089:8080 -v ./:/app -v /home/luohao/.cache/huggingface:/root/.cache/huggingface -v /home/luohao/.cache/datalab:/root/.cache/datalab --gpus '"device=3"' --name gpt_marker gpt_marker:v3 ./app.sh
