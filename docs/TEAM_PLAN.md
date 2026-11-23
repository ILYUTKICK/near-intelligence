# План работы для двух участников

**Обязательный порядок работы агентов: [PLAN.md](../PLAN.md).** Этот файл задаёт роли и handoffs; статусы хранятся только в TASKS.md.

Предложение от 5 ноября 2026. Допущение: оба участника технические; A сильнее в TypeScript/интерфейсах, B — в Python/данных. Имена и реальная загрузка пока неизвестны. Если один из участников — исключительно аналитик без backend-навыков, этот вариант нужно перераспределить до начала разработки.

План распределяет [существующий backlog](TASKS.md), не меняет приоритеты, зависимости или критерии готовности. Все задачи остаются TODO. Назначение ответственных не означает начала реализации: в этом изменении добавлена только документация.

**Назначение — 8 ноября 2026:** по прямому указанию пользователя Codex в чате `01a1ba7d-239f-7483-b2d6-fc651744fe9b` может выполнять свободные задачи и записанные handoffs обеих ролей A/B. NI-035 и NI-041 продолжают текущие исполнители; это назначение не передаёт их claims. Владельцы карточек и независимое review сохраняются.

## 1. Две зоны ответственности

| Участник | Главный результат | Основные обязанности | Основные пути |
| --- | --- | --- | --- |
| **A — продукт и интерфейс** | Пользователь проходит весь путь от чтения исследования до собственного документа и экспорта | Дизайн-система, публичные страницы, workspace, графики ECharts, Tiptap, браузерная часть auth, формы/состояния, E2E, доступность; сборка/размещение и демонстрация | `apps/web/**`, web auth gateway, JS-рендерер экспорта, Playwright, CI/web/deployment; редакционный публичный контент |
| **B — данные, backend и количественные расчёты** | Каждое число имеет проверяемый источник, а приватные документы безопасно сохраняются | Источники/права/лимиты, импорт и обновление, метрики, PostgreSQL/миграции/RLS, REST API, серверная авторизация, версии документов/снимки, модели и воспроизводимость, серверный экспорт | `apps/api/**`, Alembic, Python CLI, новые `research/models/**` и отчёты, API-схемы/генератор клиента |

Это разделение по техническим границам, с общей приёмкой продукта. A не должен независимо вычислять финансовые метрики в UI. B не должен писать отдельную реализацию графиков для каждой страницы. Существующие архивы `research/near-*` и остановленные сборщики сохраняются.

## 2. Как выполнять задачи, затрагивающие обе зоны

**Назначение — 8 ноября 2026:** по прямому поручению пользователя Codex координирует последовательное выполнение оставшихся P0 с отдельными субагентами на NI-задачи. Роли A/B, claims, handoffs и фактические результаты фиксируются в TASKS.md; чужие активные claims не перехватываются без передачи. Исключение независимой приёмки для NI-035/NI-041 сохраняется, для остальных задач действует реальный review.

**Исключение пользователя — 8 ноября 2026:** для NI-035 и NI-041 независимая приёмка отменена последующим прямым поручением; Codex исправляет подтверждённые замечания и закрывает задачи после проверок. Остальные правила review сохраняются. Слияние PR остаётся у оператора.

**Handoff — 8 ноября 2026:** пользователь передал NI-035 и NI-041 агенту Codex в чате `01a1ba7d-239f-7483-b2d6-fc651744fe9b`, разрешив вклад обеих ролей A/B. Продолжить существующие b9/b8 изменения без потери истории; NI-035 выполняется первой. Независимое review остаётся обязательным.

У каждой NI-задачи ниже **один ответственный за закрытие**. Он следит за зависимостями и доказательствами приёмки; второй участник реализует свою часть и делает review. Ответственный не обязан один писать весь код задачи. Задача остаётся IN_PROGRESS до завершения обеих частей; её не закрывают после готовности только API или только картинки.

