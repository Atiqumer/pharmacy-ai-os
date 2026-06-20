from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import inventory

app = FastAPI(
    title="AI-Powered Pharmacy OS Engine",
    description="The intelligent data automation layer for independent medical stores.",
    version="1.0.0"
)

# Allow your local Next.js development server to talk to the Python backend seamlessly
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Tighten this up to your specific port in production later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(inventory.router)

@app.get("/")
def read_root():
    return {"status": "online", "system": "AI Pharmacy Operating System Backend Engine"}