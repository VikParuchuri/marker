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
MARKER_BASE_SHA="e7c67f1d239ea6a805cbf4ed6c6b2056d435e22d"
MARKER_CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/eyeshead-marker"
MARKER_ROOT="$MARKER_CACHE/source"
MARKER_VENV="$MARKER_CACHE/venv"
OLLAMA_MODEL="gemma4:31b"
OLLAMA_BASE_URL="http://127.0.0.1:11434"
PAGE_BATCH_SIZE=30
REDO_INLINE_MATH=1
MODE=""                         # "", "fast" или "balanced"
FORCE_OCR=0                     # 1 — распознавать заново все страницы

apply_bundled_patch() {
    python3 -c 'import base64, gzip, sys; sys.stdout.buffer.write(gzip.decompress(base64.b64decode(sys.stdin.buffer.read())))' <<'EYESHEAD_PATCH_GZIP_BASE64' | git -C "$MARKER_ROOT" apply -
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
Zb+F155YdV3gwf8DMV/IhdRrAAA=
EYESHEAD_PATCH_GZIP_BASE64
}

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
    cached_revision="$(git -C "$MARKER_ROOT" rev-parse HEAD)" || exit 1
    if [ "$cached_revision" != "$MARKER_BASE_SHA" ]; then
        echo "Ошибка: в репозитории нет нужных доработок, а версия изменилась." >&2
        echo "Обновите скрипт или опубликуйте доработки в $MARKER_REPO" >&2
        exit 1
    fi
    echo "Применяю встроенные доработки таблиц и обработки по 30 страниц..."
    if ! apply_bundled_patch; then
        echo "Ошибка: не удалось применить доработки к скачанному Marker." >&2
        exit 1
    fi
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
