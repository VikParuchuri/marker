docker stop gpt_marker
docker rm gpt_marker

docker run -d -p 8089:8089 -v ./:/app -v ~/.cache/huggingface:/root/.cache/huggingface -v ~/.cache/datalab:/root/.cache/datalab -v ~/dev/checkpoints:/app/img2mol/clean_img2smiles/src/img2smiles/checkpoints --gpus '"device=0"' --network scigpt-router_gptnetwork --ip 172.22.0.8 -e OTEL_ENABLED=true \
  -e OTEL_SERVICE_NAME=gpt-marker \
  -e OTEL_SERVICE_NAMESPACE=scigpt \
  -e OTEL_EXPORTER_OTLP_ENDPOINT=http://10.25.10.41:4318 \
  -e OTEL_TRACES_EXPORTER=otlp \
  -e OTEL_METRICS_EXPORTER=otlp \
  -e OTEL_PYTHON_EXCLUDED_URLS=/api/ping \
  -e MARKER_PARSE_CALLBACK_TOKEN=5f08e604547e84e7c335f415547aa1f875352d7172e8c9e \
  -e RAG_CALLBACK_TOKEN=5f08e604547e84e7c335f415547aa1f875352d7172e8c9e \
  --restart always \
  --name gpt_marker carbonsilicon-ai-registry.cn-hangzhou.cr.aliyuncs.com/teamcity/drugflow_marker:v7 ./app.sh