| Стыковочная задача | A делает | B делает | Кто закрывает |
| --- | --- | --- | --- |
| NI-002 — каркасы | Next.js/TS/workspace/JS-lock | FastAPI/settings/Python-lock | A |
| NI-004 — контракты | Проверяет типизированное потребление в UI | Pydantic/OpenAPI и воспроизводимую генерацию клиента | B |
| NI-017/NI-018/NI-020 — auth | Страницы, server cookies, gateway, восстановление UX и browser-тесты | Проверку JWT, principal, disabled-user и серверные тесты | Владелец соответствующей NI-задачи |
| NI-025 — профиль/настройки | Экраны, сохранение, локальные draft-контролы | `/me` read/update, валидацию timezone/имени | A |
| NI-035 — saved charts | Список/действия/повторное открытие | CRUD, ownership, фильтры/ссылки | B |
| NI-040 — autosave | Очередь сохранений, статусы, conflict/recovery UI | CAS/idempotency и проверку атомарности в сервисе документов | A |
| NI-041–NI-043 — встраивание графиков | Destination picker, node view, управление и badges | Вставку блока, разрешение контекста, immutable pins | B / A / B соответственно |
| NI-047–NI-050 — insights/evidence | Формы, карточки, навигацию и источники контекста | Мутации версий, связи, ownership и integrity | B / B / B / A соответственно |
| NI-053/NI-054/NI-070 — исследование | Проверяет смысл интерпретации, пишет публичный текст и отображает настоящие результаты | Выполняет модель/диагностику, фиксирует sample/config/locks/manifest, даёт API | B / B / A соответственно |
| NI-056–NI-058 — экспорт | JS-рендер графиков и интерфейс загрузки/ошибок | Frozen IR, jobs/worker, ZIP/manifest и авторизацию download | B / A / B соответственно |
| NI-066–NI-068 — эксплуатация | Упаковка, конфигурация окружения, rollout, мониторинг и restore-runbook | Ревью DB-ролей/миграций, artifact consistency, source budget и restore/hash проверок | A |

A и B согласуют миграции/API на стыках до изменений. «B делает API» не означает, что A ждёт его целиком: типизированный контракт и отдельные тестовые данные позволяют параллельно делать интерфейс. Такие тестовые данные изолированы и подписаны; ими нельзя заменять реальные производственные метрики или закрывать интеграционные критерии.

## 3. Что согласовать перед параллельной работой

Одна короткая совместная сессия, без нового большого проектирования:

1. **P0-срез:** какие 3–5 графиков берём первыми, какие данные доступны и какая модель допустима. Недоказанная ежедневная выручка не становится доступной от появления макета.
2. **ChartView/Dataset:** десятичные строки, единицы, UTC `[start,end)`, качество, источники, immutable version ID. B владеет схемой, A проверяет пригодность для графика/экспорта.
3. **Документ:** `schema_version`, стабильные block IDs, структура JSON, revision/If-Match, pins, ошибки 409/422. B владеет сохранением; A — сериализацией редактора и восстановлением.
4. **Auth:** cookie/gateway и JWT/API границы, одинаковые 404 для несуществующего и чужого объекта, тестовые Alice/Bob.
5. **Модель:** исследовательский вопрос, исходный ряд, исключения/нулевые значения, config и допустимые выводы. B отвечает за вычисление; A делает независимый review вывода и ссылок.

Это краткие зафиксированные решения по существующим [API](API_SPECIFICATION.md), [схеме БД](DATABASE_SCHEMA.md), [редактору](EDITOR_SPECIFICATION.md) и [методологии](ECONOMETRIC_METHODOLOGY.md), а не новые конкурирующие спецификации.

## 4. Порядок работы и точки интеграции

Ниже этапы по результату, а не обещание календарных сроков. Зависимости из TASKS.md остаются обязательными. Внутри одной колонки участник выполняет задачи последовательно по их готовности, не «параллелит сам с собой» несколько критических потоков.

