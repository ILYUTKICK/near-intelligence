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

## 6. Что не брать в первую итерацию

P1/P2 не стартуют, пока не готов соответствующий P0-путь. Первые версии используют несколько реальных графиков, пустой документ, базовые блоки, Markdown ZIP и опубликованный ограниченный эмпирический анализ. Шаблоны, отдельный snapshot UX, PDF, advanced filters и organization откладываются. AI, collaboration, public sharing, стратегии/портфель и multichain не входят в MVP.

Сокращение числа участников не снимает обязательность источников, фактического refresh, настоящего результата модели, приватности и версии данных. Если они не выполнены, этап честно остаётся незавершённым.

## 7. Ответственный по каждой задаче

A/B — лид приёмки всей задачи; второй участник — reviewer и исполнитель своей технической части на стыках. P1/P2-владельцы указаны для планирования, не для раннего старта. Прямые зависимости, подробные шаги и тесты находятся в TASKS.md.

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
| NI-060 | Design revocable read-only sharing | P2 | B | A |
| NI-061 | Add business/data integration regression suite | P0 | B | A |
| NI-062 | Complete adversarial ownership and security audit | P0 | B | A |
| NI-063 | Verify complete research workflow end to end | P0 | A | B |
| NI-064 | Verify accessibility, responsiveness and performance | P0 | A | B |
| NI-065 | Plan advisory integrity checks and optional AI tools | P2 | A | B |
| NI-066 | Package portable local and production runtimes | P0 | A | B |
| NI-067 | Deploy staging and production with safe configuration | P0 | A | B |
| NI-068 | Verify backups, restore and operational monitoring | P0 | A | B |
| NI-069 | Run hackathon demo and reviewer reproduction | P0 | A | B |
| NI-070 | Finalize and publish original research release | P0 | A | B |
| NI-075 | Integrate the NI-074 desktop design into the working application | P0 | A | Owner |
| NI-071 | Add advanced supported analytical filters | P1 | A | B |
| NI-072 | Add lightweight private research organization | P1 | B | A |

## 8. Критерий готовности команды

Оба участника могут открыть публичный тезис, проследить реальное число до источника, войти под разными пользователями, создать независимые документы, добавить график/заметку/противоречащее доказательство, сохранить/переоткрыть и экспортировать закреплённую версию. Модель воспроизводится по manifest; обновление источника не переписывает старую аргументацию. Полный P0 release определяется MVP_SCOPE.md, а не только этим демонстрационным сценарием.
