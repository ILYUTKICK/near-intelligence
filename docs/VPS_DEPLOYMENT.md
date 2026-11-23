# VPS: near-intelligence.me

**Текущий релиз — 23 ноября 2026, NI-102:** merged main
`c111d6ed7f7181da1cffd559114a3ba3d8b33b14`, Comic Lab/Unslop NI-099–101.
`/opt/near-intelligence` →
`/opt/near-releases/20261123T110835Z-439128d3568dcb6a`.
База, секреты, Caddy и тома сохранены; миграции/импорт/сбор данных не запускались.
Backup перед обновлением, совместимость, финальные HTTPS/auth/chart проверки
и границы отката: [отчёт NI-102](verification/ni-102.md).
Ниже сохранены исходный runbook и датированная история NI-067.

Подготовка NI-090, 14 ноября 2026. Исходники: актуальный `near-deploy`, включая
восстановленный Overview, Blog и редактуру статьи NI-089. Это инструкция для
существующего VPS; сервер, DNS, Supabase и публичный сайт пока не изменялись.
Фактические проверки подготовки записаны в [отчёте NI-090](verification/ni-090.md).

**Выпуск остаётся за NI-079 → NI-067 → NI-068.** NI-079 принят владельцем и имеет
DONE в актуальном main. NI-067 выполняет реальное размещение; фактические результаты
и оставшиеся проверки записываются в [отчёт NI-067](verification/ni-067.md).
Перенос контейнеров сам по себе не закрывает проверки конечного HTTPS-origin,
входа, данных, экспорта и восстановления. Исторический отчёт NI-090 описывает
состояние подготовки, а TASKS.md содержит актуальные статусы.

## Что приготовлено

[Отдельный Compose](../deployment/vps/compose.yaml) запускает PostgreSQL18,
FastAPI, Next.js и Caddy. В интернет опубликованы только TCP80/443 прокси.
Все запросы, включая `/api/*`, идут через Next.js gateway; FastAPI и БД не имеют
портов хоста. Caddy обслуживает только `near-intelligence.me`, выпускает и
обновляет TLS после настройки DNS. Поддержка `www` не добавлена.

Сервисы получают явные наборы переменных: web без паролей БД, API с near_app,
мигратор только с near_migrator, export-worker с near_app/near_operator.
Bootstrap-пароли нужны только контейнеру БД при первом создании кластера.
Никакие `.env` целиком в web/API не передаются. Миграции — отдельная операция.
Сервисы перезапускаются после рестарта Docker; логи ограничены 3×10MB на сервис.

Тома: `near_db_data` (родитель versioned PG18 cluster), `near_artifacts`
(версионированные файлы данных), `caddy_data` (в том числе приватные TLS-ключи),
`caddy_config`. API читает artifacts; worker имеет запись. ZIP-экспорты и их
зафиксированные планы хранятся в PostgreSQL, поэтому входят в DB dump.
Сборщики выключены, allowlist пуст, бюджеты нулевые; refresh-сервиса/таймера нет.

## Перед началом на сервере

