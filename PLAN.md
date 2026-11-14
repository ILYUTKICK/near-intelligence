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

Никакого второго списка статусов здесь не ведём. Таблица ниже показывает плановый порядок задач. Актуальную готовность агент проверяет в TASKS.md. Ссылки на архитектуру и пользовательские сценарии не заменяют NI-задачу.

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

- Входит в текущий разрешённый scope: с 12 ноября 2026 все зарегистрированные P0/P1/P2 включены в выпуск; конкретные зависимости и claims сохраняются.
- Её Status в TASKS.md — TODO, либо прежний BLOCKED явно снят после изменения условия и подтверждающей проверки.
- Все прямые Dependencies в TASKS.md имеют DONE с проверяемыми результатами. Отсутствие кода зависимости, сомнительное DONE или неисправный интегрированный контракт сначала исправляется в этой зависимости.
- Она соответствует назначенной роли, либо передача ответственности явно зафиксирована в TEAM_PLAN.md и карточке задачи.
- Задача не занята другой сессией/участником, нет конфликта по тем же файлам и получен необходимый входной контракт.

Из доступных задач своей роли брать ту, которая раньше находится в таблице раздела 8. Таблица **не создаёт общего барьера между строками**: A и B могут параллельно выполнять разные готовые задачи, даже если более ранняя строка ещё выполняется другим участником. Зависимости и владение важнее календарной нумерации.

Если задача ранней строки недоступна, можно взять следующую готовую задачу своей роли, зафиксировав причину пропуска. Нельзя реализовывать заблокированную часть «на предположениях» и потом объявлять интеграцию готовой. Изолированные, явно синтетические development fixtures допустимы по существующим правилам, но не закрывают критерии реальных данных/persistence/ownership.

**Указание владельца — 12 ноября 2026:** выполнить все шесть P1 (NI-044/045/055/059/071/072) и обе P2 (NI-060/065) до финальной локальной приёмки и деплоя. Выбирать их после готовности собственных прямых prerequisites, не ждать NI-067/068/069 или общего NI-079: они выполняются позже. Это отменяет прежний глобальный барьер «все P0 DONE до P1/P2». Приоритеты P1/P2 сохраняются; зависимость release-gate NI-079 от этих карточек обязательна и является явным исключением старого правила о P0→P1/P2. Новые незарегистрированные направления не добавляются автоматически.

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

**Передача накопленных исправлений — 14 ноября 2026:** пользователь поручил закоммитить всю локальную пачку NI-080–086 для продолжения другим агентом. Прежний запрет Git снят для этой передачи; упаковка, push рабочей ветки и проверки выполняются как завершающая часть NI-080. [Актуальный handoff](docs/LOCAL_CORRECTIONS_HANDOFF.md) описывает состав пачки и границы продолжения. Это не разрешение на merge, deployment или публикацию исходных исследовательских данных.

