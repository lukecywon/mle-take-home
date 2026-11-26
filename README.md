# Similar Companies API

The RabbitMQ consumer reads registry events, embeds English and Malay business descriptions on CPU, and stores company records and vectors in Postgres. The FastAPI service reads those records and ranks similar companies with pgvector. The [original assessment brief](README-OLD.md) and [design notes](DESIGN.md) are included here.

## Start locally

You need Docker with Compose and `uv`. Run these commands from the repo root. `uv` uses the project's Python 3.14 version. The app uses the default local ports `5432` for Postgres and `5672` for RabbitMQ. Keep those ports free before starting the stack.

1. Install the locked dependencies and start Postgres and RabbitMQ.

   ```sh
   just setup
   just up
   ```

2. Start the consumer in one terminal and leave it running. It creates the database table, enables pgvector, and downloads the embedding model from Hugging Face on first use. Wait for `Queue: company-events successfully connected`.

   ```sh
   just consumer
   ```

3. In a second terminal, publish the sample feed and start the API. Publishing finishes when RabbitMQ has accepted the messages. The consumer may still be processing them. After publishing, the consumer will start embedding all the items in the queue, wait for this to finish before moving on to the next step.

   ```sh
   just publish
   just api
   ```

4. Open [the interactive API docs](http://127.0.0.1:8000/docs) or run the requests below (wait for the consumer to finish embedding before using the API). On Windows PowerShell, use `curl.exe` instead of `curl` if `curl` is aliased. For the complete sample results, wait for `company-events` to show zero **Ready** and **Unacked** messages in [RabbitMQ Management](http://127.0.0.1:15672), using `guest` / `guest`.

   ```sh
   curl http://127.0.0.1:8000/companies/SYN-001550
   curl "http://127.0.0.1:8000/companies/SYN-001550/similar?limit=4"
   ```

   Lookup returns one company. Recommendations return up to four by default, with a valid `limit` of 1–25. Unknown or struck-off companies return `404`. An active company without an embedding returns `[]` from `/similar`.

## Run the tests

With Postgres running, initialize pgvector if you have not started the consumer yet. Copy the example environment file once if you do not already have a `.env` file.

```sh
uv run --locked python -m consumer.db
```

In PowerShell:

```powershell
Copy-Item .env.example .env
```

In Bash:

```sh
cp .env.example .env
```

Then run the suite. The database-backed tests use isolated schemas and clean up after themselves. The broker, API server, and model download are unnecessary for this suite.

```sh
uv run --locked --env-file .env python -m unittest discover -s tests -v
```

## Run the embedding benchmark

```sh
uv run --locked python benchmark_embeddings.py
```

This measures model loading and local embedding time for the feed separately. It does not require Postgres or RabbitMQ.

## Stop the stack

Stop the API and consumer with `Ctrl+C` in their terminals, then run `just down` to stop Postgres and RabbitMQ while retaining your local data.
