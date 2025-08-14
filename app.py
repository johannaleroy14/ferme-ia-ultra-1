from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"ok": True, "app": "alive"}

@app.get("/health")
def health():
    return {"ok": True}
