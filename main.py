from fastapi import FastAPI
from app.api.routes import admin,auth,user
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="RFP Generator")

app.add_middleware(
    CORSMiddleware,
    allow_origins= ["*"], 
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"], 
)


app.include_router(auth.router,tags=["Auth"])
app.include_router(admin.router,tags=["Admin"])
app.include_router(user.router,tags=["User"])
