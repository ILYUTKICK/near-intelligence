# Обязательный план выполнения NEAR Intelligence

Версия 1 • 5 ноября 2026. **Каждый агент начинает работу с этого файла и двигается только по указанным здесь задачам и правилам.** Обязательное применение закреплено в [AGENTS.md](AGENTS.md). Файл управляет порядком исполнения; он не запускает агентов и не является самостоятельным разрешением на новые действия.

## 1. Где находится источник истины

| Файл | Что определяет |
| --- | --- |
| **PLAN.md** | Порядок выбора задач, правила старта, параллельной работы, блокировок и завершения |
| [docs/TASKS.md](docs/TASKS.md) | Единственный реестр статусов TODO/IN_PROGRESS/BLOCKED/DONE, прямые зависимости, шаги, критерии приёмки и обязательные проверки |
| [docs/TEAM_PLAN.md](docs/TEAM_PLAN.md) | Ответственный A/B, reviewer, границы файлов и передача результатов между участниками |
| [docs/MVP_SCOPE.md](docs/MVP_SCOPE.md) | Граница MVP, P0/P1/P2 и условия выпуска |
| Профильные спецификации | Поведение продукта, API/БД/редактор/графики/модели, безопасность и воспроизводимость |

Никакого второго списка статусов здесь не ведём. Таблица ниже показывает плановый порядок всех 72 задач; актуальную готовность агент всегда проверяет в TASKS.md. Ссылки на архитектуру/пользовательские сценарии не заменяют NI-задачу.

Явные инструкции пользователя имеют приоритет. Если пользователь назначил задачу или изменил scope, отразить это в плане/backlog и выполнить в уже разрешённых границах, без повторного запроса того же разрешения. Нельзя самовольно менять план только ради обхода зависимости или добавления отдельной незаказанной функции.

**Уточнение разрешения — 8 ноября 2026:** пользователь явно поручил текущему агенту выполнять задачи обеих ролей A и B через этот план. Последующее уточнение сохраняет NI-035 и NI-041 за их текущими исполнителями: брать только свободные задачи или явно записанные свободные handoffs; чужие claims не перехватывать. Ограничения scope, данных и приёмки сохраняются.

## 2. Протокол начала каждой рабочей сессии

1. Прочитать AGENTS.md, этот PLAN.md, README.md, MVP_SCOPE.md и TEAM_PLAN.md. Затем прочитать карточку выбранной NI-задачи и её профильные спецификации.
2. Проверить фактическое состояние checkout, незавершённые изменения и статусы TASKS.md. Не принимать историческую фразу «приложение ещё не реализовано» за доказательство текущего состояния после начала разработки.
3. Проверить, разрешён ли текущий вид работы пользователем. Исходное задание требует отдельного запуска реализации после документации; прямое последующее «начинай реализацию/выполни NI-…» является таким разрешением в указанном scope. Повторно просить уже выданное разрешение не нужно. Запрос на изменение документации сам по себе не запускает разработку приложения.
4. Определить роль A/B по назначению пользователя/руководителя. Если отдельная роль не задана и работает один агент, выбрать роль ответственного первой доступной задачи и записать её в claim. Это не создаёт второго агента автоматически.
5. Выбрать первую доступную задачу по правилу ниже. В коротком сообщении указать её ID, результат и основные файлы. Отметить TODO → IN_PROGRESS и записать claim в карточке TASKS.md **до начала её реализации**.
6. Выполнять одну самостоятельную NI-задачу за раз. Второму участнику передавать конкретную часть по согласованному handoff; не объявлять его работу выполненной от его имени.

Наличие этого плана не требует отдельного одобрения каждого обычного шага внутри уже разрешённой задачи. Ограничения на платные запросы, внешние публикации, остановленные сборщики и иные действия продолжают действовать в соответствии с реальными инструкциями пользователя и окружения.

## 3. Как выбрать следующую задачу

**Доступная задача** одновременно удовлетворяет всем условиям:

