#!/usr/bin/env bash
# PDF -> Markdown через Marker из EyesHead/marker и облачный Ollama API.
# Положите скрипт рядом с прежним ScriptMacOS.sh в хранилище PolytechBrain.
# Источник:  <папка скрипта>/PDF/*.pdf
# Результат: <папка скрипта>/Output/<имя PDF>/<имя PDF>.md и изображения рядом.
# Готовые результаты пропускаются; FORCE=1 ./ScriptMacOS-Ollama.sh пересобирает их.

set -u
set -o pipefail

# Настройки
MARKER_REPO="https://github.com/EyesHead/marker.git"
MARKER_CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/eyeshead-marker"
MARKER_ROOT="$MARKER_CACHE/source"
MARKER_VENV="$MARKER_CACHE/venv"
OLLAMA_MODEL="gemma4:31b"
OLLAMA_BASE_URL="https://ollama.com/v1"
PAGE_BATCH_SIZE=30
REDO_INLINE_MATH=1
MODE=""                         # "", "fast" или "balanced"
FORCE_OCR=0                     # 1 — распознавать заново все страницы

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PDF_DIR="$SCRIPT_DIR/PDF"
OUTPUT_DIR="$SCRIPT_DIR/Output"

if ! command -v git >/dev/null 2>&1; then
    echo "Ошибка: для первой установки Marker требуется git." >&2
    exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
    echo "Ошибка: для установки Marker требуется Python 3.10 или новее." >&2
    exit 1