| Этап | A | B | Совместная проверка |
| --- | --- | --- | --- |
| 0. Проверка плана | Согласует интерфейсные сценарии, первые графики и публичные тезисы | Уточняет доступность рядов/прав/лимитов и допустимость модели | Зафиксированы scope и четыре контракта выше; доступы/бюджет не считаются автоматически одобренными |
| 1. Основа | NI-001/NI-002 web-часть; затем NI-006–NI-010, NI-011; CI после зависимостей NI-005 | NI-002 API-часть; NI-003/NI-004; NI-026 после NI-001 | Обе среды запускаются; схема/клиент согласованы; первый пригодный источник определён |
| 2. Данные и auth | NI-016/NI-017; интерфейсы shell/source states; готовит потребление контракта | NI-018/NI-019; NI-027–NI-032 в порядке зависимостей | Первый настоящий ряд доходит из сохранённого источника до API; Alice/Bob изолированы |
| 3. Первый полный график | NI-020/NI-021, NI-033/NI-034, NI-015; затем NI-012 по готовности | NI-035, NI-036/NI-037, NI-022; NI-030 после своих зависимостей | Один и тот же график в public/workspace; save/reopen сохраняет выбранный контекст |
| 4. Редактор и расчёты | NI-038–NI-040; NI-023/NI-024/NI-025 по готовности | После подготовки данных и document API выделяет отдельный блок на NI-051–NI-054 | Созданный документ переживает перезагрузку; настоящая модель воспроизводится без подмены показателей |
| 5. Аргумент в документе | UI NI-041, NI-042; формы NI-047–NI-049; NI-050; методология/тезис NI-013/NI-014 | Сервер NI-041, NI-043, NI-046–NI-049; NI-061 | Гипотеза → противоречащее доказательство → закреплённый график → источник |
| 6. Экспорт и проверка | NI-057, export UI; NI-063/NI-064; публичный release NI-070 | NI-056/NI-058, NI-062; ревью цитат и результатов NI-070 | ZIP соответствует конкретной версии документа; чужой пользователь не может скачать его |
| 7. Размещение и demo | NI-066–NI-069 после всех зависимостей | Ревью миграций/данных/restore; независимый offline rerun и поддержка исправлений | Реальный deployed walkthrough + воспроизведение + восстановление backup |

Календарный план составляется после указания дедлайна и часов каждого участника. Количество задач не равно трудоёмкости: неизвестность источников и модели делает поток B особенно рискованным. Если B упирается в доступы/данные, A помогает с проверкой документации/прав и редакционным доказательным материалом, продолжая независимую UI-работу. Ложные ряды и бесконечное расширение источников не используются как обход блокировки.

## 5. Минимальные договорённости о Git и review

**Последнее указание пользователя — 8 ноября 2026:** PR сливает только пользователь. Агент готовит код, проверки, фактическое review и PR; самостоятельный merge и включение auto-merge запрещены. Прежнее разрешение координатору на merge отменено. Для PR указывать настоящую базу и зависимости; слияние в уже слитую stacked-ветку не считается доставкой. Мобильная разработка, адаптация и mobile/touch/phone/tablet QA исключены из текущего scope; работа и приёмка ориентированы на desktop. Уже выполненный мобильный код/исторические проверки не удалять.

- Один общий репозиторий и одна интеграционная ветка; короткие ветки `feat/ni-XXX-description` по существующему CONTRIBUTING.md. Каждый работает в своём checkout, без одновременной правки одних физических файлов.
- A владеет web/JS lock и web build; B — Python lock, миграциями и Pydantic/OpenAPI. Не редактировать генерированный клиент руками. Корневой Compose/CI/README координирует A, DB/provider-секции проверяет B.
- Для задачи, затрагивающей обе стороны, сначала маленький PR схемы/контракта, затем потребитель. Изменение обязательного поля или экономического определения требует уведомления второго участника и совместной проверки.
- У каждого PR второй участник — reviewer. Для эконометрики review проверяет определения/sample/выводы и воспроизводимость, а не только синтаксис Python. Для приватных ресурсов обязательны два пользователя.
- Ежедневно короткая синхронизация: что интегрировано, какой контракт нужен следующим, какой blocker появился. Регулярно показывать настоящий сквозной сценарий; частота подстраивается под дедлайн.
- Не откладывать интеграцию до финала. Не создавать две копии метрик/рендеров/редактора. Перед DONE выполнить критерии исходной NI-задачи; владельцы ниже не могут ослабить их.