- Входит в текущий разрешённый scope; для обычного MVP это P0.
- Её Status в TASKS.md — TODO, либо прежний BLOCKED явно снят после изменения условия и подтверждающей проверки.
- Все прямые Dependencies в TASKS.md имеют DONE с проверяемыми результатами. Отсутствие кода зависимости, сомнительное DONE или неисправный интегрированный контракт сначала исправляется в этой зависимости.
- Она соответствует назначенной роли, либо передача ответственности явно зафиксирована в TEAM_PLAN.md и карточке задачи.
- Задача не занята другой сессией/участником, нет конфликта по тем же файлам и получен необходимый входной контракт.

Из доступных задач своей роли брать ту, которая раньше находится в таблице раздела 8. Таблица **не создаёт общего барьера между строками**: A и B могут параллельно выполнять разные готовые задачи, даже если более ранняя строка ещё выполняется другим участником. Зависимости и владение важнее календарной нумерации.

Если задача ранней строки недоступна, можно взять следующую готовую задачу своей роли, зафиксировав причину пропуска. Нельзя реализовывать заблокированную часть «на предположениях» и потом объявлять интеграцию готовой. Изолированные, явно синтетические development fixtures допустимы по существующим правилам, но не закрывают критерии реальных данных/persistence/ownership.

P1 допускается после завершения и проверки всех P0 и только в разрешённом scope. P2 — после P0 и явного включения соответствующей функции в scope. Законченные собственные P0 при незавершённых P0 другой роли — повод помочь в согласованной части, review или устранении блокировки; не повод самовольно переходить к P1/P2.

Если доступных задач нет, сообщить точный blocker и необходимые входные данные. Не выдумывать новую независимую функцию, не обходить отсутствие данных фиктивной метрикой и не ставить DONE ради продолжения.

## 4. Claim, статусы и handoff

Статус хранится в существующем поле **Status** карточки TASKS.md. При старте добавить под ним фактические execution metadata, без фиктивных значений:

```text
- **Claimed by:** <agent/session identifier>
- **Execution role:** A или B
- **Started at:** <ISO-8601 с timezone>
- **Branch/worktree:** <реальное имя/путь, если используется>
- **Handoff:** <конкретная часть, исполнитель и входной контракт, если требуется>
```

При завершении дополнить:

```text
- **Verification:** <фактические команды/проверки и результат>
- **Result:** <изменённые модули и наблюдаемое поведение>
- **Reviewer:** <реальный reviewer/статус review, если требуется для приёмки>
- **Completed at:** <фактическое время после выполнения критериев>
```

- TODO → IN_PROGRESS: задача выбрана, зависимости проверены, claim свободен.
- IN_PROGRESS → BLOCKED: реальное условие мешает завершить; указать причину, затронутые критерии и условие разблокировки. Это статус backlog, а не команда остановки всего проекта.
- BLOCKED → IN_PROGRESS: condition изменилось, записаны доказательства; claim подтверждён владельцем или передача зафиксирована.
- IN_PROGRESS → DONE: выполнены **все** критерии и проверки исходной задачи, включая обе технические части при handoff.
- DONE → IN_PROGRESS: обнаружен конкретный дефект её критериев; записать причину повторного открытия, пересмотреть затронутые зависимости. Не удалять предыдущие результаты проверок.

Чужой IN_PROGRESS не перехватывать по одному возрасту записи. Сначала согласовать передачу через доступную координацию или пользователя; можно продолжать независимую доступную задачу. В разных checkout claims/контракты синхронизируются перед стартом через общий процесс Git/review. Пока Git ещё не создан, участники явно координируют записи и не правят один файл одновременно. Markdown сам по себе не является атомарной блокировкой.

## 5. Границы изменения файлов и контрактов

A отвечает за web/UI, JS-рендер графиков, browser-тесты и согласованную упаковку; B — за API/Python/БД/метрики/модели. Детальные назначения — в TEAM_PLAN.md. Один человек может помогать во второй зоне только в рамках явно согласованной части текущей задачи.

