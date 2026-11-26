import asyncio
import logging

import aio_pika
from .db import save_company, init_db
from .embed import load_model, embed_description
from .json_parser import CompanyUpserted, CompanyStruckOff, Event, event_parser, parse_updated_at
from pydantic import ValidationError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class Consumer:
    """
    Defines a consumer for the RabbitMQ Queue
    """

    def __init__(self, url: str, queue_name: str):
        self.url = url
        self.queue_name = queue_name

    async def start(self, verbose=False):
        """
        Starts the consumer
        """

        # Initialize table in DB
        await asyncio.to_thread(init_db)

        # Load embedding model
        if verbose:
            print("Loading embedding model...")
        model = await asyncio.to_thread(load_model)
        if verbose:
            print("Model finished loading")

        # Start connection to RabbitMQ
        connection = await aio_pika.connect_robust(self.url)

        async with connection:
            channel = await connection.channel()
            await channel.set_qos(prefetch_count=10)
            if verbose:
                print("Channel established")

            queue = await channel.declare_queue(self.queue_name, durable=True)
            if verbose:
                print("Queue: " + self.queue_name + " successfully connected")

            # Iterate through queue
            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    async with message.process():
                        # Validate JSON against defined format
                        try:
                            event = event_parser.validate_json(message.body)
                        except ValidationError as err:
                            logger.warning("Invalid company event %s: %s", message.message_id, err)
                            continue

                        # Parse timestamp
                        try:
                            updated_at = parse_updated_at(event.updatedAt)
                        except (ValueError, OverflowError, OSError) as err:
                            logger.warning("Invalid updatedAt for message %s: %s", message.message_id, err)
                            continue

                        registration = event.registrationNumber.strip().upper()

                        # Check event type
                        if isinstance(event, CompanyUpserted):
                            data = event.data

                            # Embed description
                            embedding = await asyncio.to_thread(
                                embed_description, model, data.natureOfBusiness
                            )

                            await asyncio.to_thread(
                                save_company,
                                registration,
                                updated_at,
                                company_name = data.companyName,
                                description = data.natureOfBusiness,
                                state = data.state,
                                industry = data.industry,
                                embedding = embedding,
                                is_active = True
                            )
                        else: # CompanyStruckOff event instead
                            await asyncio.to_thread(
                                save_company,
                                registration,
                                updated_at,
                                is_active = False
                            )

                        print(f"Parsed {type(event).__name__}: {registration}")


async def main():
    """
    Defines the url and port, and then runs the consumer
    """

    port = "5672"
    url = f"amqp://guest:guest@127.0.0.1:{port}/"
    queue_name = "company-events"

    consumer = Consumer(url, queue_name=queue_name)
    await consumer.start(verbose=True)

if __name__ == "__main__":
    asyncio.run(main())
