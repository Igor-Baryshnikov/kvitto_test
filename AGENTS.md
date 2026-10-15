# Приоритет
1. Требования из TZ.md важнее всего остального.
2. Раздел «Архитектура» важнее раздела «Общие правила» при конфликте.
3. Вопросы, которые не описаны в TZ.md, решаются по разделу «Допущения».

# Архитектура
Структура репозитория:

```
.
├── .dockerignore
├── .gitignore
├── AGENTS.md
├── AI_LOG.md
├── Dockerfile
├── README.md
├── TZ.md
├── docker-compose.yml
├── poetry.lock
├── pyproject.toml
├── tests/                      # API-тесты и фикстуры
└── billing_service/
    ├── alembic.ini
    ├── migrations/             # миграции Alembic
    └── app/
        ├── main.py             # FastAPI app, lifespan, роутер, обработчики ошибок
        ├── api/routers/billing.py
        ├── core/               # БД, зависимости, Enum, исключения
        ├── models/billing.py
        ├── repositories/billing.py
        ├── schemas/billing.py
        └── services/billing.py # BillingService, чистые функции, словарь переходов
```

Правила слоёв:
- Все импорты приложения абсолютные, от `app`. Запуск из корня: `poetry run python -m uvicorn app.main:app --app-dir billing_service`.
- main.py: только создание приложения, lifespan, подключение роутера и обработчиков исключений. Lifespan вызывает `BillingService.seed_tariffs`.
- Роутеры тонкие: разбор запроса, вызов сервиса, явное преобразование ORM-объектов в схемы через model_validate и формирование ответа. Возвращаемые типы — схемы ответа. Без бизнес-логики и без SQL. Сервис возвращает ORM-объекты, не импортирует схемы ответа и HTTPException.
- BillingService: бизнес-логика и оркестрация. BillingRepository: только SQLAlchemy-операции.
- Расчёт цены и графика, проверка переходов — отдельные чистые функции в services/billing.py. Они не обращаются к БД и FastAPI. Словарь допустимых переходов — константа модуля. Отдельные модули выделяются только при росте логики или повторном использовании.
- Исключения только из core/exceptions.py (`PaymentNotFoundError`, `TariffNotFoundError`, `InvalidTransitionError`, `UnknownPromoCodeError`, `DuplicateIdempotencyKeyError` и т. п.). Обработчики в main.py превращают их в HTTP-ответы.
- Репозиторий ловит `IntegrityError`, делает `rollback` и бросает `DuplicateIdempotencyKeyError`. Сервис ловит его и возвращает существующий платёж с кодом 200.
- Без интерфейсов и абстрактных репозиториев, UnitOfWork, DI-контейнеров, DTO-мапперов. DI только через `Depends` в core/dependencies.py. Проект маленький, не усложнять.
- Асинхронный SQLAlchemy 2.0: AsyncSession, async def и await для операций БД. Асинхронные вызовы последовательно ожидаются в репозитории, сервисе, роутерах и lifespan. Alembic использует асинхронный движок.

