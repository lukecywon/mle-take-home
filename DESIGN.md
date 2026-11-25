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

Since in the data, there are sometimes multiple events that affect a single company, the first instance in the queue is added to the database first as the initial entry. If the consumer encounters another event affecting the same "registration_number" it compares the timestamp of the new event in the queue verses the last logged event in the databse. If the new event in the queue is newer than last recorded event, then it will update the database entry. If not, no changes will occur.

This prevents stale or repeat events from overriding more relevant ones.

### Assumptions
- The queue operate in the Malaysian timezone (GMT+8)
- Events with no usable timestamps are skipped and not put back into the queue
- Events with malformed JSON bodies are skipped and not put back into the queue

## Embedding
### Decisions
I used the `"intfloat/multilingual-e5-small"` model via HuggingFace (sentence-transformers) for the vector embedding. It is a multilingual model with around 100M parameters and an embedding size of 384.

The reasons I choose this model are as follows:
- The data contains descriptions with both English and Malay languages
- This might cause issues with the initially recommended `"BAAI/bge-small-en-v1.5"` model, as this is a monolingual model only officially supporting English
- Therefore it might not be able to understand Malay and rank companies with Malay descriptions next to English ones
- Looking at `"intfloat/multilingual-e5-small"` as compared to `"BAAI/bge-small-en-v1.5"`, the latter has around 33.4M parameters compared to the roughly 100M parameters of the former
- I believe the added multilingual functionality is a good trade-off for the increased parameter count
- Upon testing on my desktop CPU (i5-9400F), which is a pretty old i5 model, it runs the through the whole dataset (all 2518 messages) in

### Assumptions
- The dataset will contain multiple languages, potentially more than just English and Malay in the future
- Whatever CPU that will be running this on a server, will be at least as powerful as mine (i5-9400F) or better

## Handling bad messages
### Decisions
There are multiple events with a malformed JSON body or missing attributes. These ones are skipped and not readded to the queue to prevent an infinite loop. Instead the `logging` library is used to record instances of this happening into the app.log file that gets generated on each run. Invalid events are logged with their `message_id` and acknowledged so the consumer can move on.

## Updating the databse entries
### Decisions
Upsert events are treated as snapshots. Omitted optional fields are replaced with `NULL` in the database. As such a newer upsert without a description can clear an existing embedding.

# Producer

# AI Usage
AI was used to assist with this project, but not write it. Unless stated otherwise, all code in the consumer and producer sections are handwritten with assistance from only chatbot style LLMs for syntax and explainations. I used ChatGPT 6.2 Sol to assist with explaining syntax, best practices and introducing me to how RabbitMQ works.

On the other hand, the automated unittests are generated using agentic AI, using ChatGPT 6.2 Sol via Codex. Even though the tests are written using AI, I initially defined what test cases I wanted manually to ensure that they are useful and not just a bunch of unnessacary tests. AI was used here just to save on time to work on the implementaion more.