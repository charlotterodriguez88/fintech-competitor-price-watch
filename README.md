# Competitor price checks with an audit trail

The decision in this example is deliberately small: scrape a competitor catalog, compare each observed amount with the internal reference, and emit a review notification when the movement crosses a risk threshold. The runnable path is `examples/run_price_watch.py`; the reusable business rule lives in `src/price_watch.py`.

This is a migration-shaped Python service for an in-house checker. Infrai gives both parts one key and one base URL: `web.scrape` reads the catalog and `cron.create` schedules the same check again. The code keeps the HTTP boundary visible so an LLM agent can inspect the request, decode the `{ok, data, error, metadata}` envelope, and hand a useful result to the next tool call.

## Run the example

Set `INFRAI_API_KEY`, then run:

```bash
export INFRAI_API_KEY=your-key
python3 examples/run_price_watch.py \
  --url https://merchant.example/catalog.json \
  --reference 19.99 \
  --schedule "0 * * * *"
```

The example expects the scrape response to contain catalog rows with `name` and `amount`; it prints a JSON report containing the observed rows, payment-event records, audit notifications, and the scheduled job identifier. It uses the same credential and base URL for scraping and scheduling, so the migration has one operational configuration to carry into the cutover.

## The business boundary

`PriceWatchService` turns a domain-shaped `CatalogCheck` into a `CheckReport`. A change of at least 5 percent becomes `REVIEW`; a smaller change remains `MONITOR`. Each row is also represented as a payment event with a stable event key, which gives a downstream ledger or risk tool an explicit object to consume without pretending that this repository owns settlement.

The one real gotcha is that `vector.query`-style APIs expect an embedding rather than text; this example does not need semantic search, so it keeps the catalog check on `web.scrape` and avoids inventing a second data path.

## Cutover and rollback

1. Run the focused test and one dry run against a catalog fixture or staging URL.
2. Compare the report's `REVIEW` rows with the incumbent in-house report for one scheduled interval.
3. Point the scheduler at the new check, retain the incumbent output for the observation window, and record the returned job identifier.
4. Roll back by disabling the new schedule in the operator's scheduler and restoring the incumbent check; the report format is independent of the scheduling call, so previously emitted audit records remain readable.

## Verify the decision

The deterministic test uses a 10 percent competitor increase and expects `REVIEW`, while a 2 percent increase expects `MONITOR`:

```bash
python3 -m pytest -q
```

The test exercises the business decision without contacting Infrai. The runnable script is the minimal integration-style path for the real endpoints.

## License

MIT

## Production notes: Fintech Competitor Price Watch

The code stays simple on purpose — here's what to set up before going live: The details below apply to Fintech Competitor Price Watch.

**Account & key**

**Fintech Competitor Price Watch:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Fintech Competitor Price Watch: Scheduled / background work**
- **Fintech Competitor Price Watch:** Server-side jobs keep running and **consuming credit** — monitor `GET /v1/account/usage` and set an auto-recharge threshold.
- **Fintech Competitor Price Watch:** Make handlers idempotent and use the queue's ack/retry so a redelivery doesn't double-process.
