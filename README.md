# Микросервисный проект: Загрузка, хранение и анализ файлов

Этот проект реализует систему микросервисов для загрузки, хранения и анализа текстовых файлов. Он состоит из API Шлюза (API Gateway), Сервиса Хранения Файлов (FSS) и Сервиса Анализа Файлов (FAS).

## Структура проекта

```
.
├── api_gateway/            # API Шлюз на FastAPI
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .env.example        # Переменные окружения для API Шлюза (скопировать в .env)
│   ├── main.py
│   ├── config.py
│   ├── http_client.py
│   └── logging_config.py
├── file_analysis_service/  # Сервис Анализа Файлов на FastAPI
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .env.example        # Переменные окружения для FAS (скопировать в .env)
│   ├── main.py
│   ├── routers/
│   ├── crud.py
│   ├── models.py
│   ├── schemas.py
│   ├── database.py
│   ├── config.py
│   └── logging_config.py
├── files_storing_service/  # Сервис Хранения Файлов на FastAPI
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .env.example        # Переменные окружения для FSS (скопировать в .env)
│   ├── main.py
│   ├── routers/
│   ├── crud.py
│   ├── models.py
│   ├── schemas.py
│   ├── database.py
│   ├── config.py
│   └── logging_config.py
├── filestorage_fss/        # Том (volume) для хранения файлов FSS (создается автоматически Docker)
├── wordclouds_fas/         # Том (volume) для сгенерированных FAS облаков слов (создается автоматически Docker)
├── docker-compose.yml        # Конфигурация Docker Compose
├── init-db.sh                # Скрипт инициализации PostgreSQL (убедитесь, что он исполняемый: chmod +x init-db.sh)
└── README.md                 # Этот файл
```

## Сервисы

### 1. API Шлюз (`api_gateway`)
- **Назначение**: Единая точка входа для всех клиентских запросов. Маршрутизирует запросы к соответствующим нижестоящим сервисам (FSS, FAS).
- **Порт (проброшен на хост)**: `8000` (настраивается через `API_GATEWAY_PORT` в его `.env` файле)
- **Ключевые эндпоинты**:
    - `POST /api/v1/files/upload`: Загрузить файл.
    - `GET /api/v1/analysis/file/{original_file_id}`: Получить результаты всех анализов для указанного `original_file_id`.
    - `GET /api/v1/files/{file_id}/download`: Скачать исходный файл (используется `file_id` из ответа на загрузку).
    - `GET /api/v1/analysis/wordclouds/{analysis_id}/{image_filename}`: Скачать изображение облака слов для конкретного анализа (используются `analysis_id` и `image_filename` из ответа на запрос статуса анализа).

### 2. Сервис Хранения Файлов (`files_storing_service`)
- **Назначение**: Хранит загруженные файлы и их метаданные. Уведомляет FAS о загрузке новых файлов.
- **Внутренний порт (в сети Docker)**: `8000` (настраивается через `FSS_PORT` в его `.env` файле)
- **База данных**: PostgreSQL (подключение через `DATABASE_URL`, указанный в его `.env` файле)
- **Хранилище файлов**: Использует том Docker, смонтированный в `./filestorage_fss/` на хосте. Этот путь внутри контейнера — `/app/filestorage_fss`.

### 3. Сервис Анализа Файлов (`file_analysis_service`)
- **Назначение**: Выполняет анализ текстовых файлов. В настоящее время генерирует текстовую статистику (количество слов, абзацев и т.д.) и изображение облака слов с использованием внешнего API (`https://quickchart.io/wordcloud`).
- **Внутренний порт (в сети Docker)**: `8000` (настраивается через `FAS_PORT` в его `.env` файле)
- **База данных**: PostgreSQL (подключение через `DATABASE_URL`, указанный в его `.env` файле)
- **Хранилище облаков слов**: Использует том Docker, смонтированный в `./wordclouds_fas/` на хосте. Этот путь внутри контейнера — `/app/wordclouds_fas`.

## Настройка и Запуск

### Необходимые условия
- Docker
- Docker Compose

### 1. Конфигурация окружения

**Конфигурация окружения для каждого сервиса (файлы `.env`)**

Каждому сервису (`api_gateway`, `files_storing_service`, `file_analysis_service`) требуется собственный файл `.env`. Создайте их, скопировав соответствующий файл `.env.example` из директории каждого сервиса.