## 6. Актуальный scope перед размещением

**Указание владельца — 12 ноября 2026:** все зарегистрированные P1/P2 входят в выпуск до деплоя. Соблюдать прямые prerequisites; не ждать deployment-задач или NI-079, чтобы начать P1/P2. A: NI-055/059/071 и UI handoffs NI-044/045/072/060; B: NI-044/045/072/060 и API/data/export handoffs. NI-065 координирует A с B evidence-tool/API частью. Сохранить основной дизайн NI-075, править конкретные дефекты NI-078. CRDT, portfolio, multichain и другие незарегистрированные направления не добавляются.

Сокращение числа участников не снимает обязательность источников, фактического refresh, настоящего результата модели, приватности и версии данных. Если они не выполнены, этап честно остаётся незавершённым.

## 7. Ответственный по каждой задаче

A/B — лид приёмки всей задачи; второй участник — reviewer и исполнитель своей технической части на стыках. P1/P2-владельцы отвечают за реализацию до локального release-gate по указанию 12 ноября. Прямые зависимости, подробные шаги и тесты находятся в TASKS.md.

Распределение P0: **A — 35 задач, B — 29 задач**. Эта пропорция не является оценкой часов: сложность и межкомандные части учитываются отдельно.

| ID | Задача | Приоритет | Ответственный | Reviewer |
| --- | --- | --- | --- | --- |
| NI-001 | Initialize repository and pin tooling | P0 | A | B |
| NI-002 | Create web and API runtime skeletons | P0 | A | B |
| NI-003 | Create database roles and initial schema migrations | P0 | B | A |
| NI-004 | Establish OpenAPI generation and typed clients | P0 | B | A |
| NI-005 | Add baseline CI and developer checks | P0 | A | B |
| NI-006 | Implement design tokens and typography | P0 | A | B |
| NI-007 | Build accessible interaction primitives | P0 | A | B |
| NI-008 | Create public and workspace layout shells | P0 | A | B |
| NI-009 | Build common data and async states | P0 | A | B |
| NI-010 | Create chart frame and source drawer | P0 | A | B |
| NI-011 | Create public editorial routes and mechanism section | P0 | A | B |
| NI-012 | Bind landing to approved findings and metrics | P0 | A | B |
| NI-013 | Publish methodology and reproduction content | P0 | A | B |
| NI-014 | Create public thesis with claim registry | P0 | A | B |
| NI-015 | Deliver public analytics explorer | P0 | A | B |
| NI-016 | Configure managed authentication environment | P0 | A | B |
| NI-017 | Implement same-origin login and cookie lifecycle | P0 | A | B |
| NI-018 | Verify JWT and bootstrap application principal | P0 | B | A |
| NI-019 | Enforce request-scoped ownership and RLS | P0 | B | A |
| NI-020 | Verify authentication recovery and session boundaries | P0 | A | B |
| NI-021 | Protect workspace routes and shell | P0 | A | B |
| NI-022 | Implement owner-scoped home aggregation API | P0 | B | A |
| NI-023 | Build My Research and recent-item views | P0 | A | B |
| NI-024 | Build research-focused workspace Home | P0 | A | B |
| NI-025 | Implement profile and minimal settings | P0 | A | B |
| NI-026 | Verify provider capability, entitlement and rights | P0 | B | A |
| NI-027 | Import existing archives read-only | P0 | B | A |
| NI-028 | Implement immutable dataset staging and publication | P0 | B | A |
| NI-029 | Implement exact metric computations and quality | P0 | B | A |
| NI-030 | Add one bounded scheduled refresh adapter | P0 | B | A |
| NI-031 | Define versioned chart and metric registries | P0 | B | A |
| NI-032 | Deliver metrics, chart views and source APIs | P0 | B | A |
| NI-033 | Implement reusable interactive ECharts renderer | P0 | A | B |
| NI-034 | Build chart library and detail navigation | P0 | A | B |
| NI-035 | Persist saved chart instances | P0 | B | A |
| NI-036 | Implement canonical document schema and revision service | P0 | B | A |
| NI-037 | Implement document CRUD and version endpoints | P0 | B | A |
| NI-038 | Prototype Tiptap custom block integration | P0 | A | B |
| NI-039 | Build editor layout and block operations | P0 | A | B |
| NI-040 | Implement autosave, manual save and conflict recovery | P0 | A | B |
| NI-041 | Implement Add Chart to owned research | P0 | B | A |
| NI-042 | Complete interactive chart node behavior | P0 | A | B |
| NI-043 | Freeze resolved evidence on every document revision | P0 | B | A |
| NI-044 | Add explicit snapshot management UX | P1 | B | A |
| NI-045 | Implement template and public research duplication | P1 | B | A |
| NI-046 | Define structured insight and evidence node contracts | P0 | B | A |
| NI-047 | Persist context-preserving chart insights | P0 | B | A |
| NI-048 | Implement hypothesis blocks and assessments | P0 | B | A |
| NI-049 | Implement evidence relationships and classifications | P0 | B | A |
| NI-050 | Build evidence navigation and research context panels | P0 | A | B |
| NI-051 | Implement model dataset readiness gate | P0 | B | A |
| NI-052 | Implement fixed deterministic econometric estimator | P0 | B | A |
| NI-053 | Generate diagnostics, robustness and interpretation artifacts | P0 | B | A |
| NI-054 | Publish reproducible model artifacts and APIs | P0 | B | A |
| NI-055 | Add model-result block to private research | P1 | A | B |
| NI-056 | Create frozen document export representation | P0 | B | A |
| NI-057 | Render static chart assets from frozen contexts | P0 | A | B |
| NI-058 | Deliver Markdown ZIP export jobs and download | P0 | B | A |
| NI-059 | Implement PDF export from frozen representation | P1 | A | B |
| NI-060 | Implement revocable read-only sharing | P2 | B | A |
| NI-061 | Add business/data integration regression suite | P0 | B | A |
| NI-062 | Complete adversarial ownership and security audit | P0 | B | A |
| NI-063 | Verify complete research workflow end to end | P0 | A | B |
| NI-064 | Verify accessibility, responsiveness and performance | P0 | A | B |
| NI-065 | Implement advisory integrity checks and optional AI tools | P2 | A | B |
| NI-066 | Package portable local and production runtimes | P0 | A | B |
| NI-067 | Deploy staging and production with safe configuration | P0 | A | B |
| NI-068 | Verify backups, restore and operational monitoring | P0 | A | B |
| NI-069 | Run hackathon demo and reviewer reproduction | P0 | A | B |
| NI-070 | Finalize and publish original research release | P0 | A | B |
| NI-075 | Integrate the NI-074 desktop design into the working application | P0 | A | Owner |
| NI-076 | Run PR 87 locally and review desktop design against NI-074 | P0 | A | Owner |
| NI-077 | Record finish-local-verify-deploy handoff | P0 | A | Coordinator |
| NI-078 | Complete desktop research and chart presentation | P0 | A | Coordinator |
| NI-080 | Repair workspace navigation and email-label demo entry | P0 | A | B |
| NI-081 | Redesign the public methodology reading experience | P0 | A | B |
| NI-082 | Audit and design the long-history evidence extension | P0 | B | A |
| NI-083 | Implement interactive long-history research and exact descriptive calculations | P0 | A with B data/calculations | Coordinator |
| NI-084 | Record the Blog and research-publication product direction | P1 | A | Coordinator |
| NI-085 | Implement the public Blog and research-publication catalog | P1 | A | Coordinator |
| NI-086 | Implement the approved editorial Overview design | P1 | A | Coordinator |
| NI-087 | Present the complete investment thesis and simplify the chart library | P0 | A | Owner |
| NI-088 | Explain the research workflow and simplify chart details | P0 | A | Owner |
| NI-079 | Pass final integrated local release acceptance | P0 | A with B data/API/model contributions | Coordinator |
| NI-071 | Add advanced supported analytical filters | P1 | A | B |
| NI-072 | Add lightweight private research organization | P1 | B | A |

