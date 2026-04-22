# from sqlalchemy import create_engine
# from sqlalchemy.orm import sessionmaker, declarative_base
# import os
# from dotenv import load_dotenv

# load_dotenv() 

# DATABASE_URL = os.getenv("DATABASE_URL") 

# engine = create_engine(DATABASE_URL)
# Base = declarative_base()

# def get_db():
#     db = sessionmaker(bind=engine,expire_on_commit=False)()
#     try:
#         yield db
#     finally:
#         db.close()


from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
import os
from dotenv import load_dotenv

load_dotenv()
# DATABASE_URL = os.getenv("DATABASE_URL") 
ASYNC_DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_async_engine(ASYNC_DATABASE_URL, echo=False, pool_pre_ping=True)

Base = declarative_base()

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()