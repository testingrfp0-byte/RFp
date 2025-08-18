from fastapi_mail import ConnectionConfig

mail_config = ConnectionConfig(
    MAIL_USERNAME="nileshlinux01@gmail.com",
    MAIL_PASSWORD= "zzec ytjd nngt xajj",#"bhtv mpnb ufhz ftup",
    MAIL_FROM="nileshlinux01@gmail.com",
    MAIL_PORT=587,
    MAIL_SERVER="smtp.gmail.com", 
    MAIL_FROM_NAME="RFP Automation",
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True
)