Обязательные стыки: Pydantic/OpenAPI → generated TS; canonical ChartView → ECharts; document JSON/revision/pins → Tiptap; frozen export IR → static charts/ZIP; fixed model manifest → public results. Не создавать параллельную реализацию того же определения или схемы. Изменение контракта сначала документировать/проверить с потребителем; после — обновлять обе стороны и генерацию.

Разрешены только изменения, нужные для критериев текущей задачи, её проверки и согласованного handoff. Небольшую выявленную ошибку в её границах исправить и проверить. Независимую новую работу сначала оформить отдельной NI-задачей с приоритетом, зависимостями, ролью и приёмкой; обновить этот план и TEAM_PLAN.md. Основание изменения scope должно быть записано. При действующем указании пользователя не просить повторно разрешение на уже заказанное изменение.

Нельзя помечать P0 готовым, подменяя реальную метрику похожим показателем, источник тестовой фикстурой, проверку владельца UI-фильтром или результат модели выдуманным коэффициентом. Архивные данные не становятся live от кнопки Refresh.

## 6. Минимальный результат перед следующим заданием

Перед DONE проверить исходную карточку TASKS.md, необходимые контракты и затронутые тесты; не применять необоснованно все проверки ко всем типам изменений. Для соответствующих задач обязательны owner-isolation, финансовая точность, version pins, воспроизводимость, доступность и реальные интеграционные проверки.

Обновить статусы/claim, спецификации при изменении контракта, README при изменении команд и DECISIONS при архитектурном решении. В сообщении о результате назвать NI-ID, выполненное поведение, фактические проверки и оставшиеся ограничения. Только после этого выбирать следующую доступную задачу.

План/документация не заменяют работающий продукт. Рисунок, пустой маршрут, успешная HTTP200 или файл без проверок не считаются доказательством выполнения полной задачи.

## 7. Текущая точка входа

На момент создания этого плана все 72 NI-задачи имеют TODO. Это датированный исходный факт, а не обновляемый реестр статусов. При будущем старте перечитать TASKS.md и проверить код.

После разрешённого запуска реализации первая задача — **NI-001, роль A**. После её DONE могут идти параллельно **NI-002, роль A с API-handoff B**, и **NI-026, роль B**. У одного участника B эти части не исполняются одновременно: handoff и проверка источников планируются явно. Следующие NI-003/NI-004 требуют NI-002 DONE. Не начинать NI-026 сетевыми/платными запросами без соответствующего доступа и разрешения; его офлайн/документальную часть можно выполнить в разрешённых пределах, сохранив незакрытые критерии.

## 8. Упорядоченный реестр исполнения

Последовательность вычислена из прямых зависимостей TASKS.md; проверка источников NI-026 вынесена в начало после NI-001. Приоритет и роль показаны для ориентации и обязаны совпадать с TASKS/TEAM_PLAN. Статусов в этой таблице нет. После изменения зависимостей, состава задач или назначения обновить таблицу и проверить отсутствие циклов/пропусков.

