# Промпт для продолжения NEAR Intelligence

Ниже готовый промпт для нового агента. Снимок передачи: 8 ноября 2026. После старта фактический Git и `docs/TASKS.md` важнее этого снимка.

---

Продолжай разработку NEAR Intelligence в `/Users/ilyutkinn/Desktop/Near`. Выполняй оставшиеся разрешённые P0 NI-задачи по порядку через `PLAN.md`, используя отдельного субагента для каждой задачи. Ты — координатор: определяешь доступную задачу, даёшь ограниченное поручение, проверяешь результат, готовишь коммит и PR. Обычные шаги реализации обеих ролей A/B и публикация кода/тестов/конфигурации в приватном репозитории уже Дайразрешены; повторное подтверждение для них не нужно.

Главные актуальные ограничения пользователя:

1. **Исключить мобильную разработку, мобильную адаптацию и мобильное QA.** Не заниматься phone/tablet/touch UX, мобильными viewport, физическими телефонами, мобильными скриншотами и повторными mobile-прогонами. Работать для desktop. Существующий responsive-код, тесты и исторические доказательства не удалять. Старые упоминания обязательной мобильной проверки в завершённых карточках не являются новым поручением. Desktop-клавиатура, доступность, точность данных и безопасность остаются обязательными. Правка scope уже внесена в PLAN, MVP_SCOPE, TEAM_PLAN, TESTING_STRATEGY и NI-064.
2. **PR сливает только пользователь.** Не выполнять merge, не включать auto-merge и не менять настройки защиты веток. Предыдущее разрешение агенту сливать PR отменено. Подготавливать проверенные PR с понятным описанием, CI и фактическим review; передавать пользователю ссылку для слияния.
3. Экономить лимиты: один самостоятельный NI-task за раз; один исполнитель на задачу, дополнительный A/B handoff только при реальном стыке. Не плодить агентов для одинакового review и не запускать полные suites после каждой мелочи. Сначала целевые проверки, затем нужные финальные gates; повторять широкие прогоны только при значимых изменениях/ошибках. Browser QA — ограниченный desktop-сценарий, когда он нужен критериям задачи.

Перед работой прочитай `AGENTS.md`, `PLAN.md`, `README.md`, `docs/MVP_SCOPE.md`, `docs/TEAM_PLAN.md`, карточку выбранной задачи в `docs/TASKS.md` и её профильные спецификации. TASKS — единственный реестр статусов, зависимостей и приёмки. Исторические фразы «приложение ещё не реализовано» не описывают нынешний код. Не создавай второй backlog. Не переходи к P1/P2, пока P0 не завершён и scope не разрешает это.

Точка продолжения:

- Репозиторий: `ILYUTKICK/near-intelligence`, приватный.
- Последняя проверенная main: `a1f35b3ca72b7c3ba703368113a445086efd200d` — merge PR #71, NI-042. Ранее доставлены PR #69 (NI-012 + NI-041) и #70 (NI-024).
- Текущая локальная ветка: `codex/ni-043-frozen-revisions`, создана от этой main. **NI-043 остаётся TODO: claim не записан, реализации и запущенных процессов нет.** Передача от предыдущего субагента свободна. Проверь, не появился ли новый claim после этого снимка.
- Есть посторонний untracked корневой `package-lock.json`; происхождение неизвестно. Не удалять, не менять, не коммитить. Не использовать `git add .`.
- Документы с новыми правилами и этот промпт оставлены локально без коммита/PR. Сначала посмотри `git status`/diff и сохрани эти разрешённые изменения; не сбрасывай их. Приложение при подготовке передачи не менялось.

**Первая задача — NI-043, роль B:** Freeze resolved evidence on every document revision. Проверить DONE зависимостей NI-042 и NI-028, записать реальный claim, агента/роль/время/ветку в TASKS до кода. Прочитать API_SPECIFICATION, EDITOR_SPECIFICATION, CHART_SYSTEM, REPRODUCIBILITY, DATABASE_SCHEMA и AUTHENTICATION_SECURITY. Сначала определить строгую семантику `observed_contexts` и owner-scoped historical reader, затем реализовать полную карточку. Исторический просмотр и CSV должны воспроизводить сохранённый pin, а не latest. Новая публикация источника не меняет старые content/context hashes. Missing pinned artifact — явная reconstruction error, не подстановка новых данных. Проверить preview/save race, несовместимую definition version, точные decimal-строки и Alice/Bob. При необходимости поручить ограниченную desktop UI-часть A-субагенту с чётким владением файлами.

Что уже есть после NI-042:

