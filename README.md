# Marker: PDF → Markdown и таблицы в JSON

Форк [EyesHead/marker](https://github.com/EyesHead/marker/tree/codex/my-change) для конвертации русскоязычных PDF, включая СП и ГОСТ. Текст сохраняется в Markdown, таблицы — в HTML внутри Markdown и отдельном JSON с координатами, объединёнными ячейками, формулами и изображениями.

Основной вариант — **Ollama Cloud + Gemma 4 31B**. Gemma работает в облаке; Marker и OCR работают на вашем компьютере. Установка локальной Gemma не требуется.

## Что нужно

- Python 3.10 или новее, Git и доступ к интернету.
- Аккаунт Ollama и [API-ключ](https://ollama.com/settings/keys). Доступ к модели зависит от лимитов аккаунта.
- PDF в папке `PDF` рядом со скриптом.

Рабочая ветка с этими доработками: `codex/my-change`.

## 1. Основной запуск на macOS: все PDF из папки

Расположение папок:

```text
PolytechBrain/
  ScriptMacOS-Ollama.sh
  PDF/
    document.pdf
  Output/
```

Для первого получения скрипта:

```bash
cd "$HOME/BRAIN_University/PolytechBrain"
curl -fL https://raw.githubusercontent.com/EyesHead/marker/refs/heads/codex/my-change/ScriptMacOS-Ollama.sh -o ScriptMacOS-Ollama.sh
chmod +x ScriptMacOS-Ollama.sh
```

Запуск из этой же папки:

```bash
./ScriptMacOS-Ollama.sh
```

В начале появится окно для API-ключа Ollama. Ключ не сохраняется в файл. Если в окружении уже задан `OLLAMA_API_KEY`, окно пропускается.

Скрипт один раз скачивает форк и устанавливает зависимости в `~/.cache/eyeshead-marker`. При переходе с прежней версии выполняется однократное обновление. Обычные повторные запуски используют установленную копию и пропускают PDF, для которых уже есть Markdown.

## 2. Повторная обработка готовых PDF

```bash
cd "$HOME/BRAIN_University/PolytechBrain"
FORCE=1 ./ScriptMacOS-Ollama.sh
```

Это нужно, например, чтобы получить JSON таблиц для PDF, сконвертированных старым скриптом.

## 3. Один PDF через Marker CLI и Ollama Cloud

Один раз установите эту ветку в отдельное Python-окружение:

```bash
git clone --branch codex/my-change https://github.com/EyesHead/marker.git
cd marker
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --editable .
```

Введите ключ скрыто; переменная `OPENAI_API_KEY` здесь содержит **ключ Ollama** для совместимого API:

```bash
export OPENAI_API_KEY="$(python -c 'import getpass; print(getpass.getpass("Ollama API key: "))')"
```

Замените `document.pdf` на имя вашего файла:

```bash
marker_single "$HOME/BRAIN_University/PolytechBrain/PDF/document.pdf" \
  --output_dir "$HOME/BRAIN_University/PolytechBrain/Output" \
  --output_format markdown \
  --use_llm \
  --llm_service marker.services.openai.OpenAIService \
  --openai_base_url https://ollama.com/v1 \
  --openai_model gemma4:31b \
  --openai_image_format png \
  --table_json_reconstruction \
  --redo_inline_math \
  --max_concurrency 1 \
  --max_output_tokens 32768 \
  --timeout 180
```

Для прямого облачного API используется имя `gemma4:31b`; суффикс `-cloud` не требуется. [Документация Ollama](https://docs.ollama.com/api/openai-compatibility).

## 4. Сканы или PDF с повреждённым текстовым слоем

Для независимого OCR с координатами таблиц установите Tesseract с русским и английским языками:

```bash
brew install tesseract tesseract-lang
```

Принудительно распознать PDF заново через скрипт:

```bash
cd "$HOME/BRAIN_University/PolytechBrain"
FORCE_OCR=1 FORCE=1 ./ScriptMacOS-Ollama.sh
```

При запуске через CLI добавьте `--force_ocr` к команде из сценария 3. Для обычного PDF с корректным текстовым слоем этот флаг не нужен.

## Результат

Для `document.pdf` скрипт сохраняет:

```text
Output/document/
  document.md
  document_tables.json
  изображения ячеек и рисунков
```

В `document_tables.json`:

- `reconstruction.tables` — принятые таблицы: сетка, роли ячеек, spans, исходный текст, LaTeX, рисунки и привязка к блокам.
- `sources` — координаты исходных фрагментов и необязательные линии PDF.
- `validation` — отчёты со статусами `structurally_valid`, `needs_review` или `rejected`. При отклонении сохраняется доступный ответ/кандидат для разбора.

## Как проверяются таблицы

Marker сначала извлекает текст и геометрию из PDF или координатного OCR. Gemma получает изображения таблиц вместе с этими данными и возвращает JSON. Код проверяет схему, покрытие сетки, пересечения объединённых ячеек, ссылки на блоки, координаты строк и колонок, числовую запись и парность разделителей формул.

Продолжения таблиц сверяются по общим исходным блокам. HTML и изображения ячеек создаются кодом после проверки. Если JSON отклонён или требует проверки, прежняя таблица в Markdown сохраняется, а результат попадает в отчёт.

`structurally_valid` означает успешную проверку структуры и привязок; он не гарантирует правильность каждого инженерного символа. Полный прогон Gemma на контрольном СП пока не выполнен.

Ollama Cloud [сейчас не поддерживает принудительные structured outputs](https://docs.ollama.com/capabilities/structured-outputs). Поэтому схема передаётся в промпте, температура равна 0, а валидация выполняется локально с ограниченными повторными попытками.

[Промпт](marker/tables/russian_normative.md) · [JSON Schema](marker/tables/schema.json) · [Модели данных](marker/tables/schema.py)

Лицензия: [Apache 2.0](LICENSE).
