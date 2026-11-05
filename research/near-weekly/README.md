# Семидневная сверка NEAR Intents

Актуальные числовые выводы и ограничения — в [FINDINGS.md](FINDINGS.md).

Период: 27 октября–2 ноября 2026 UTC. Все обращения read-only. Ключей и платежей нет.

Основные результаты:

- `data/reconciliation.csv`: точная сверка балансов и явные MATCH/UNCHECKED/MISMATCH.
- `data/native_payout_audit.csv`: соответствия событий вывода и успешных переводов.
- `data/collection_status.json`: текущее состояние публичного сборщика.
- `data/snapshots_missing.json`: недостающие независимые снимки.
- `manifest.json`: происхождение данных и контрольные суммы.

Повторный локальный расчёт из уже сохранённых данных:

```bash
python3 research/near-weekly/scripts/reconcile.py
python3 research/near-weekly/scripts/audit_native_quality.py
python3 research/near-weekly/scripts/render_report.py
python3 research/near-weekly/scripts/update_manifest.py
```

Сборщик `scripts/complete_public.py` использует по одному запросу с интервалом не менее 30 секунд и соблюдает Retry-After. Возобновляется из кэша. Останавливается после полной сверки, при ошибке, отсутствии прогресса или появлении локального файла `data/STOP_PUBLIC_COLLECTION`. Скрипт не отправляет уведомлений или сообщений кому-либо.

Файл `PROVIDER_QUESTIONS.md` — неотправленный черновик вопросов по пяти несовпавшим intent-хешам.

## Анализ конвертаций и происхождения поступлений

Результат 4 ноября: [analysis/CONVERSION_FINDINGS.md](analysis/CONVERSION_FINDINGS.md). Офлайн-воспроизведение: `python3 research/near-weekly/scripts/analyze_conversions.py`.