Для последующих установок нужны IP/SSH-алиас, ОС/архитектура и ресурсы VPS.
Фактический сервер14 ноября: DigitalOcean104.248.240.9, Ubuntu24.04 x86_64,
4GB RAM,80GB SSD; текущий релиз и измерения — в отчёте NI-067.
Используйте поддерживаемый Linux с systemd, Python3.12+ и Docker Engine с
Compose v2 (`--wait`, JSON config). Для установки следуйте
[инструкции Docker для своей ОС](https://docs.docker.com/engine/install/).
Размер VPS и диска нужно сверить с фактической БД, артефактами и резервными
копиями; сборка образов требует больше памяти, чем их запуск. Ресурсный замер
этого конкретного сервера ещё не выполнен.

Выделите `/opt/near-intelligence` владельцу `near`, который запускает Docker.
Доступ к Docker эквивалентен административному: это операторский пользователь,
не публичный пользователь приложения. Создайте закрытый каталог
`/var/backups/near-intelligence` с владельцем `near`, правами0700. Сохраните SSH
доступ и разрешите входящие80/443 в firewall провайдера и хоста. Для Docker
учтите [особенности firewall](https://docs.docker.com/engine/network/packet-filtering-firewalls/).
Порты5432/8000/3000 открывать не требуется.

У регистратора направьте A `near-intelligence.me` на IPv4 VPS. AAAA добавляйте
только при работающем IPv6 и открытых портах. Если используется DNS-прокси,
сначала согласуйте его TLS-режим; локально TLS/DNS ещё не проверены.

## Получить точные исходники

Из подготовленного исходного checkout создаётся архив с помощью
[bundle.py](../deployment/vps/bundle.py), а не `git archive HEAD`: последний
потерял бы незакоммиченную редактуру и исправление иллюстрации. Архив содержит
только разрешённые исходники/документацию и явные новые файлы подготовки.
Секреты, `.env.vps`, локальный Compose override, исходные исследовательские
архивы, содержимое БД и private exports не входят. `SOURCE_MANIFEST.json`
перечисляет SHA256 каждого файла и даёт уникальный tag текущего дерева.
Manifest проверяет целостность; подлинность канала передачи обеспечивает SSH.

Перенесите подготовленный архив по SSH и распакуйте в `/opt` (получится
`/opt/near-intelligence`). Не накладывайте архив поверх работающего релиза:
для обновления используйте отдельный каталог кандидата, сохраняя прежние образы
и приватную конфигурацию. Сверьте SHA256 архива с переданным `.sha256`, затем:

```sh
cd /opt/near-intelligence
python3 deployment/vps/verify_source.py
python3 -m unittest discover -s deployment/vps/tests -p 'test_*.py'
```

В Git checkout без `SOURCE_MANIFEST.json` сначала создайте bundle и проверьте
его распакованную копию. Создание нового архива для нового кандидата:

```sh
python3 deployment/vps/bundle.py --output /tmp/near-source.tar.gz
```

## Приватная конфигурация

Создайте файл **на сервере**, не пересылайте его в чат или Git:

```sh
python3 deployment/vps/env.py init --env-file .env.vps --release-tag "$(python3 deployment/vps/verify_source.py --release-tag)"
```

Команда создаёт0600 файл, генерирует шесть независимых секретов и отказывается
перезаписывать существующий файл. В `.env.vps` замените только Supabase placeholders
на параметры выбранного production-проекта: URL без завершающего `/`, browser-safe
publishable/anon key, issuer, JWKS URL, audience `authenticated` и реальный
асимметричный алгоритм signing key. **Service-role/secret key не нужен.**
Не копируйте dev-ключи автоматически. Валидатор проверяет формат/согласованность,
но не подлинность ключа или доступность аккаунта.

В Supabase задайте Site URL `https://near-intelligence.me` и нужные redirect URLs
на этом origin (включая `https://near-intelligence.me/auth/callback` для link flow).
Проверьте email confirmation/recovery/SMTP и, если используете кнопку demo,
Anonymous Sign-Ins. Эти настройки не изменялись подготовкой; подробности в
[auth specification](AUTHENTICATION_SECURITY.md).

```sh
python3 deployment/vps/env.py validate --env-file .env.vps
python3 deployment/vps/env.py check-compose --env-file .env.vps
python3 deployment/vps/ops.py validate
```

Не печатайте `docker compose config` и полный `docker inspect` в публичные логи:
развёрнутая конфигурация содержит пароли. Helper проверяет её в памяти.
Изменение DB passwords в env после создания тома **не меняет пароли ролей в БД**:
ротация — отдельная согласованная SQL-операция и обновление конфигурации.

## Первый запуск после NI-079

Для кандидата с принятой NI-079 проверьте исходники и пройдите релизный
процесс NI-067. Из каталога проекта:

```sh
python3 deployment/vps/ops.py build
python3 deployment/vps/ops.py db
python3 deployment/vps/ops.py migrate
python3 deployment/vps/ops.py up
python3 deployment/vps/ops.py status
python3 deployment/vps/ops.py check
```

`db` создаёт роли только на пустом томе. `migrate` использует отдельную роль,
не запускается при старте HTTP. `up` использует уже собранные образы и поднимает
прокси с реальной выдачей TLS. Не запускайте его ради локального smoke-теста
домена: для этого есть отдельная репетиция ниже.

`check` проверяет DB-доступ, текущую миграцию, доступ к хранилищу и внутренние
маршруты Overview/Blog/Research/иллюстрации. `/health` сам по себе проверяет
конфигурацию, а не полноту данных. Отдельно на реальном HTTPS-origin проверьте
редирект HTTP→HTTPS, сертификат, Secure/HttpOnly/SameSite cookies, CSRF/origin,
login/logout/recovery, Alice/Bob denial и полный save/reopen/export workflow.
Не публикуйте пустой каталог моделей как завершённое исследование.

Данные передаются отдельно по разрешённым manifest/import-командам из
[JUDGE_SETUP](JUDGE_SETUP.md). Source bundle намеренно не содержит raw evidence.
Без подтверждённых прав/входов не подменяйте данные и не включайте сборщики.

## Экспорты и расписание

Проверьте однократно `python3 deployment/vps/ops.py worker` и `sweep`.
Export worker обрабатывает не более10 заданий за запуск, с лимитами lease/timeout.
Он не является непрерывным daemon. После релизного smoke-теста установите
[systemd units](../deployment/vps/systemd/near-exports.service), адаптировав пути
и User/Group, если сервер отличается:

```sh
sudo install -m 0644 deployment/vps/systemd/near-*.service deployment/vps/systemd/near-*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now near-exports.timer near-export-sweep.timer near-backup.timer
systemctl list-timers 'near-*'
```

Таймеры exports/sweep/backup используют один файловый lock по Compose project
в общем закрытом каталоге `/tmp/near-intelligence-vps-<uid>`. Все команды, в том
числе из нового candidate-каталога, запускайте от одного пользователя `near`. Backup дождётся
worker, остановит API/web, снимет БД и artifacts, затем восстановит состояние
запущенных API/web; на это время сайт кратко недоступен. Backup также откажет, если
после сбоя остался работающий one-shot worker/мигратор. Не запускайте пишущие
операторские команды в обход lock во время backup. Расписание не включает
refresh/model/collector. Не прерывайте backup командой `kill -9`; после сбоя
проверьте состояние сервисов. При обслуживании сначала остановите таймеры.

## Резервная копия и восстановление

```sh
python3 deployment/vps/ops.py backup /var/backups/near-intelligence/manual-before-release
```

Новый закрытый каталог содержит `database.dump`, `artifacts.tar`, `backup.json`
с SHA256 и release tag. Существующий каталог не перезаписывается. Неполная или
изменённая копия не восстанавливается. Пароли/env и TLS-ключи в этот комплект
не входят: храните env в менеджере секретов; Caddy volume сохраняйте на сервере,
при disaster recovery сертификат может потребовать повторной выдачи.

Nightly timer создаёт **локальные** копии. Настроить шифрованную внешнюю копию,
retention, свободное место, уведомление об ошибке unit и периодический restore
drill нужно в NI-068. Пока этого нет, потеря диска VPS означает потерю локальных
копий тоже. RPO24h/RTO4h остаются целями, не измеренными гарантиями.

Восстанавливайте только в новый изолированный проект с отдельным именем/томами.
Helper отказывается от in-place restore и существующего целевого тома:

```sh
python3 deployment/vps/ops.py --project near-vps-rehearsal-restore --rehearsal restore /var/backups/near-intelligence/manual-before-release
python3 deployment/vps/ops.py --project near-vps-rehearsal-restore --rehearsal up
python3 deployment/vps/ops.py --project near-vps-rehearsal-restore --rehearsal check
```

Это репетиция без прокси/TLS, без портов хоста, без real auth/provider calls.
После восстановления проверьте конкретные dataset/document pins, artifact hashes
и двух пользователей. Переключение production на восстановленную БД требует
отдельного плана и остановки пишущих процессов; автоматической смены pointer нет.

## Обновление и откат

Остановите таймеры; запишите прежний release tag/образ, сделайте backup,
проверьте expansion-first миграцию и совместимость со старым приложением.
Пройдите новую приёмку, обновите `.env.vps` release tag, соберите образ, примените
рассмотренную миграцию, запустите `up`/`check` и HTTPS smoke. Только после этого
возобновите расписание. Зафиксированные документы/dataset/model artifacts не
перезаписываются.

При доказанной совместимости схемы используйте старые сохранённые образы:

```sh
python3 deployment/vps/ops.py rollback --tag PREVIOUS_VERIFIED_RELEASE_TAG --schema-compatible
```

Замените placeholder реальным прежним tag; команда его валидирует. Она меняет
только api/web images, не выполняет downgrade/удаление томов/откат данных.
После smoke сохраните прежний tag в приватном env перед возобновлением таймеров.
Если миграция несовместима, не делайте автоматический downgrade: используйте
проверенный backup и отдельный recovery plan. Не удаляйте старые образы до
завершения rollback window и не выполняйте `down -v` на production.

## Что ещё требуется для реального запуска

- IP/SSH-алиас, ОС/архитектура/ресурсы VPS и проверка портов/DNS.
- Настройки выбранного production Supabase и final-origin auth/TLS проверки.
- Закрытая приёмка NI-079 с реальными разрешёнными данными и моделью.
- NI-067: фактический rollout; NI-068: offsite backup/restore/monitoring.

Секреты и приватные SSH-ключи в чат не нужны.

## Развёрнуто 14 ноября 2026 — NI-067

Сайт: https://near-intelligence.me. Исполняемый код: свежий main1d5e550 плюс
проверенные исправления fc29502/e1671af (PR103, слияние остаётся владельцу).
`/opt/near-intelligence` указывает на неизменяемый релиз
`/opt/near-releases/20261114T200424Z-f924da0c2859129e`.
Источник конфигурации — его закрытый `.env.vps`; не создавайте новые пароли
поверх действующей БД и не запускайте обычный developer Compose.

Реальные графики и модель перенесены отдельным согласованным research-only
пакетом. Экспорты и локальные ночные бэкапы включены; сбор данных выключен.
Фактические проверки и границы — [NI-067](verification/ni-067.md).
NI-068/069 ещё не объявлены выполненными.
