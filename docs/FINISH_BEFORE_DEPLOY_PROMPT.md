# Задание агенту: завершить все P0/P1/P2 → проверить локально с графиками → задеплоить

Это уточнённый порядок владельца от **12 ноября 2026**, заменяющий прежнее ограничение «только MVP». Дизайн уже почти готов: используй NI-075 как основу, не начинай новый редизайн. Сначала реализуй **все зарегистрированные P0, P1 и P2**, добейся полноценной локальной работы с графиками, затем проверь итоговую интегрированную версию локально и покажи результат владельцу. Только после успешной локальной приёмки переходи к размещению. Не закрывай функциональные задачи планами, макетами, кнопками-заглушками или одной успешной сборкой.

## Начало и границы

1. Прочитай [AGENTS.md](../AGENTS.md), [PLAN.md](../PLAN.md), [README](../README.md), [MVP_SCOPE](MVP_SCOPE.md), [TEAM_PLAN](TEAM_PLAN.md), актуальные карточки [TASKS](TASKS.md) и профильные спецификации. TASKS — единственный реестр статусов. Этот текст не фиксирует готовность вместо карточек.
2. Проверь checkout, main/PR, незакоммиченные изменения, фактический код и claims. Исходная точка передачи — review PR #87 (`0b80bf2`), а не требование использовать этот устаревающий commit как финальный. Сохрани чужие изменения и работающие сервисы. Проверь, доставлены ли сами документы NI-077 в твою копию; не начинай по одному старому промпту.
3. Работа ведётся по NI-задачам с реальным claim до кода. Для A/B частей используй отдельных субагентов с конкретными файлами/контрактами по PLAN; координатор проверяет полную приёмку. Независимое второе review отменено указанием 9 ноября, обязательные тесты сохранены. Активный NI-064 не перехватывай: согласуй handoff либо продолжай независимый NI-078.
4. «Закончить проект» = все зарегистрированные P0 + шесть P1 + две P2, перечисленные ниже, и точечные NI-078. Приоритеты сохраняются, запрет на P1/P2 снят прямым указанием владельца: их собственные prerequisites должны быть готовы, но ждать deployment-задач и NI-079 нельзя. Portfolio/trading, collaboration/CRDT, multichain, billing, сценарный симулятор и другие незарегистрированные направления не добавлять. Mobile/touch/phone/tablet разработка и QA по-прежнему исключены; desktop, клавиатура и доступность обязательны.

## Этап 1. Завершить продукт, сохранив дизайн

Выполни все восемь задач перед NI-079:

| Приоритет / NI | Рабочий результат |
| --- | --- |
| P1 NI-044 | Создание/просмотр неизменяемых snapshots и сравнение с live |
| P1 NI-045 | Шаблон исследования и независимая приватная копия публичной ревизии с attribution/pins |
| P1 NI-055 | Model-result block: настоящий опубликованный run, вставка/сохранение/экспорт |
| P1 NI-059 | PDF из того же frozen IR, что Markdown, с корректными графиками/таблицами/источниками |
| P1 NI-071 | Поддержанные источником фильтры и сравнение с сохранением контекста |
| P1 NI-072 | Приватные tags/favorites, поиск/фильтры и persistence |
| P2 NI-060 | Реальный локальный read-only sharing выбранной frozen ревизии, consent, expiry/revoke и защита assets |
| P2 NI-065 | Работающие deterministic integrity checks и optional evidence-grounded AI adapter, no-key workflow |

NI-060 и NI-065 раньше были design/plan-only. Их приёмка обновлена владельцем: теперь нужны реализация и тесты. AI-вызовы, провайдер, расходы и передача приватного текста не включаются автоматически: ключи/контекст/назначение требуют действующего разрешения; базовые проверки и продукт работают локально без AI. Не выдавай mock-ответ за реальную интеграцию. Новые security-sensitive публикации реальных документов не создавать ради проверки — используй изолированные синтетические локальные записи.

Выполни **NI-078** по [отчёту NI-076](verification/ni-076/README.md) и NI-074 design pack (если он передан отдельно). Если атлас отсутствует, запроси конкретный handoff; не выдумывай его содержимое. Сохрани полный публичный тезис и нынешние рабочие сценарии.