## 8. Критерий готовности команды

Оба участника могут открыть публичный тезис, проследить реальное число до источника, войти под разными пользователями, создать независимые документы, добавить график/заметку/противоречащее доказательство, сохранить/переоткрыть и экспортировать закреплённую версию. Модель воспроизводится по manifest; обновление источника не переписывает старую аргументацию. Полный P0 release определяется MVP_SCOPE.md, а не только этим демонстрационным сценарием.


NI-076 owner review: role A /root coordinates isolated local deployment and desktop browser verification; /root/design_pr_audit performs bounded read-only implementation/atlas comparison. NI-075 claim and prior acceptance history are preserved.

**Owner handoff — 11 November 2026:** NI-077 documents the finish→local-acceptance→deployment order; [current executable assignment](FINISH_BEFORE_DEPLOY_PROMPT.md). A owns NI-078 desktop/UI and NI-079 integrated acceptance; B owns the latter's real data/model/API contributions through the applicable existing NI-cards. NI-064's existing claim is unchanged: agree a handoff with its executor or progress independent work. The final local gate precedes remote rollout under NI-067; NI-068/069 still verify actual remote operations/demo. Independent second review is skipped under the 9 November instruction; coordinator acceptance and original checks remain mandatory. No new execution claim or paid/cloud/data permission is created by this ownership table.

