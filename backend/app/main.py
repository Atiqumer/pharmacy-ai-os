from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
# Explicitly import both route files directly to avoid any __init__ folder caching issues
from app.routes import inventory, query, analytics

app = FastAPI(
    title="AI-Powered Pharmacy OS Engine",
    description="The intelligent data automation layer for independent medical stores.",
    version="1.0.0"
)

# Allow local Next.js development server connections
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Explicitly mount both routers onto the core app instance
app.include_router(inventory.router)
app.include_router(analytics.router)
app.include_router(query.router)  

@app.get("/")
def read_root():
    return {"status": "online", "system": "AI Pharmacy Operating System Backend Engine"}