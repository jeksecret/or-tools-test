from fastapi import FastAPI
from app.routes.api.solve_routes import router as solve_routes_router

app = FastAPI()

@app.get("/")
def read_root():
    """Root endpoint for API status."""
    return {"message": "API is running"}

app.include_router(solve_routes_router)