**Уточнение передачи — 12 ноября 2026:** NI-079 принимает весь P0/P1/P2, включая работающие локально графики на public/private/snapshot/model/comparison/Markdown/PDF/share путях. Прежнее ограничение NI-077 только MVP заменено этой передачей; активные claims и границы прав/данных сохранены. P2 NI-060/065 теперь implement-and-test, не ADR-only. Ни состав ролей, ни optional AI adapter не разрешают внешнюю передачу приватного текста или расходы автоматически.

**NI-064 completion handoff — 13 November 2026:** the owner explicitly assigned completion to Codex `/root` in chat `01a1d450-7c47-7371-8d61-022471615ad3`. This supersedes the older retained NI-064 claim only for its acceptance/fixes; prior implementation evidence remains. Role A owns current desktop accessibility/keyboard/performance verification and the screen-reader/IME remainder, with actual results in TASKS and the QA report. No mobile or deployment scope.

**NI-064 completion — 13 November 2026:** Codex `/root` finished the bounded fixes and local desktop verification; the owner confirmed the remaining IME/VoiceOver checklist with “Все четок”. Evidence and DONE status are recorded only in [TASKS.md](TASKS.md) and the linked QA report. The execution claim is released; PR #99 is the owner-merge handoff. NI-079 and NI-067 retain their own acceptance scope.

**NI-080 owner correction batch — 13 November 2026:** `/root` coordinates Home/navigation and demo-entry corrections in TASKS. A bounded subagent handles shared workspace route/UI changes; the coordinator owns demo gateway/harness integration and actual two-visitor verification. No competing claim or shared Alice identity.

**NI-081 local methodology review — 13 November 2026:** role A coordinates a reader-facing design/local implementation. A dedicated NI-081 subagent handles the page and focused tests; root checks source fidelity and desktop behavior. NI-080 changes remain preserved. All Git publication is on hold by owner instruction.

**NI-082 — 13 November 2026:** root coordinates a bounded role-B read-only archive audit via a dedicated agent, then checks interpretation and primary-source policy dates. No data collection, remote publication or replacement of the existing cohort is authorized by this claim.

**NI-083 — 14 November 2026:** root owns research UI/shared chart interactions, integration and acceptance; dedicated task agent owns backend saved-history loading, exact descriptive calculations, contracts and focused tests. Coordinate generated client changes before consumption. Root alone updates task/plan status. Preserve NI-080/081/082 and the Git hold.

**NI-084 — 14 November 2026:** documentation only. A dedicated agent writes the Blog/editorial brief; root synchronizes README, product requirements, scope, route planning and the decision log. No application route, dependency, public content or raw data is added. Status and acceptance remain in TASKS.