- Research: компактный обзор статусов H1–H4 и читаемая последовательность «график → вывод → доказательства», полный текст ниже.
- Добавь исторические фигуры USD по трём окнам CL-004 и покупок относительно net supply growth CL-007. Используй проверенные определения/данные, обозначай estimates, источники, периоды и ограничения. Покупки не являются burn и не вычитаются из supply.
- Chart detail: одно название, компактные действия/фильтры, значительная часть графика на первом экране.
- Saved Charts: компактные сопоставимые previews на общем renderer; точные таблицы и источники доступны, без повторных титулов и длинных форм в каждой карточке.
- Editor: компактный header, больше места paper, contextual block actions, UUID в Properties; pins/save/freshness и explicit refresh остаются видимыми и корректными.
- Отдельно воспроизведи Custom range → Apply: в NI-076 автоматизация не подтвердила изменение периода. Зафиксируй фактический результат, исправь подтверждённую проблему и проверь URL/range/reopen. Не объявляй баг доказанным лишь на основании этого наблюдения.

Заверши оставшиеся P0/P1/P2 и подтверждённые дефекты. Готовые компоненты и основной визуальный стиль сохрани; NI-078 исправляет конкретные проблемы, а не создаёт новый дизайн. Старое DONE не отменяет конкретный невыполненный критерий: сохрани историю, переоткрой соответствующую карточку с причиной либо оформи отдельную bounded NI-задачу. Не реализуй untracked work. Обязательные требования к реальному refresh и настоящему эмпирическому результату сохраняются: в момент передачи публичная модель была честно пустой, fit реального архива оставался pending. Одной готовой реализации estimator недостаточно.

Данные/модель выполняй только по существующему разрешению и проверенному permitted input handoff через NI-030/051–054/070. Отсутствие исходных файлов, прав или согласования — конкретный blocker, а не разрешение получить другие данные. Не публикуй сырой архив, не запускай stopped collectors, cloud SQL, платные источники или новый bulk collection. Продолжай независимые задачи без обхода data gate.

## Этап 2. Полная локальная приёмка P0/P1/P2 с графиками — NI-079

После интеграции всех функций P0/P1/P2 и исправлений проверь **один итоговый release candidate**, а не разные ветки по частям. Базовые обязательные проверки определяют [TESTING_STRATEGY](TESTING_STRATEGY.md), [JUDGE_SETUP](JUDGE_SETUP.md), карточки NI-061/062/063/064/066 и CI. Ниже стартовые существующие команды; сначала проверь scripts, окружение и реальные пути. Ничего из этого ещё не объявляется выполненным этой передачей.

```sh
pnpm install --frozen-lockfile
uv sync --project apps/api --frozen
uv lock --check --project apps/api
pnpm lint
pnpm typecheck
pnpm test
pnpm --filter @near-intelligence/shared-types typecheck
pnpm --filter @near-intelligence/shared-types test
pnpm check:contracts
pnpm check:doc-links
pnpm check:contrast
pnpm build
pnpm check:client-secrets
uv run --project apps/api python -m unittest discover -s apps/api/tests -p 'test_*.py'
```

Далее полный disposable PostgreSQL suite, необходимые production HTTP suites, NI-063 и актуальные desktop/design E2E. `pnpm test:api:unit` в текущем корне охватывает лишь две семьи и не заменяет полный Python discovery. Кластерные/архивные skips не считать PASS этих gates — запустить нужный режим отдельно либо оставить blocker.

```sh
# Укажи фактический локальный путь PostgreSQL 18; на macOS Homebrew:
uv run --project apps/api python scripts/run-db-tests.py --pg-bin /opt/homebrew/opt/postgresql@18/bin
uv run --project apps/api python scripts/run-db-tests.py --pg-bin /opt/homebrew/opt/postgresql@18/bin --suite landing
uv run --project apps/api python scripts/run-db-tests.py --pg-bin /opt/homebrew/opt/postgresql@18/bin --chart-insertion-http
pnpm --filter web exec playwright test --config e2e/playwright.config.ts
```

Проверь, какие дополнительные suites добавлены в текущем коде. Браузер/зависимости устанавливай из закреплённых официальных источников; production build должен предшествовать соответствующим HTTP/E2E. Не запускай конфликтующие builds и не останавливай чужие процессы.

Обязательно проверить и приложить доказательства:

