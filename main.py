import asyncio
from bot import run_bot
from database import init_db
from scheduler import start_scheduler

async def main():
    await init_db()
    asyncio.create_task(start_scheduler())
    await run_bot()

if __name__ == '__main__':
    asyncio.run(main())