Например, для Сервиса Хранения Файлов:
```bash
cp files_storing_service/.env.example files_storing_service/.env
```
Сделайте то же самое для `file_analysis_service` и `api_gateway`:
```bash
cp file_analysis_service/.env.example file_analysis_service/.env
cp api_gateway/.env.example api_gateway/.env
```
Предоставленные файлы `.env.example` предварительно настроены для работы с Docker Compose, включая подключения к базе данных с использованием `appuser:apppassword@postgres_db:5432/...`.
Файл `docker-compose.yml` сам устанавливает `POSTGRES_USER` в `appuser` и `POSTGRES_PASSWORD` в `apppassword` для сервиса базы данных. Никаких дальнейших ручных изменений в файлах `.env` для стандартной настройки не требуется.

### 2. Убедитесь, что `init-db.sh` является исполняемым
Если вы только что склонировали репозиторий, убедитесь, что скрипт инициализации базы данных является исполняемым:
```bash
chmod +x init-db.sh
```

### 3. Сборка и запуск с помощью Docker Compose

Из корневой директории проекта:
```bash
docker compose up --build -d
```
Эта команда:
- Соберет Docker-образы для каждого сервиса.
- Запустит все сервисы, включая базу данных PostgreSQL (которая будет использовать `appuser`/`apppassword`).
- Скрипт `init-db.sh` автоматически создаст базы данных `fss_db` и `fas_db` в PostgreSQL.

### 4. Проверка статуса сервисов
```bash
docker compose ps
```
Все сервисы должны быть в состоянии `Up` или `Healthy`.

### 5. Тестирование (примеры с `curl`)

**a. Загрузка файла:**
Создайте тестовый текстовый файл, например, `my_test_file.txt`:
```
Hello world. This is a test.
Test, test, test. Hello microservices.
```
Загрузите его:
```bash
curl -X POST -F "file=@my_test_file.txt" http://localhost:8000/api/v1/files/upload
```
Эта команда вернет JSON с метаданными файла, включая его `id` (это `original_file_id` для последующих запросов на анализ, а также `file_id` для скачивания исходного файла). Запомните этот ID.

**b. Получение статуса анализа:**
Замените `{original_file_id}` на ID (значение поля `id` из ответа на загрузку), полученный на шаге загрузки.
```bash
curl http://localhost:8000/api/v1/analysis/file/{original_file_id}
```
Эта команда вернет массив результатов анализа. Каждый элемент будет содержать статус анализа, `analysis_id`, `word_cloud_image_url` (если доступно) и другую информацию. Анализ может занять несколько секунд. Для скачивания облака слов вам понадобятся `analysis_id` и имя файла из `word_cloud_image_url`.

**c. Скачивание облака слов:**
Предположим, из предыдущего шага вы получили `analysis_id` равный `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` и `word_cloud_image_url` указывающий на файл `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx_my_test_file_wordcloud.png`.
```bash
curl -o wordcloud.png http://localhost:8000/api/v1/analysis/wordclouds/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx_my_test_file_wordcloud.png
```

**d. Скачивание исходного файла:**
Замените `{file_id}` на ID, полученный на шаге загрузки.
```bash
curl -o downloaded_original.txt http://localhost:8000/api/v1/files/{file_id}/download
```

### 6. Тестирование и Покрытие Кода

Все сервисы имеют наборы тестов (pytest), которые можно запускать внутри соответствующих Docker-контейнеров.

Для запуска тестов и получения отчета о покрытии для каждого сервиса:

**API Gateway:**
```bash
docker compose exec api_gateway pytest --cov=.
```

**File Storing Service (FSS):**
```bash
docker compose exec files_storing_service pytest --cov=.
```

**File Analysis Service (FAS):**
```bash
docker compose exec file_analysis_service pytest --cov=.
```

**Общее покрытие кода по проекту (рассчитано вручную на основе покрытия каждого сервиса): 83.41%**
- API Gateway: 99.24%
- File Storing Service (FSS): 79.88%
- File Analysis Service (FAS - только код приложения): 73.72%

### 7. Просмотр логов
```bash
docker compose logs api_gateway
docker compose logs files_storing_service
docker compose logs file_analysis_service
docker compose logs postgres_db
```
Для просмотра логов в реальном времени добавьте флаг `-f` (например, `docker compose logs -f api_gateway`).

### 8. Остановка сервисов
```bash
docker compose down
```
Для удаления томов (volumes), включая данные базы данных, сохраненные файлы в `filestorage_fss/` и сгенерированные изображения в `wordclouds_fas/`:
```bash
docker compose down -v
```