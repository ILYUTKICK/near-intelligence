# Treasury retention audit

Актуальные выводы: [FINDINGS.md](FINDINGS.md).

Период истории: 5 октября — 3 ноября 2026 UTC. Фиксированный текущий срез: 4 ноября 2026, 11:31:03 UTC.

Офлайн-пересчёт:

```sh
python3 research/near-treasury/scripts/analyze.py
```

История получена публичным FastNear Transactions API, состояния и governance — NEAR RPC. Все первичные ответы сохранены с запросами и timestamps. `fetch_current.py`, `fetch_governance.py`, `fetch_history.py` выполняют ограниченные сетевые чтения; они не нужны для воспроизведения сохранённого анализа. `sql/01_treasury_30d.sql` подготовлен как дополнительная BigQuery-проверка, но не выполнялся.

Нулевая исходящая активность относится к доступному индексу ролей FastNear с исчерпанной пагинацией; стейкинг/lockup не объявляются исчерпывающе проверенными по всем контрактам и сетям.