fi
mkdir -p "$PDF_DIR" "$OUTPUT_DIR"
shopt -s nullglob
pdf_files=("$PDF_DIR"/*.[pP][dD][fF])
if [ ${#pdf_files[@]} -eq 0 ]; then
    echo "В $PDF_DIR нет PDF-файлов."
    exit 0
fi

pending=()
for pdf in "${pdf_files[@]}"; do
    base="$(basename "$pdf")"
    name="${base%.*}"
    if [ -f "$OUTPUT_DIR/$name/$name.md" ] && [ "${FORCE:-0}" != "1" ]; then
        echo "Пропуск: $base уже сконвертирован (для пересборки: FORCE=1)."
    else
        pending+=("$pdf")
    fi
done
if [ ${#pending[@]} -eq 0 ]; then
    echo "Новых PDF для обработки нет."
    exit 0
fi

# Ключ остаётся только в памяти процесса и не попадает в аргументы команды Marker.
# При запуске из Finder показываем системное окно; в Терминале можно заранее
# задать OLLAMA_API_KEY, тогда окно не появится.
api_key="${OLLAMA_API_KEY:-}"
unset OLLAMA_API_KEY
if [ -z "$api_key" ]; then
    if command -v osascript >/dev/null 2>&1; then
        if ! api_key="$(osascript <<'APPLESCRIPT'
set dialog_result to display dialog "Введите API-ключ Ollama для облачной модели gemma4:31b" default answer "" with hidden answer buttons {"Отмена", "Продолжить"} default button "Продолжить" with title "Ollama API"
return text returned of dialog_result
APPLESCRIPT
)"; then
            echo "Ввод API-ключа отменён." >&2
            exit 1
        fi
    elif [ -t 0 ]; then
        IFS= read -r -s -p "Ollama API key: " api_key
        printf '\n'
    else
        echo "Ошибка: задайте OLLAMA_API_KEY в окружении." >&2
        exit 1
    fi
fi
if [ -z "$api_key" ]; then
    echo "Ошибка: API-ключ Ollama не введён." >&2
    exit 1
fi

if ! OPENAI_API_KEY="$api_key" python3 - "$OLLAMA_BASE_URL/models/$OLLAMA_MODEL" <<'PY'
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

request = Request(sys.argv[1], headers={"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"]})
try:
    with urlopen(request, timeout=30):
        pass
except HTTPError as error:
    print(f"Ошибка Ollama API: HTTP {error.code}. Проверьте ключ и доступ к модели.", file=sys.stderr)
    sys.exit(1)
except URLError:
    print("Ошибка: не удалось подключиться к облачному Ollama API.", file=sys.stderr)
    sys.exit(1)
PY
then
    exit 1
fi

# Скачиваем форк только при первом запуске. Автоматического git pull нет:
# последующие конвертации используют ровно ту же установленную версию.
if [ ! -d "$MARKER_ROOT/.git" ]; then
    if [ -e "$MARKER_ROOT" ]; then
        echo "Ошибка: $MARKER_ROOT существует, но это не Git-репозиторий." >&2
        exit 1
    fi
    mkdir -p "$MARKER_CACHE" || exit 1
    clone_dir="$(mktemp -d "$MARKER_CACHE/source.XXXXXX")" || exit 1
    echo "Один раз скачиваю Marker из $MARKER_REPO..."
    if ! git clone --depth 1 "$MARKER_REPO" "$clone_dir"; then
        rm -rf "$clone_dir"
        echo "Ошибка: не удалось скачать Marker. Проверьте доступ к GitHub." >&2
        exit 1
    fi
    if ! mv "$clone_dir" "$MARKER_ROOT"; then
        rm -rf "$clone_dir"
        echo "Ошибка: не удалось сохранить скачанный Marker." >&2
        exit 1
    fi
fi

repo_origin="$(git -C "$MARKER_ROOT" remote get-url origin 2>/dev/null || true)"
if [ "$repo_origin" != "$MARKER_REPO" ]; then
    echo "Ошибка: кэш $MARKER_ROOT принадлежит другому репозиторию: $repo_origin" >&2
    exit 1
fi
if ! grep -Fq 'os.environ.get("OPENAI_API_KEY")' "$MARKER_ROOT/marker/services/openai.py"; then
    if [ -n "$(git -C "$MARKER_ROOT" status --porcelain)" ]; then
        echo "Ошибка: в кэше Marker есть изменения; обновите его вручную: $MARKER_ROOT" >&2
        exit 1
    fi
    echo "Однократно обновляю ранее установленный Marker для облачного Ollama API..."
    if ! git -C "$MARKER_ROOT" fetch --depth 1 origin master || \
       ! git -C "$MARKER_ROOT" checkout --detach FETCH_HEAD; then
        echo "Ошибка: не удалось обновить кэш Marker." >&2
        exit 1
    fi
fi
if ! grep -q 'page_batch_size' "$MARKER_ROOT/marker/converters/pdf.py" || \
   ! grep -q 'data-bbox' "$MARKER_ROOT/marker/processors/llm/llm_table.py"; then
    echo "Ошибка: скачанная версия Marker не содержит нужных доработок." >&2
    echo "Кэш: $MARKER_ROOT. Репозиторий: $MARKER_REPO" >&2
    exit 1
fi

repo_revision="$(git -C "$MARKER_ROOT" rev-parse HEAD)" || exit 1
installed_revision="$(cat "$MARKER_CACHE/installed-revision" 2>/dev/null || true)"
if [ ! -x "$MARKER_VENV/bin/marker_single" ] || [ "$installed_revision" != "$repo_revision" ]; then
    echo "Один раз устанавливаю Marker и зависимости в $MARKER_VENV..."
    if [ ! -x "$MARKER_VENV/bin/python" ]; then
        python3 -m venv "$MARKER_VENV" || exit 1
    fi
    if ! "$MARKER_VENV/bin/python" -m pip install --editable "$MARKER_ROOT"; then
        echo "Ошибка: установка Marker не завершилась. При следующем запуске она повторится." >&2
        exit 1
    fi
    printf '%s\n' "$repo_revision" > "$MARKER_CACHE/installed-revision" || exit 1
fi
MARKER_BIN="$MARKER_VENV/bin/marker_single"

WORK_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/marker-ollama.XXXXXX")" || exit 1
cleanup() {
    unset api_key
    rm -rf "$WORK_ROOT"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# Используем команду Marker из собственного окружения, а не системную версию.
export PYTHONPATH="$MARKER_ROOT"
echo "Marker: $MARKER_ROOT ($repo_revision)"
echo "LLM: облачный Ollama API, модель $OLLAMA_MODEL."
echo "Пакет страниц: $PAGE_BATCH_SIZE; на каждый PDF один запуск Marker."

failed=0
for pdf in "${pending[@]}"; do
    base="$(basename "$pdf")"
    name="${base%.*}"
    note_dir="$OUTPUT_DIR/$name"
    run_dir="$WORK_ROOT/run"
    rm -rf "$run_dir"
    mkdir -p "$run_dir"

    args=(
        --output_dir "$run_dir"
        --output_format markdown
        --use_llm
        --llm_service marker.services.openai.OpenAIService
        --openai_base_url "$OLLAMA_BASE_URL"
        --openai_model "$OLLAMA_MODEL"
        --openai_image_format png
        --page_batch_size "$PAGE_BATCH_SIZE"
        --max_concurrency 1
        --timeout 180
    )
    if [ "$REDO_INLINE_MATH" = "1" ]; then args+=(--redo_inline_math); fi
    if [ -n "$MODE" ]; then args+=(--mode "$MODE"); fi
    if [ "$FORCE_OCR" = "1" ]; then args+=(--force_ocr); fi

    echo "--------------------------------------------------"
    echo "Конвертирую: $base"
    if ! OPENAI_API_KEY="$api_key" "$MARKER_BIN" "$pdf" "${args[@]}"; then
        echo "Ошибка Marker для $base. Исходный PDF не затронут." >&2
        failed=$((failed + 1))
        continue
    fi

    generated_dir="$run_dir/$name"
    generated_md="$generated_dir/$name.md"
    if [ ! -f "$generated_md" ]; then
        echo "Ошибка: Marker не создал $generated_md" >&2
        failed=$((failed + 1))
        continue
    fi

    # Публикуем результат только после успешной конвертации всего PDF.
    # Старые файлы при FORCE сохраняются, пока новый Markdown не готов.
    if ! mkdir -p "$note_dir"; then
        echo "Ошибка: не удалось создать $note_dir" >&2
        failed=$((failed + 1))
        continue
    fi
    assets_ok=1
    for asset in "$generated_dir"/*; do
        [ -f "$asset" ] || continue
        case "$asset" in
            *.md|*.json) ;;
            *)
                if ! mv -f "$asset" "$note_dir/"; then
                    assets_ok=0
                    break
                fi
                ;;
        esac
    done
    if [ "$assets_ok" != "1" ] || ! mv -f "$generated_md" "$note_dir/$name.md"; then
        echo "Ошибка: не удалось сохранить результат $base" >&2
        failed=$((failed + 1))
        continue
    fi
    echo "Готово: $note_dir/$name.md"
done

echo "--------------------------------------------------"
if [ "$failed" -gt 0 ]; then
    echo "Завершено с ошибками: $failed PDF. Успешные результаты сохранены." >&2
    exit 1
fi
echo "Все PDF обработаны."
