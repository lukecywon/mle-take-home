import asyncio
import json

import aio_pika


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
                        event = json.loads(message.body)
                        print(event)


async def main():
    """
    Defines the url and port, and then runs the consumer
    """

    port = "5672"
    url = f"amqp://guest:guest@127.0.0.1:{port}/"
    queue_name = "company-events"

    consumer = Consumer(url, queue_name=queue_name)
    await consumer.start()


if __name__ == "__main__":
    asyncio.run(main())
