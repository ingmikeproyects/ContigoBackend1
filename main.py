import os

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from routers import auth, users, biometrics, emotional_states, activities, alerts, vinculaciones, notas, calibration, payments, risk, gad7, tasks
from database import get_supabase

app = FastAPI(title="Contigo API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(biometrics.router)
app.include_router(emotional_states.router)
app.include_router(activities.router)
app.include_router(alerts.router)
app.include_router(vinculaciones.router)
app.include_router(notas.router)
app.include_router(calibration.router)
app.include_router(payments.router)
app.include_router(risk.router)
app.include_router(gad7.router)
app.include_router(tasks.router)

@app.get("/")
async def root():
    return {"message": "Contigo API esta corriendo"}

@app.get("/ping")
def ping():
    return {
        "status": "ok",
        "message": "Backend Contigo funcionando correctamente",
        "version": "1.0.0"
    }

@app.get("/health")
def health():
    revision = os.getenv("RAILWAY_GIT_COMMIT_SHA", "local")[:8]
    return {
        "status": "ok",
        "message": "El servidor responde correctamente",
        "revision": revision,
    }


if __name__ == "__main__":
    import uvicorn

    # Railway inyecta PORT en tiempo de ejecución. Leerlo desde Python evita
    # depender de que el shell del contenedor expanda correctamente `$PORT`.
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
    )