**Актуальное поручение — 12 ноября 2026: завершить все зарегистрированные P0/P1/P2; сохранить почти готовый desktop-дизайн, устранить конкретные проблемы и добиться работающих локально графиков; затем полностью проверить интегрированную версию и только после этого размещать.** Порядок и обязательный барьер перед размещением — в разделе 10; задание для передачи агенту — [docs/FINISH_BEFORE_DEPLOY_PROMPT.md](docs/FINISH_BEFORE_DEPLOY_PROMPT.md). Это актуальная точка входа вместо исторического старта с NI-001. Статусы остаются только в TASKS.md.

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
| 61 | [NI-070](docs/TASKS.md) | Finalize and publish original research release | P0 | A |
| 62 | [NI-075](docs/TASKS.md) | Integrate the NI-074 desktop design into the working application | P0 | A |
| 63 | [NI-076](docs/TASKS.md) | Run PR #87 locally and review its desktop design against NI-074 | P0 | A |
| 64 | [NI-077](docs/TASKS.md) | Record finish-local-verify-deploy handoff | P0 | A |
| 65 | [NI-078](docs/TASKS.md) | Complete desktop research and chart presentation | P0 | A |
| 66 | [NI-044](docs/TASKS.md) | Add explicit snapshot management UX | P1 | B |
| 67 | [NI-045](docs/TASKS.md) | Implement template and public research duplication | P1 | B |
| 68 | [NI-055](docs/TASKS.md) | Add model-result block to private research | P1 | A |
| 69 | [NI-059](docs/TASKS.md) | Implement PDF export from frozen representation | P1 | A |
| 70 | [NI-071](docs/TASKS.md) | Add advanced supported analytical filters | P1 | A |
| 71 | [NI-072](docs/TASKS.md) | Add lightweight private research organization | P1 | B |
| 72 | [NI-060](docs/TASKS.md) | Implement revocable read-only sharing | P2 | B |
| 73 | [NI-065](docs/TASKS.md) | Implement advisory integrity checks and optional AI tools | P2 | A |
| 74 | [NI-080](docs/TASKS.md) | Repair workspace navigation and email-label demo entry | P0 | A |
| 75 | [NI-081](docs/TASKS.md) | Redesign the public methodology reading experience | P0 | A |
| 76 | [NI-082](docs/TASKS.md) | Audit and design the long-history evidence extension | P0 | B |
| 77 | [NI-083](docs/TASKS.md) | Implement interactive long-history research and exact descriptive calculations | P0 | A with B |
| 78 | [NI-084](docs/TASKS.md) | Record the Blog and research-publication product direction | P1 | A |
| 79 | [NI-085](docs/TASKS.md) | Implement the public Blog and research-publication catalog | P1 | A |
| 80 | [NI-086](docs/TASKS.md) | Implement the approved editorial Overview design | P1 | A |
| 81 | [NI-087](docs/TASKS.md) | Present the complete investment thesis and simplify the chart library | P0 | A |
| 82 | [NI-088](docs/TASKS.md) | Explain the research workflow and simplify chart details | P0 | A |
| 83 | [NI-089](docs/TASKS.md) | Recover the current local preview and retain article edits | P0 | A |
| 84 | [NI-090](docs/TASKS.md) | Prepare the current release for an owner-supplied VPS and domain | P0 | A |
| 85 | [NI-079](docs/TASKS.md) | Pass final integrated local release acceptance | P0 | A |
| 86 | [NI-067](docs/TASKS.md) | Deploy staging and production with safe configuration | P0 | A |
| 87 | [NI-068](docs/TASKS.md) | Verify backups, restore and operational monitoring | P0 | A |
| 88 | [NI-069](docs/TASKS.md) | Run hackathon demo and reviewer reproduction | P0 | A |
| 89 | [NI-098](docs/TASKS.md) | Explain the product and document reproducible self-hosting | P0 | A |

## 9. Изменение самого плана

**Поручение пользователя — 11 ноября 2026:** внедрить согласованное desktop-направление NI-074 отдельной задачей NI-075. Сохранить актуальные сценарии приложения, полный публичный тезис, контракты данных и границы эксплуатации. Работа по NI-075 разрешена независимо от незавершённых эксплуатационных задач. Слияние PR остаётся за владельцем.

**Последнее указание пользователя — 8 ноября 2026 (передача другому агенту):** продолжить оставшиеся NI-задачи, исключив мобильную разработку, мобильную адаптацию и mobile/touch/phone/tablet QA из текущего scope. Проверять desktop, клавиатуру, доступность данных, persistence, ownership и воспроизводимость; не тратить прогоны/скриншоты на мобильные viewport/device. Существующий мобильный код и прошлые доказательства не удалять. Соответствующая часть NI-064 и release checklist обновлена по прямому поручению пользователя. **PR сливает только пользователь:** прежнее разрешение агенту на merge отменено, включая auto-merge; агент готовит код, checks, review и PR, затем оставляет слияние пользователю. Разрешение реализации A/B и поручение использовать субагентов по NI-задачам сохраняются. Текущая передача: [промпт продолжения](docs/CONTINUATION_PROMPT.md).

**Историческое разрешение слияний — 8 ноября 2026 (отменено последним указанием выше):** пользователь прямо разрешил координатору самостоятельно сливать готовые PR после успешного CI и зафиксированного review либо явной отмены review пользователем. Все PR направлять в актуальную main; не сливать последующую задачу в уже слитую прежнюю stacked-базу. Зависимости и независимые проверки остальных задач сохраняются.

**Последнее указание пользователя — 9 ноября 2026:** задачи ролей A и B выполнять параллельно, каждую через отдельного субагента. Независимое ревью завершённых задач вторым агентом отменено: приёмку выполняет координатор — реальные проверки, обязательные gates, CI на последнем коммите и фактические результаты в карточке. В карточках задач, закрытых без независимого ревью, явно отмечать «independent review skipped by user instruction 2026-11-09». Все остальные границы (claims, зависимости, данные, merge только пользователем) сохраняются.

**Последовательное поручение — 8 ноября 2026:** пользователь поручил выполнить оставшиеся P0-задачи по порядку и явно вызывать субагентов для задач. Codex координирует отдельного исполнителя для каждого NI-ID, соблюдает реальные dependencies/claims и исходную приёмку. Начать с завершения NI-012, восстановить доставку готовой NI-041 в main, затем выбирать доступные P0 по таблице. Это не снимает ограничений на провайдеры, сбор данных, расходы и облачное размещение; P1/P2 остаются отложены до завершения P0.