# Критичное
- Деньги только int (копейки). float и оператор `/` запрещены.
- Скидка: `price * 10 // 100`. `amount = price - discount`.
- График рассрочки: `base, remainder = divmod(amount, months)`, первые `remainder` платежей получают `base + 1`. Для card и sbp `schedule = null`. Проверка: 1990000 / 3 = `[663334, 663333, 663333]`.
- Промокод: сравнение через `.upper()`, `KVITTO10` даёт 10%, неизвестный код даёт 422.
- Допустимые переходы хранятся в словаре `{pending: {succeeded, failed}, succeeded: {refunded}}`. Переход в тот же статус запрещён.
- Статус и способ оплаты это Enum. Неизвестное значение даёт 422.
- Порядок проверок вебхука: 404 (нет платежа), затем 409 (запрещённый переход). Статус при 409 не меняется.
- Ответ 409 вебхука: `JSONResponse` с `{"error": "invalid_transition"}`, не HTTPException. Успех: 200 `{"result": "ok"}`.
- Idempotency-Key: nullable колонка с unique-констрейнтом + обработка IntegrityError (с rollback). Повтор возвращает тот же платёж с кодом 200.
- Тарифы создаются в lifespan и только если таблица пуста.
- Схему создаёт только Alembic, `create_all` в приложении запрещён. Тесты могут использовать `create_all` на SQLite in-memory (StaticPool + `dependency_overrides`).
- Миграция: денежные колонки `Integer`, unique на `idempotency_key`, рабочий `downgrade()`.
- Для SQLite в env.py Alembic `render_as_batch=True`.
- `GET /payments` с фильтрами `email` и `status` (необязательные, комбинируются), порядок по `id` по убыванию, пустой результат это 200 и `[]`. Маршрут объявлен до `/payments/{id}`.
- `DATABASE_URL` из окружения, значение по умолчанию `sqlite+aiosqlite:///./payments.db`. Один и тот же URL для приложения и Alembic.
- Docker: `python:3.11-slim`, Poetry без виртуального окружения, `poetry install --no-root`. Запуск: миграции, затем `uvicorn ... --host 0.0.0.0 --port 8000`. SQLite-файл в томе.

# Допущения 
- Несуществующий `tariff_id`: 404.
- `installment_months` при `card` или `sbp`: 422.
- Email при сохранении и поиске приводится к нижнему регистру.

# Формат ответов
После изменений кратко перечисли, что и зачем изменено. Не пиши длинных пересказов. В конце ответа: "I finished!"

# Общие правила
1. Use Python 3.11 for all code
2. Split code into logically grouped modules inside folders according to the "Архитектура" section
3. The main entrypoint must be main.py and contain minimal logic: primarily imports and high-level orchestration
4. Every function and method must include type hints for all parameters and return types
5. Do not add type hints to local variables inside functions
6. Delete all unused imports immediately
7. Keep code clean, readable, and minimal, while retaining clarity
8. Always use poetry as the dependency and packaging manager
9. Variable and function names must be human-readable and self-explanatory at first glance
10. Use Python dictionaries instead of multiple if statements where applicable
11. Always favor explicit exceptions over silent exits or fallbacks
12. Never return None from functions. Instead, raise meaningful exceptions (the caller catches them where the "not found" case is expected)
13. Maintain the following method order in classes: public methods first, then protected (`_method`), then private (`__method`)
14. Do not add docstrings. Use clear function and method names.
15. Prefer code simplification when possible, but never at the cost of readability
16. Do not add logging (no logger module, no logging calls): the task does not require it
17. Do not use print statements
18. When handling exceptions: do not silence errors. Catch an exception only where it is actually handled, otherwise let it propagate to the exception handlers in main.py
19. Use pytest for all testing
20. Keep API tests in tests/test_billing.py and fixtures in tests/conftest.py. Cover the required scenarios through endpoints and verify database state. Do not add separate service, migration, lifespan, or concurrency tests without a request.
21. Run tests after every change
22. Add and maintain Dockerfile and README.md files
23. These files must always be up to date with the codebase
24. After every change: run tests, run linters (black, isort and mypy), fix all errors, ensure the code remains clean and compliant
25. Rewrite code like this:

    Wrong:
    ```python
    if len(args) == 2:
        do_something()
    else:
        raise ValueError("Ошибка")
    ```

    Correct:
    ```python
    if len(args) != 2:
        raise ValueError("Неверное количество аргументов")

    do_something()
    ```
26. For the tests use pytest.mark.parametrize and replace test variables with test arguments
27. For the tests use this structure: preparation, action, assertion (separated by blank lines)
28. Tests must check the result (amounts, schedule, status in DB, number of payments), not only the response code
29. Keep tests up-to-date with code
30. In README.md add instructions how to run and set up the program locally and in docker. Add explicit info how the user can interact with the program (curl examples for every endpoint), what every command is used for, and the assumptions from the "Допущения" section