- Редактор использует общий ChartView/ECharts, точную таблицу и source drawer. Range/filter применяются как явное undoable изменение только после успешного разрешения контекста. Только явный Refresh запрашивает latest и принимает возвращённый UUID.
- `GET /api/documents/{document_id}/chart-view`: owner check до разрешения scientific refs, no-store, immutable definition UUID, обязательный `dataset_version=UUID|latest`, даты и bounded filters. Это working-view endpoint; historical reader не должен использовать latest.
- Generic save переносит неизменённые frozen contexts дословно, включая `resolved_at`; для новых/изменённых chart attrs валидирует registry/approved pin и строит контекст существующим `build_resolved_context`. Непустой top-level `observed_contexts` пока отклоняется — это один из незавершённых стыков NI-043.
- Late replies защищены от Undo/account changes, plot связан с точной identity контекста; ошибки графика не ломают prose. Восстановление local draft с chart активирует guard. Add Insight честно отключён до NI-047; snapshot storage/UX остаются NI-044 P1.
- При закрытии NI-042 прошли 390 PostgreSQL tests, 427 web tests и финальные 7 node tests, 18 chart tests + production HTTP E2E, build/lint/types/contracts/docs. CI PR #71: все три job green. Эти результаты — историческая база, не доказательство для твоего нового кода.

Дальше выбирай задачи строго по PLAN/TASKS и фактическим dependencies. Ожидаемая ближайшая цепочка: NI-043 → NI-047 → NI-048 → NI-049 → NI-050, затем frozen export/ZIP и проверки. NI-046 и model foundation уже выполнены — не реализуй их заново. При незакрытом prerequisite PR явно указывай базу/зависимость; не выдавай код ветки за интегрированный main. Не обходи dependency gate. Не направляй изменения в уже слитую устаревшую stacked-ветку. Слияние любых новых PR оставляй пользователю.

Известные входы для последующих задач, уже записанные в TASKS:

- **NI-062:** scanner ошибочно считает обычный JWT audience `authenticated` секретом. Исправить с положительным тестом настоящей утечки и отрицательным тестом публичных metadata; не маскировать ошибку отключением сканера. Проверить full-workbench cross-tab identity retention: workbench держит loaded/recovery content без собственного auth/focus/storage revalidation, а chart guard защищает только график. Покрыть logout/account switch, pending saves, draft/download/copy-as-new.
- **NI-064, только desktop:** sidebar `/workspace/data/*` и `/workspace/models` расходится с фактическими `/data/*` и `/models`; unused Button `asChild` передаёт Slot несколько children; global anchor color может перебить on-accent foreground. Исправлять в соответствующей задаче с нужными регрессиями.
- **NI-067:** пользователь выбрал DigitalOcean, регион любой. Бюджет, домен, доступ к аккаунту/серверу не определены. Сначала подготовить проверяемую конфигурацию/вариант размещения; не создавать платные ресурсы без недостающего разрешения. При внешнем blocker записать его и продолжать другие доступные P0, не придумывать успешный deploy/restore.

Технические ориентиры:

```sh
export PATH="/opt/homebrew/opt/node@24/bin:/tmp/ni005-bin:$PATH"
# Python: apps/api/.venv/bin/python
# PostgreSQL 18: /opt/homebrew/opt/postgresql@18/bin
pnpm --filter web test
pnpm --filter web lint
pnpm --filter web typecheck
pnpm build
pnpm check:contracts
pnpm check:doc-links
apps/api/.venv/bin/python scripts/run-db-tests.py --pg-bin /opt/homebrew/opt/postgresql@18/bin
# После актуального production build, когда затронут этот flow:
apps/api/.venv/bin/python scripts/run-db-tests.py --pg-bin /opt/homebrew/opt/postgresql@18/bin --chart-insertion-http
```

Используй доступные инструменты и необходимые разрешения среды; loopback PG/HTTP и production build в этой среде требуют escalation, sandbox build ранее зависал. Не запускай рядом несколько build или конфликтующих services. Не убивай чужие процессы. Если нужен CUA desktop, native Chrome работает; browser-tab surface ранее был недоступен. Соблюдай его tool instructions и completion_summary. Не делай mobile QA.

Сохраняй границы данных: никакого перезапуска остановленных RPC collectors, удаления STOP_PUBLIC_COLLECTION, cloud SQL, платных providers, нового bulk collection или публикации raw research JSON/CSV/SQL. Не выдумывать финансовые результаты и данные. Fixtures изолированы и подписаны. Decimal/integer arithmetic, API decimals как строки, UTC half-open ranges. Owner из проверенной сессии, не `user_id` клиента. Reuse canonical registry/delivery/renderer, генерируй TS из OpenAPI. Независимое review требуется, waiver был только для NI-035/NI-041.

Для каждого завершения: реализованные исходные критерии, подходящие реальные проверки, affected docs/contracts, честные results/limitations и actual reviewer в TASKS. Затем focused commit/PR со статусом CI и ссылкой пользователю. Не объявляй merge/deploy или полную готовность P0 без фактического результата. Не останавливаться на плане или обещании — продолжать разрешённую работу до завершения либо реального внешнего blocker.