- **Графики — основной критерий приёмки:** trace хотя бы одного разрешённого реального ряда от input→metric/API→plot и exact table→Save Chart→документ→snapshot→refresh/compare→Markdown/PDF. Проверить исторические фигуры исследования, tooltip/table/units/source/dates, range/filter comparison, реальные model-result figures и frozen charts в sharing. Скриншот без сохранения/источника/API не доказывает работу. Не использовать production charts с тестовыми цифрами. Недоступные метрики честно показывают причину; заполнить все категории фиктивными данными нельзя.
- **Все P1/P2 journeys:** snapshot freeze/compare; template/public duplication с ID remap и независимыми правками; published model insert/save/reopen/export; PDF со всеми страницами/таблицами/фигурами; поддержанные filters/comparison; private tags/favorites; sharing consent→anonymous read→expiry/revoke→asset denial; integrity finding→source jump→fix→rerun и AI-off/outage. Доказать persistence/ownership и точность контекста, а не наличие меню.

- Настоящие локальные web/API/PostgreSQL/worker: public research → chart → login → Save Chart → Add Chart → документ → Insight → противоречащее Evidence → autosave/manual save → reload → pinned revision → Markdown ZIP. Распаковать ZIP, сравнить manifest/hash/CSV/SVG с сохранённой ревизией.
- Alice/Bob на server/RLS/gateway: чужие CRUD, nested IDs, поиск, charts, history и export недоступны. Logout/expiry/account switch, конфликт вкладок и recovery не показывают чужой контент.
- Outage/empty/error/stale: не рисуются вымышленные нули, last good сохраняется, сбой графика/источника не блокирует prose. Новые данные не переписывают исторические ревизии/экспорт.
- Все публичные и приватные desktop экраны, реальные plots, клавиатура/focus/dialog return, доступная таблица без hover, contrast, reduced motion, отсутствие overflow. До/после для D1–D5; performance budgets на 200 blocks/20 chart refs/366 periods с записанными машиной/режимом.
- Локальная production/container репетиция по JUDGE_SETUP: чистые build/миграции/health, worker/export, приватная сеть/секреты, collectors/scheduler off по умолчанию, backup DB+artifacts → изолированный restore с hash/ownership/pins и rollback образа. Linux-container проверку не заменять native macOS запуском.
- Отдельно реальные разрешённые исследовательские inputs, provenance/rights, actual refreshed series с last-good поведением и воспроизводимая опубликованная модель на настоящем ряде. Синтетический QA harness проверяет инженерный путь, но не доказывает наличие research data, real Supabase integration или разрешённых научных результатов. Real-auth проверять только в согласованном dev окружении; если недоступно — записать незакрытый gate.

Итог: `docs/verification/ni-079/README.md` с commit, tree/diff hash, lock/image/input versions, окружением, командами/exit results, pass/fail/skips, screenshots, найденными и исправленными проблемами и перечнем ещё только удалённых проверок. Не помещать туда credentials, raw restricted inputs или приватные документы. После исправлений повторить затронутые проверки; не использовать доказательства старой сборки. Для размещения итоговые изменения должны быть в проверенном зафиксированном candidate; PR сливает владелец.

При любом незакрытом required P0/P1/P2/graph/core-flow/security/data/model/design gate **NI-079 не DONE и удалённый rollout запрещён**. Покажи рабочий локальный продукт и точный список blockers. Не меняй критерии или priority ради зелёного отчёта.

## Этап 3. Размещение после локальной приёмки

Только при NI-079 DONE переходи к **NI-067**, затем **NI-068 → NI-069**. До этого готовить проверяемую конфигурацию/runbook можно; создавать/обновлять удалённое размещение и включать scheduler нельзя.

DigitalOcean ранее выбран владельцем; регион не ограничен. Бюджет, домен и актуальный доступ не следует считать известными. Подготовь конкретный вариант и соблюдай существующие разрешения на ресурсы/расходы; не запрашивай повторно уже выданное разрешение, но не выдумывай недостающее. Не merge/auto-merge PR от имени владельца.

На staging/production проверить реальный TLS origin, callback/cookies/auth/expiry, migrations/health, production smoke, отсутствие primary fixtures и публичного private caching. Выполнить удалённые backup/restore/monitoring/rollback и deployed demo/reproduction по исходным карточкам. Локальная репетиция не закрывает эти проверки. Полный проект P0/P1/P2 в согласованном scope готов только после всех применимых release gates; сообщи реальные URL, commit и результаты, без фиктивных обещаний ежедневного обновления.