**Уточнение — 8 ноября 2026:** пользователь поручил исправить три замечания ревью NI-035/NI-041 и явно отменил независимую приёмку для этих двух задач. После исправлений и проверок агент может закрыть их без второго reviewer. Это исключение не относится к остальным NI-задачам и не поручает слияние PR.

**Назначение — 8 ноября 2026:** пользователь разрешил этому агенту выполнять задачи обеих ролей A/B, затем явно передал NI-035 и NI-041 с продолжением сохранённого кода. Выполнять их последовательно (NI-035 первой), сохраняя исходную приёмку и независимое review. Последнее поручение отменяет прежнее указание оставлять эти два claims у других исполнителей.

Этот файл — рабочая дисциплина, а не запрет на осмысленные решения. Исправление зависимостей/обнаруженной ошибки допускается с явным объяснением и синхронным обновлением связанных документов. Отдельная новая функция требует основания в текущем поручении пользователя; её нельзя легализовать незаметной правкой PLAN.md.

При конфликте между планом, критериями или фактическим кодом агент фиксирует конкретное расхождение и устраняет его в разрешённом scope. Защита данных, проверка владельца и воспроизводимость остаются обязательными. Если конфликт нельзя разрешить имеющимися инструкциями, сообщить его пользователю, продолжая независимую разрешённую работу.


**Прямое поручение — 11 ноября 2026 (проверка PR):** пользователь попросил локально развернуть свежий PR и оценить дизайн. NI-076 проверяет PR #87, exact head 0b80bf2, в отдельной копии и выдаёт рабочий локальный просмотр и отчёт относительно NI-074. Это проверка, без автоматического внедрения новых правок, удалённого размещения, слияний или сбора данных.

## 10. Завершение до размещения — обязательный порядок

По прямому уточнению пользователя 12 ноября 2026 (заменяет ограничение передачи 11 ноября только MVP):

1. **Завершение продукта.** Проверить актуальный код и claims; закрыть все зарегистрированные P0/P1/P2, включая NI-044/045/055/059/071/072 и рабочие NI-060/065, а также NI-078 (точечные исправления/графики по NI-076). Почти готовый дизайн NI-075 — основа, новый редизайн не требуется. Графики должны работать локально от источника/API до сохранения, snapshots, модели, сравнения и Markdown/PDF. Мобильный scope и незарегистрированные направления не добавляются. Чужой NI-064 IN_PROGRESS сохраняется за исполнителем до явного handoff.
2. **Локальная приёмка итоговой версии — NI-079.** После интеграции исправлений выполнить полный применимый локальный прогон на production-сборке и реальных web/API/DB/worker. Проверить данные/модель, два пользователя, весь research→export workflow, ошибки, desktop UI/клавиатуру, контейнерный запуск и восстановление. Зафиксировать commit, дерево исходников/локальный diff, версии, входы, команды, результаты и screenshots в одном отчёте. Синтетические E2E не заменяют настоящие исследовательские результаты. Незакрытый обязательный P0/P1/P2/graph/data/model gate означает BLOCKED, а не «готово к деплою».
3. **Размещение — NI-067 только после NI-079 DONE.** Локальная приёмка должна соответствовать фактически разворачиваемому коду; последующие изменения требуют проверки затронутых частей и обновления отчёта. До этого можно готовить конфигурацию и runbook, но нельзя выполнять удалённый rollout или включать облачный scheduler. Бюджет/домен/доступ/разрешение на платные ресурсы проверяются по действующим границам; этот документ не создаёт разрешения на расходы. PR сливает пользователь.
4. **Проверки окружения после размещения.** NI-067 проверяет staging, конечный TLS origin, настоящие callbacks/cookies и production smoke; NI-068 — удалённые backups/restore/monitoring; NI-069 — deployed demo и judge reproduction. Эти проверки невозможно объявить пройденными локально. Полный release DONE только после них; требование «все P0 DONE до NI-067» не применяется к самим NI-067/068/069.

NI-077 оформляет передачу и её уточнение 12 ноября; он не запускает реализацию или размещение в текущей сессии. Агент-исполнитель берёт NI-задачи по актуальным claims и исходной приёмке. При внешнем blocker продолжает независимую разрешённую работу и сообщает точные недостающие входы; не снижает gates.

**Уточнение scope — 12 ноября 2026:** владелец остановил передачу «только MVP» и потребовал выполнить все P1/P2 до деплоя, с приоритетом работающего локального продукта и графиков. NI-060 и NI-065 переведены из design/plan-only в implement-and-test; подробная приёмка — TASKS и FEATURE_SPECIFICATIONS. Это расширяет существующие восемь карточек, но не включает отдельные CRDT/portfolio/multichain/billing или платные сервисы. Старые указания об отсрочке P1/P2 в разделе 9 — история и заменены этим уточнением. Принимающий агент исполняет расширенную передачу; текущая NI-077 остаётся документационной.

