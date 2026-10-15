# Kvitto Billing Service

API оплаты курсов: тарифы, платежи, промокод, рассрочка и уведомления банка.
Python 3.11, FastAPI, Pydantic v2, асинхронный SQLAlchemy 2.0, SQLite, Alembic.
Все суммы в API и БД — целые числа в копейках.

## Настройки окружения

Перед первым запуском создайте `.env` из примера (если файл уже существует,
сохраните свои настройки):

```sh
cp .env.example .env
```

В PowerShell: `Copy-Item .env.example .env`.

`.env.example` — только шаблон: `your_database_url` нужно вручную заменить
в созданном `.env` на рабочий URL базы данных до запуска приложения или Docker.
Для SQLite можно указать:

```dotenv
DATABASE_URL=sqlite+aiosqlite:///./payments.db
```

`DATABASE_URL` — единый URL для приложения и Alembic при локальном запуске
и в Docker.
Compose читает его из корневого `.env` и передаёт контейнеру как `DATABASE_URL`.

Локально относительный путь ведёт в корень проекта, а в контейнере — в рабочую
папку `/data`, подключённую к тому `payments`. Поэтому настройки одинаковые,
но базы раздельные и данные Docker сохраняются после пересоздания контейнера.
При изменении SQLite URL сохраняйте относительный путь к файлу в рабочей папке
контейнера либо указывайте абсолютный путь внутри `/data` для Docker.

Переменные окружения терминала имеют приоритет над `.env`. Локальная и Docker-базы
раздельные. `.env` исключён из Git и контекста Docker; `.env.example` хранится
в репозитории без секретов. После изменения URL пересоздайте контейнер командой
`docker compose up -d`.

## Запуск

### Docker

```sh
docker compose up --build
```

Нужен Docker Desktop или Docker Engine. Сервис доступен на порту 8000,
Swagger — http://localhost:8000/docs. Миграции выполняются перед запуском сервера,
SQLite хранится в именованном томе `payments`. Остановка с сохранением данных:
`docker compose down`.

### Локально

Установите Git и Python 3.11. Клонируйте репозиторий и перейдите в его папку:

```sh
git clone https://github.com/Igor-Baryshnikov/kvitto_test.git
cd kvitto_test
```

Установите Poetry, если он ещё не установлен:

```sh
python3.11 -m pip install --user poetry
poetry --version
```

В Windows для установки можно использовать `py -3.11 -m pip install --user poetry`.
Если команда `poetry` не находится, добавьте каталог пользовательских скриптов
Python в PATH и откройте новый терминал.

Создайте `.env` по инструкции выше. Далее выполняйте команды из корня проекта:

```sh
poetry env use python3.11
poetry install --no-root
poetry run python -m alembic -c billing_service/alembic.ini upgrade head
poetry run python -m uvicorn app.main:app --app-dir billing_service --reload
```

На Windows вместо `python3.11` в `poetry env use` можно указать `3.11`
или полный путь к Python 3.11.

Миграции нужны при первом запуске и после обновления; при обычном повторном
запуске достаточно команды Uvicorn. Остановка — Ctrl+C.

`DATABASE_URL` задаётся через окружение или корневой `.env` (окружение имеет
приоритет). По умолчанию: `sqlite+aiosqlite:///./payments.db`. Приложение и Alembic
используют один URL.

При старте пустая таблица тарифов заполняется: basic — 990000, standard — 1990000,
premium — 2990000 копеек. Непустая таблица не меняется. Схема создаётся только
миграциями.

## Тесты и линтеры

```sh
poetry run pytest
poetry run black --check billing_service tests
poetry run isort --check-only billing_service tests
poetry run mypy billing_service tests
```

## Примеры API

Примеры для bash. В PowerShell используйте `curl.exe` и передавайте JSON из файла
(`--data-binary @request.json`), либо работайте через Swagger UI на `/docs`.
Маршруты без префикса: `GET /tariffs`, `POST /payments`, `GET /payments`,
`GET /payments/{id}`, `POST /webhooks/bank`.

### Тарифы

```sh
curl http://localhost:8000/tariffs
```

200 — список `id`, `title`, `price`.

### Создание платежа

```sh
curl -i -X POST http://localhost:8000/payments \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: order-001' \
  -d '{"tariff_id":2,"email":"Student@example.com","method":"installment","installment_months":3,"promo_code":"kvitto10"}'
```

Первый запрос возвращает 201. Для standard с промокодом: `amount=1791000`,
`discount=199000`, `schedule=[597000,597000,597000]`, статус `pending`.
Без промокода график на три месяца: `[663334,663333,663333]`.

Ответ платежа: `id`, `status`, `tariff_id`, `amount`, `discount`, `method`,
`installment_months`, `schedule`, `email`, `created_at`.

### Получение платежа

```sh
curl http://localhost:8000/payments/1
```

200 — платёж, 404 — платёж не найден.

### Список платежей

```sh
curl 'http://localhost:8000/payments?email=student@example.com&status=pending'
```

Фильтры `email` и `status` необязательны и комбинируются. Порядок — по `id` по
убыванию. Пустой результат — 200 и `[]`. Неизвестный статус — 422.

### Уведомление банка

Замените `1` на ID созданного платежа.

```sh
curl -i -X POST http://localhost:8000/webhooks/bank \
  -H 'Content-Type: application/json' \
  -d '{"payment_id":1,"status":"succeeded"}'
```

Успех — 200 `{"result":"ok"}`.

## Правила

- Методы оплаты: `card`, `sbp`, `installment`. Рассрочка требует срок 3, 6 или 12
  месяцев. Для card и sbp срок нужно опустить или передать `null`, график равен `null`.
- Промокод необязателен; `KVITTO10` даёт 10%, регистр не важен. Неизвестный код — 422.
- Повтор того же `Idempotency-Key` возвращает существующий платёж с кодом 200, даже
  если тело запроса отличается. Без заголовка каждый запрос создаёт новый платёж.
  Ключ — до 255 символов. Конфликт параллельных запросов обрабатывается через
  unique-ограничение в БД и rollback.
- Разрешены переходы `pending → succeeded`, `pending → failed`, `succeeded → refunded`.
  Вебхук сначала проверяет наличие платежа (404), затем переход
  (409 `{"error":"invalid_transition"}`). При 409 статус не меняется; повтор
  уведомления с тем же статусом тоже 409.
- Неверные входные данные и неизвестные значения Enum — стандартный ответ 422.
- Подпись вебхука из бонусов ТЗ не реализована.

## Допущения

- `amount` — сумма после скидки, `discount` — размер скидки.
- Несуществующий `tariff_id` возвращает 404.
- `installment_months` при card или sbp возвращает 422.
- Email при сохранении и поиске приводится к нижнему регистру.

## Структура

- `main.py` создаёт приложение, подключает роутер и обработчики ошибок.
- Роутер вызывает `BillingService` и преобразует ORM-объекты в схемы через
  `model_validate`; операции с БД выполняет `BillingRepository`.
- Расчёты цены, графика и проверка переходов — чистые функции в `services/billing.py`.
- API-тесты в `tests/test_billing.py` (pytest, AnyIO, httpx) проверяют суммы,
  график, повторные ключи, переходы статусов, фильтры и валидацию.
  Фикстуры находятся в `tests/conftest.py`. Используется SQLite in-memory;
  рабочая БД не затрагивается.
