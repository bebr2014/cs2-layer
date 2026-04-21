from fastapi import FastAPI
from app.api.webhooks import router

app = FastAPI(title="cs2-layer")
app.include_router(router)

@app.get("/")
async def root():
    return {"status": "ok"}