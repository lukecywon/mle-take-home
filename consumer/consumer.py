import asyncio
import logging

import aio_pika
from json_parser import CompanyUpserted, CompanyStruckOff, Event, event_parser
from pydantic import ValidationError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("app.log"),  # Write to a file
        logging.StreamHandler()          # Print to the console
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

        connection = await aio_pika.connect_robust(self.url)

        async with connection:
            channel = await connection.channel()
            await channel.set_qos(prefetch_count=10)
            if verbose:
                print("Channel established")

            queue = await channel.declare_queue(self.queue_name, durable=True)
            if verbose:
                print("Queue: " + self.queue_name + " successfully connected")

            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    async with message.process():
                        try:
                            event = event_parser.validate_json(message.body)
                        except ValidationError as err:
                            logger.warning("Invalid company event %s: %s", message.message_id, err)

                        registration = event.registrationNumber.strip().upper()

                        if isinstance(event, CompanyUpserted):
                            description = event.data.natureOfBusiness

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
