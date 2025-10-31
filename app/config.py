import os
from dotenv import load_dotenv
from fastapi_mail import ConnectionConfig
from fastapi.security import OAuth2PasswordBearer
from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec

load_dotenv()

#MAIL CONFIG
mail_config = ConnectionConfig(
    MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
    MAIL_FROM=os.getenv("MAIL_FROM"),
    MAIL_PORT=int(os.getenv("MAIL_PORT", 587)),
    MAIL_SERVER=os.getenv("MAIL_SERVER"),
    MAIL_FROM_NAME=os.getenv("MAIL_FROM_NAME"),
    MAIL_STARTTLS=os.getenv("MAIL_STARTTLS") == "True",
    MAIL_SSL_TLS=os.getenv("MAIL_SSL_TLS") == "True",
    USE_CREDENTIALS=os.getenv("USE_CREDENTIALS") == "True",
    VALIDATE_CERTS=os.getenv("VALIDATE_CERTS") == "True",
)

SENDER_EMAIL = os.getenv("sender_email")
SENDER_PASSWORD = os.getenv("sender_password")

# AUTH CONFIG
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
SECRET_KEY = "narscbjim@$@&^@&%^&RFghgjvbdsha"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440

#OPENAI / SERPAPI CONFIG
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")
client = OpenAI(api_key=OPENAI_API_KEY)
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENV = os.getenv("PINECONE_ENV", "aws-us-east-1")
PINECONE_INDEX = os.getenv("PINECONE_INDEX", "kb-index")
PINECONE_INDEX_RINGER = os.getenv("PINECONE_INDEX_RINGER", "ringerinfo")

pc = Pinecone(api_key=PINECONE_API_KEY)

if PINECONE_INDEX not in pc.list_indexes().names():
    pc.create_index(
        name=PINECONE_INDEX,
        dimension=1536,
        metric="cosine",
        spec=ServerlessSpec(
            cloud="aws",
            region=PINECONE_ENV,
        ),
    )

if PINECONE_INDEX_RINGER not in pc.list_indexes().names():
    pc.create_index(
        name=PINECONE_INDEX_RINGER,
        dimension=1536,
        metric="cosine",
        spec=ServerlessSpec(
            cloud="aws",
            region=PINECONE_ENV,
        ),
    )

index = pc.Index(PINECONE_INDEX)
index_ringer = pc.Index(PINECONE_INDEX_RINGER)

UPLOAD_FOLDER = "uploads"
GENERATED_FOLDER = "generated_docs"
LOGIN_URL = os.getenv("LOGIN_URL")
