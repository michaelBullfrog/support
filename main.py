from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def home():
    return {"ok": True, "message": "running"}

@app.get("/health")
def health():
    return {"ok": True}