| Порядок | Задача | Результат / название карточки | Приоритет | Ответственный |
| --- | --- | --- | --- | --- |
| 01 | [NI-001](docs/TASKS.md) | Initialize repository and pin tooling | P0 | A |
| 02 | [NI-026](docs/TASKS.md) | Verify provider capability, entitlement and rights | P0 | B |
| 03 | [NI-002](docs/TASKS.md) | Create web and API runtime skeletons | P0 | A |
| 04 | [NI-003](docs/TASKS.md) | Create database roles and initial schema migrations | P0 | B |
| 05 | [NI-004](docs/TASKS.md) | Establish OpenAPI generation and typed clients | P0 | B |
| 06 | [NI-005](docs/TASKS.md) | Add baseline CI and developer checks | P0 | A |
| 07 | [NI-006](docs/TASKS.md) | Implement design tokens and typography | P0 | A |
| 08 | [NI-007](docs/TASKS.md) | Build accessible interaction primitives | P0 | A |
| 09 | [NI-008](docs/TASKS.md) | Create public and workspace layout shells | P0 | A |
| 10 | [NI-009](docs/TASKS.md) | Build common data and async states | P0 | A |
| 11 | [NI-010](docs/TASKS.md) | Create chart frame and source drawer | P0 | A |
| 12 | [NI-011](docs/TASKS.md) | Create public editorial routes and mechanism section | P0 | A |
| 13 | [NI-016](docs/TASKS.md) | Configure managed authentication environment | P0 | A |
| 14 | [NI-017](docs/TASKS.md) | Implement same-origin login and cookie lifecycle | P0 | A |
| 15 | [NI-018](docs/TASKS.md) | Verify JWT and bootstrap application principal | P0 | B |
| 16 | [NI-019](docs/TASKS.md) | Enforce request-scoped ownership and RLS | P0 | B |
| 17 | [NI-020](docs/TASKS.md) | Verify authentication recovery and session boundaries | P0 | A |
| 18 | [NI-021](docs/TASKS.md) | Protect workspace routes and shell | P0 | A |
| 19 | [NI-022](docs/TASKS.md) | Implement owner-scoped home aggregation API | P0 | B |
| 20 | [NI-025](docs/TASKS.md) | Implement profile and minimal settings | P0 | A |
| 21 | [NI-027](docs/TASKS.md) | Import existing archives read-only | P0 | B |
| 22 | [NI-028](docs/TASKS.md) | Implement immutable dataset staging and publication | P0 | B |
| 23 | [NI-029](docs/TASKS.md) | Implement exact metric computations and quality | P0 | B |
| 24 | [NI-030](docs/TASKS.md) | Add one bounded scheduled refresh adapter | P0 | B |
| 25 | [NI-031](docs/TASKS.md) | Define versioned chart and metric registries | P0 | B |
| 26 | [NI-032](docs/TASKS.md) | Deliver metrics, chart views and source APIs | P0 | B |
| 27 | [NI-033](docs/TASKS.md) | Implement reusable interactive ECharts renderer | P0 | A |
| 28 | [NI-012](docs/TASKS.md) | Bind landing to approved findings and metrics | P0 | A |
| 29 | [NI-034](docs/TASKS.md) | Build chart library and detail navigation | P0 | A |
| 30 | [NI-015](docs/TASKS.md) | Deliver public analytics explorer | P0 | A |
| 31 | [NI-035](docs/TASKS.md) | Persist saved chart instances | P0 | B |
| 32 | [NI-036](docs/TASKS.md) | Implement canonical document schema and revision service | P0 | B |
| 33 | [NI-037](docs/TASKS.md) | Implement document CRUD and version endpoints | P0 | B |
| 34 | [NI-023](docs/TASKS.md) | Build My Research and recent-item views | P0 | A |
| 35 | [NI-024](docs/TASKS.md) | Build research-focused workspace Home | P0 | A |
| 36 | [NI-038](docs/TASKS.md) | Prototype Tiptap custom block integration | P0 | A |
| 37 | [NI-039](docs/TASKS.md) | Build editor layout and block operations | P0 | A |
| 38 | [NI-040](docs/TASKS.md) | Implement autosave, manual save and conflict recovery | P0 | A |
| 39 | [NI-041](docs/TASKS.md) | Implement Add Chart to owned research | P0 | B |
| 40 | [NI-042](docs/TASKS.md) | Complete interactive chart node behavior | P0 | A |
| 41 | [NI-043](docs/TASKS.md) | Freeze resolved evidence on every document revision | P0 | B |
| 42 | [NI-046](docs/TASKS.md) | Define structured insight and evidence node contracts | P0 | B |
| 43 | [NI-047](docs/TASKS.md) | Persist context-preserving chart insights | P0 | B |
| 44 | [NI-048](docs/TASKS.md) | Implement hypothesis blocks and assessments | P0 | B |
| 45 | [NI-049](docs/TASKS.md) | Implement evidence relationships and classifications | P0 | B |
| 46 | [NI-050](docs/TASKS.md) | Build evidence navigation and research context panels | P0 | A |
| 47 | [NI-051](docs/TASKS.md) | Implement model dataset readiness gate | P0 | B |
| 48 | [NI-013](docs/TASKS.md) | Publish methodology and reproduction content | P0 | A |
| 49 | [NI-014](docs/TASKS.md) | Create public thesis with claim registry | P0 | A |
| 50 | [NI-052](docs/TASKS.md) | Implement fixed deterministic econometric estimator | P0 | B |
| 51 | [NI-053](docs/TASKS.md) | Generate diagnostics, robustness and interpretation artifacts | P0 | B |
| 52 | [NI-054](docs/TASKS.md) | Publish reproducible model artifacts and APIs | P0 | B |
| 53 | [NI-056](docs/TASKS.md) | Create frozen document export representation | P0 | B |
| 54 | [NI-057](docs/TASKS.md) | Render static chart assets from frozen contexts | P0 | A |
| 55 | [NI-058](docs/TASKS.md) | Deliver Markdown ZIP export jobs and download | P0 | B |
| 56 | [NI-061](docs/TASKS.md) | Add business/data integration regression suite | P0 | B |
| 57 | [NI-062](docs/TASKS.md) | Complete adversarial ownership and security audit | P0 | B |
| 58 | [NI-063](docs/TASKS.md) | Verify complete research workflow end to end | P0 | A |
| 59 | [NI-064](docs/TASKS.md) | Verify accessibility, responsiveness and performance | P0 | A |
| 60 | [NI-066](docs/TASKS.md) | Package portable local and production runtimes | P0 | A |
| 61 | [NI-067](docs/TASKS.md) | Deploy staging and production with safe configuration | P0 | A |
| 62 | [NI-068](docs/TASKS.md) | Verify backups, restore and operational monitoring | P0 | A |
| 63 | [NI-070](docs/TASKS.md) | Finalize and publish original research release | P0 | A |
| 64 | [NI-069](docs/TASKS.md) | Run hackathon demo and reviewer reproduction | P0 | A |
| 65 | [NI-044](docs/TASKS.md) | Add explicit snapshot management UX | P1 | B |
| 66 | [NI-045](docs/TASKS.md) | Implement template and public research duplication | P1 | B |
| 67 | [NI-055](docs/TASKS.md) | Add model-result block to private research | P1 | A |
| 68 | [NI-059](docs/TASKS.md) | Implement PDF export from frozen representation | P1 | A |
| 69 | [NI-071](docs/TASKS.md) | Add advanced supported analytical filters | P1 | A |
| 70 | [NI-072](docs/TASKS.md) | Add lightweight private research organization | P1 | B |
| 71 | [NI-060](docs/TASKS.md) | Design revocable read-only sharing | P2 | B |
| 72 | [NI-065](docs/TASKS.md) | Plan advisory integrity checks and optional AI tools | P2 | A |