**NI-085 — 14 November 2026:** dedicated task agent owns Blog web implementation, curated publication metadata/routing, public navigation and focused UI tests. Root owns plan/contracts documentation, local production build, real archive/API browser verification and acceptance. Coordinate before editing shared files; preserve NI-080–084 and the Git hold.

**NI-086 — 14 November 2026:** dedicated task agent owns Overview web layout/copy and affected frontend tests. Root owns approved mockup/hero asset handoff, legacy landing HTTP integration acceptance updates, documentation and production/browser verification. No shared-file edits without coordination. Research article, Blog, private workspace and all prior batches remain preserved; Git hold remains.


## NI-089 local-preview recovery

Role A: Codex /root applies bounded current-checkout recovery and verifies local containers/browser. /root/current_design_review independently checks preservation of the approved Overview/Blog/article structure and the source-qualified editorial delta. Do not edit another task's active Overview/chart-detail files or change data services.


## NI-090 VPS preparation

Role A: Codex /root coordinates the current checkout, source handoff and operator runbook. /root/vps_config implements isolated production Compose/Caddy/environment validation in a staging directory; /root reviews security/credentials/network boundaries and verifies in disposable local containers. Independent review follows before DONE. No remote mutation or takeover of NI-067/079.


## NI-098 — README and self-hosting handoff

Explicit owner request14 November2026: A owns product README, local/own-domain
deployment guide and verification record; B supports read-only review of
configuration, data/model handoff and credential boundaries. Root coordinates
NI-098; /root/ni067_review audits commands. Status/acceptance remain in TASKS.
No application/SEO feature, new data collection or remote rollout is included.

NI-098 follow-up15 November2026: root handles published-history audit and release record; /root/ni067_review implements the approved original-code MIT/third-party notices and public-clone README adjustments. No visibility mutation or research-data publication.


## NI-099 — Comic Lab implementation

Role A /root coordinates the owner-approved desktop redesign. The dedicated task agent owns apps/web code and bounded design documentation; root supplies canonical brand/font assets, claims/status, runtime/verification and GitHub delivery. Preserve current backend/metrics, editor schema, auth/ownership and immutable exports. Existing NI-080/088/092/093/095 claims remain assigned as recorded. The earlier independent-review waiver applies; actual coordinator checks remain mandatory. No mobile work, merge or deployment. Status lives only in TASKS.md.


## NI-100 — Unslop polish

Role A /root coordinates the explicitly requested Unslop pass using the already-approved Comic Lab direction. Dedicated task agent /root/ni100_unslop owns bounded web/styles/tests/design-doc edits; root owns audit, registry, runtime, acceptance and the existing PR105. Preserve all product/data/auth/export contracts, canonical brand and section order. No generated media, mobile work, merge or deployment. Sole status/claim in TASKS.md; independent review waiver remains.

## NI-101 — Complete Unslop follow-up and Save chart

Role A /root coordinates the owner-requested full desktop surface audit. Dedicated /root/ni101_unslop owns frontend and affected test implementation; root owns registry, runtime/browser acceptance, verification report and PR delivery. Save chart restoration reuses existing API ownership/persistence without new backend contracts. Preserve other claims and all data/pin/export/auth boundaries. Status only in TASKS.md; independent review waiver remains.

## NI-102 — Existing owner VPS update

Owner production-update handoff (23 November 2026): role A /root coordinates registry, source packaging, existing-VPS SSH/backup/rollout and external acceptance; dedicated /root/ni102_rollout reviews merged-source deployment/schema/auth compatibility read-only. Existing claims and NI-068 operational remainder are preserved. No source collection or new infrastructure. Status and actual results live only in TASKS.md.

## NI-103 — Real-product thesis demo

Role A /root coordinates the owner-requested recording, separate demo identity, actual product workflow, source/date fidelity and final media acceptance. Dedicated /root/ni103_edit prepares real production-stack recording acceptance and local video editing/English chapter captions within the approved Comic Lab direction. Native capture was replaced by the existing isolated regression harness after CUA became unavailable; synthetic authentication transport is disclosed. No fabricated UI, runtime source changes, collection or social publication. Sole claim/status in TASKS.md; independent review waiver remains.
