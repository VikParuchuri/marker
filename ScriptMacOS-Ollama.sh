#!/usr/bin/env bash
# PDF -> Markdown через Marker из EyesHead/marker и локальную Ollama.
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
OLLAMA_BASE_URL="http://127.0.0.1:11434"
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
if ! command -v curl >/dev/null 2>&1; then
    echo "Ошибка: требуется curl для запуска локальной модели Ollama." >&2
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

OLLAMA_BIN="$(command -v ollama 2>/dev/null || true)"
if [ -z "$OLLAMA_BIN" ] && [ -x /Applications/Ollama.app/Contents/Resources/ollama ]; then
    OLLAMA_BIN=/Applications/Ollama.app/Contents/Resources/ollama
fi
if [ -z "$OLLAMA_BIN" ] && [ -x "$HOME/Applications/Ollama.app/Contents/Resources/ollama" ]; then
    OLLAMA_BIN="$HOME/Applications/Ollama.app/Contents/Resources/ollama"
fi
if [ -z "$OLLAMA_BIN" ]; then
    echo "Ошибка: Ollama не установлен или команда ollama недоступна." >&2
    echo "Установите Ollama для macOS: https://ollama.com/download/mac" >&2
    exit 1
fi

WORK_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/marker-ollama.XXXXXX")" || exit 1
OLLAMA_PID=""
UNLOAD_MODEL=0
cleanup() {
    if [ "$UNLOAD_MODEL" = "1" ]; then
        curl -fsS --max-time 10 -H 'Content-Type: application/json' \
            --data "{\"model\":\"$OLLAMA_MODEL\",\"keep_alive\":0}" \
            "$OLLAMA_BASE_URL/api/generate" >/dev/null 2>&1 || true
    fi
    if [ -n "$OLLAMA_PID" ]; then
        # Останавливаем только тот сервер Ollama, который запустил этот скрипт.
        kill "$OLLAMA_PID" 2>/dev/null || true
        wait "$OLLAMA_PID" 2>/dev/null || true
    fi
    rm -rf "$WORK_ROOT"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

export OLLAMA_HOST=127.0.0.1:11434
if ! curl -fsS --max-time 2 "$OLLAMA_BASE_URL/api/version" >/dev/null 2>&1; then
    echo "Запускаю локальный сервер Ollama..."
    "$OLLAMA_BIN" serve >"$WORK_ROOT/ollama.log" 2>&1 &
    OLLAMA_PID=$!
    ready=0
    for ((i=0; i<60; i++)); do
        if curl -fsS --max-time 2 "$OLLAMA_BASE_URL/api/version" >/dev/null 2>&1; then
            ready=1
            break
        fi
        if ! kill -0 "$OLLAMA_PID" 2>/dev/null; then break; fi
        sleep 1
    done
    if [ "$ready" != "1" ]; then
        echo "Ошибка: сервер Ollama не запустился. Журнал:" >&2
        cat "$WORK_ROOT/ollama.log" >&2
        exit 1
    fi
else
    echo "Использую уже работающий локальный сервер Ollama."
fi

if ! "$OLLAMA_BIN" show "$OLLAMA_MODEL" >/dev/null 2>&1; then
    echo "Модель $OLLAMA_MODEL ещё не загружена. Скачиваю её через Ollama..."
    if ! "$OLLAMA_BIN" pull "$OLLAMA_MODEL"; then
        echo "Ошибка: не удалось загрузить модель $OLLAMA_MODEL." >&2
        exit 1
    fi
fi

# Не выгружаем модель, если она уже работала до запуска скрипта.
if ! "$OLLAMA_BIN" ps 2>/dev/null | awk -v model="$OLLAMA_MODEL" \
    'NR > 1 && $1 == model { found = 1 } END { exit !found }'; then
    UNLOAD_MODEL=1
fi

echo "Загружаю $OLLAMA_MODEL в память компьютера..."
if ! curl -fsS --max-time 900 -H 'Content-Type: application/json' \
    --data "{\"model\":\"$OLLAMA_MODEL\",\"keep_alive\":-1}" \
    "$OLLAMA_BASE_URL/api/generate" >"$WORK_ROOT/preload.json"; then
    echo "Ошибка: Ollama не смог загрузить модель $OLLAMA_MODEL." >&2
    exit 1
fi

# Используем команду Marker из собственного окружения, а не системную версию.
export PYTHONPATH="$MARKER_ROOT"
echo "Marker: $MARKER_ROOT ($repo_revision)"
echo "LLM: локальная Ollama $OLLAMA_MODEL; API-ключ не требуется."
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
        --llm_service marker.services.ollama.OllamaService
        --ollama_base_url "$OLLAMA_BASE_URL"
        --ollama_model "$OLLAMA_MODEL"
        --page_batch_size "$PAGE_BATCH_SIZE"
        --max_concurrency 1
    )
    if [ "$REDO_INLINE_MATH" = "1" ]; then args+=(--redo_inline_math); fi
    if [ -n "$MODE" ]; then args+=(--mode "$MODE"); fi
    if [ "$FORCE_OCR" = "1" ]; then args+=(--force_ocr); fi

    echo "--------------------------------------------------"
    echo "Конвертирую: $base"
    if ! "$MARKER_BIN" "$pdf" "${args[@]}"; then
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