**Owner correction batch — 13 November 2026:** NI-080 implements the first cabinet-feedback batch (remove Home Data context, retain workspace explorer/chart navigation, usable email-label demo entry). It precedes NI-079 and replaces the older public-route-only sidebar choice for these journeys. Email labels do not establish identity; demo ownership remains isolated. No data collection or cloud rollout is added.

**Local public-page review — 13 November 2026:** owner requests a proper reader-facing methodology design (NI-081) and explicitly defers Git commits, pushes and PR publication while collecting local corrections. NI-080 local acceptance is preserved; its publication waits for this hold to end. NI-081 may proceed after its own DONE dependencies without claiming NI-079 or remote readiness.

**NI-081 follow-up — 13 November 2026:** owner removes all methodology-page technical disclosures together with their contents. Keep the public explanatory article and honest limits; preserve the detailed records internally. This replaces the prior on-page appendix design. Continue local-only, without Git publication.

**Long-term thesis evidence — 13 November 2026:** owner requests more historical depth beyond the 90-day cohort. NI-082 first audits saved history and defines the comparable extension/protocol. It grants no new bulk collection, paid/cloud/API-key access, collector restart or Git publication. Existing long-run readiness and revenue/attribution gates remain intact.

**Interactive history implementation — 14 November 2026:** the owner explicitly requests interactive research charts and corrected calculations after NI-082. NI-083 implements that local scope using saved real inputs, exact descriptive calculations and the shared ECharts renderer. Preserve existing pinned 90-day evidence and model gates. No new collection or Git publication is authorized; NI-079 must include this local batch.

**Research publication direction — 14 November 2026:** the owner wants the public product to grow into a collection of research articles with a separate Blog page and asks to anchor this in the project. NI-084 records that decision and implementation brief only. The existing full research is the first publication; further articles/updates build on it. Blog routes, CMS, automatic publishing and daily data collection are not implemented or started by this documentation task. Existing workspace/data/reproducibility requirements and the Git hold remain in force.

**Blog implementation — 14 November 2026:** the owner explicitly says to implement the recorded direction. NI-085 adds the public catalog/navigation and reusable publication routing/content organization, with the existing full research as its first real article. Preserve `/research` and all evidence anchors, source/metric/chart identities and private boundaries. No invented extra articles/metadata, CMS dependency, external publication, new data collection or Git mutation. This local batch is included in NI-079 before deployment.

**Approved Overview — 14 November 2026:** owner approved the generated editorial Overview mockup and explicitly requests implementation through NI-086. Replace the old thesis-heavy landing presentation with the approved hero, one real featured research card, three data-exploration links, reader workflow, methodology band and workspace CTA. This supersedes NI-012's on-Overview metric/claim-table presentation only; preserve the real data services, full research/evidence/model status and existing documented deep links through compatible destinations. No fake KPIs, live claims, automatic data refresh or Git publication. Include NI-086 in NI-079 local acceptance.


## Explicit local-preview recovery — 14 November 2026

NI-089 (role A), requested by the owner: restore the current Blog/Overview experience after this chat used the obsolete localhost:13000 review stack. The current source is near-deploy at 13e9d0c and the current local preview is localhost:13002. Preserve the NI-085–088 design and behavior; carry over only source-qualified article copy/quiet metadata, fix missing local static assets if confirmed, and verify desktop Overview→Blog→article. No external deployment, database migration, provider collection or takeover of NI-088. Status/acceptance live in TASKS.md.


**Owner instruction — 14 November 2026, VPS preparation:** prepare the current Blog/Overview release for the existing VPS and near-intelligence.me. NI-090 covers repository configuration, explicit environment validation, HTTPS proxy, backup/recovery/export-worker tooling, a reproducible source handoff and local disposable verification. No remote login, provisioning, DNS mutation, public rollout or source collection is requested yet. Preparation may proceed under DEPLOYMENT.md without closing NI-079; NI-067/068 retain real remote acceptance and missing data/model gates remain explicit.


**Owner request — 14 November2026, README and self-hosting:** NI-098 rewrites the reader-facing product overview and documents a complete reproducible local/own-domain deployment using existing packaging. Accurately describe authoring, curated public publication and search/AI discoverability intent; do not invent an AI thesis generator, guaranteed indexing, public data bundle or a new deployment capability. Documentation may proceed directly after its DONE dependencies; no remote rollout or new collection is authorized.
