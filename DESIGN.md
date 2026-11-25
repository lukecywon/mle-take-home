# Consumer
## Company Identity and Event Ordering
### Decisions
The company registration number serves as the primary key in the created "companies" table. The table contains the following information/columns:
- registration_number (primary key)
- company_name (str)
- description (str)
- state (str)
- industry (str)
- embedding (VECTOR(384))
- updated_at (datetime)
- is_active (boolean)

Before adding a registration number to the database, the code trims the whitespace, and uppercases the ID to normalize it.

Since in the data, there are sometimes multiple events that affect a single company, the first instance in the queue is added to the database first as the initial entry. If the consumer encounters another event affecting the same "registration_number" it compares the timestamp of the new event in the queue verses the last logged event in the databse. If the new event in the queue is newer than last recorded event, then it will update the database entry. If not, no changes will occur.

This prevents stale or repeat events from overriding more relevant ones.

Speaking of events, when a company is struck off, their entry remains inside the database. Just the `is_active` flag is toggled to False. When the API is called later, searching for an inactive company will result in an error stating that the chosen company is no longer active.

### Assumptions
- The queue operate in the Malaysian timezone (GMT+8)
- Events with no usable timestamps are skipped and not put back into the queue
- Events with malformed JSON bodies are skipped and not put back into the queue

## Delivery and failure handling
### Decisions
The consumer processes messages one at a time and waits for the database to commit before acknowledging successful deliveries. The process of embedding and database work are moved off the main thread with `asyncio.to_thread`.

There are multiple events with a malformed JSON body or missing attributes. These ones are skipped and not readded to the queue to prevent an infinite loop. Instead the `logging` library is used to record instances of this happening into the app.log file that gets generated on each run. Invalid events are logged with their `message_id` and acknowledged so the consumer can move on.



## Embedding
### Decisions
I used the `"intfloat/multilingual-e5-small"` model via HuggingFace (sentence-transformers) for the vector embedding. It is a multilingual model with around 100M parameters and an embedding size of 384.

The reasons I choose this model are as follows:
- The data contains descriptions with both English and Malay languages
- This might cause issues with the initially recommended `"BAAI/bge-small-en-v1.5"` model, as this is a monolingual model only officially supporting English
- Therefore it might not be able to understand Malay and rank companies with Malay descriptions next to English ones
- Looking at `"intfloat/multilingual-e5-small"` as compared to `"BAAI/bge-small-en-v1.5"`, the latter has around 33.4M parameters compared to the roughly 100M parameters of the former
- I believe the added multilingual functionality is a good trade-off for the increased parameter count
- Upon testing on my desktop CPU (i5-9400F), which is a pretty old i5 model, it runs the through the whole dataset (all 2518 messages) in 55.65s.

### Assumptions
- The dataset will contain multiple languages, potentially more than just English and Malay in the future
- Whatever CPU that will be running this on a server, will be at least as powerful as mine (i5-9400F) or better

### Limitations
- During manual testing, I noticed that there are some instances where a company with an English description has a company with a similar Malay description in its top 25 but the company with the Malay description did not have the English one in its top 25.
- This seems to be a concrete issue with the choice of model, I can only hypothesise as to why this happens for now, but it seems like the model ranks descriptions of the same language closer together than descriptions which have the same meaning in a different language.
- ONLY **company description** is used for the vector embedding, other fields like "state" or "industry" are returned in the API, but are **not** used in the vector embedding. Ties are broken by registration number.

# API Service
## Decisions
- The API distinguishes a missing company from a company with no matches in the return error.
- Endpoints:
  - `/companies/{registration_number}` - used for getting individual company information
  - `/companies/{registration_number}/similar` - used for getting said company's similar companies

## Limitations
- Current FastAPI implementation runs syncronously, can be slower than an asyncronous implementation

# What was not done
## Transient failures
An unexpected embedding or database error can escape the loop. The current code rejects that delivery without requeuing. So anything that fails due to an embedding error or database error will fail without being requeued. This is something that I would choose to work on closing if there was more time.

# What would be changed for a 10x implementation
## Timing
| Metric | Current feed (measured) | 10× feed (estimated) |
|---|---:|---:|
| Descriptions embedded | 2,429 | 24,290 |
| Total embedding time | 55.65 s | 556.50 s (9 min 16.5 s) |
| Mean time per description | 22.9 ms | 22.9 ms |
| P95 time per description | 44.8 ms | 44.8 ms |
| Cached model load time | 3.73 s | 3.73 s |

The 10× estimate assumes the same CPU, a similar mix of description lengths, and one-at-a-time embedding. The model loads once per run. Timings exclude RabbitMQ and Postgres.

## Embedding
- **Repeated Descriptions** : Cache vectors by prepared desscriptions. The sample feed has many repeats, so many companies can reuse the same vector while keeping seperate records.
- **Improve database writes and retries** : If db commit speed becomes a bottleneck, it could be processed in batches, with several events being processed in one transaction.
- **Bounded retries** : Since the transient errors are an issue now, a future implementation would ideally allow for bounded retries for database failures so that a valid update survives a small database outage.

## API Service
- **FastAPI asynchronous implementation** : For now I went with a basic synchronous implementation because I am also using a synchronous SQLModel engine. In a 10x volume implementation ideally that would also be made asynchronous.

# AI Usage
AI was used to assist with this project, but not write it. Unless stated otherwise, all code in the consumer and api sections are handwritten with assistance from only chatbot style LLMs for syntax and explainations. I used ChatGPT 6.2 Sol to assist with explaining syntax, best practices and introducing me to how RabbitMQ works.

On the other hand, the automated unittests are generated using agentic AI, using ChatGPT 6.2 Sol via Codex. Even though the tests are written using AI, I initially defined what test cases I wanted manually to ensure that they are useful and not just a bunch of unnessacary tests. AI was used here just to save on time to work on the implementaion more.

What was generated using agentic AI:
- Unittests - although test cases defined manually
- `benchmark_embeddings.py` - timing script