## 9. Изменение самого плана

**Уточнение — 8 ноября 2026:** пользователь поручил исправить три замечания ревью NI-035/NI-041 и явно отменил независимую приёмку для этих двух задач. После исправлений и проверок агент может закрыть их без второго reviewer. Это исключение не относится к остальным NI-задачам и не поручает слияние PR.

**Назначение — 8 ноября 2026:** пользователь разрешил этому агенту выполнять задачи обеих ролей A/B, затем явно передал NI-035 и NI-041 с продолжением сохранённого кода. Выполнять их последовательно (NI-035 первой), сохраняя исходную приёмку и независимое review. Последнее поручение отменяет прежнее указание оставлять эти два claims у других исполнителей.

Этот файл — рабочая дисциплина, а не запрет на осмысленные решения. Исправление зависимостей/обнаруженной ошибки допускается с явным объяснением и синхронным обновлением связанных документов. Отдельная новая функция требует основания в текущем поручении пользователя; её нельзя легализовать незаметной правкой PLAN.md.

При конфликте между планом, критериями или фактическим кодом агент фиксирует конкретное расхождение и устраняет его в разрешённом scope. Защита данных, проверка владельца и воспроизводимость остаются обязательными. Если конфликт нельзя разрешить имеющимися инструкциями, сообщить его пользователю, продолжая независимую разрешённую работу.
