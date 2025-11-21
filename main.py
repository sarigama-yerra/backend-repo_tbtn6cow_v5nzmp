import os
from datetime import datetime, timezone
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import VerificationTask, TaskResult, AppUser

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AssignResponse(BaseModel):
    task_id: str
    title: str
    price: float
    location: str
    image_url: str
    property_type: str
    reward_cents: int
    instructions: str


@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"

            # Try to list collections to verify connectivity
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]  # Show first 10 collections
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"

    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    # Check environment variables
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


# -----------------------------
# Property Verification API
# -----------------------------

# Utility to convert ObjectId to string within dicts

def _doc_to_dict(doc: dict):
    if not doc:
        return doc
    d = {**doc}
    if d.get("_id"):
        d["id"] = str(d.pop("_id"))
    return d


@app.post("/api/seed")
def seed_data():
    """Seed a few sample properties and a demo user if collections are empty."""
    # Seed user
    users = get_documents("appuser", {})
    if not users:
        create_document("appuser", AppUser(name="Demo User", email="demo@example.com", wallet_balance_cents=0))

    # Seed tasks (properties)
    tasks = get_documents("verificationtask", {})
    if not tasks:
        samples = [
            {
                "title": "Modern Studio Apartment",
                "price": 1200.0,
                "location": "San Francisco, CA",
                "image_url": "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?q=80&w=1200&auto=format&fit=crop",
                "property_type": "Apartment",
                "reward_cents": 30,
            },
            {
                "title": "Cozy Suburban Home",
                "price": 350000.0,
                "location": "Austin, TX",
                "image_url": "https://images.unsplash.com/photo-1560185008-b033106af2fa?q=80&w=1200&auto=format&fit=crop",
                "property_type": "House",
                "reward_cents": 30,
            },
            {
                "title": "Downtown Loft",
                "price": 2200.0,
                "location": "Chicago, IL",
                "image_url": "https://images.unsplash.com/photo-1600585154526-990dced4db0d?q=80&w=1200&auto=format&fit=crop",
                "property_type": "Loft",
                "reward_cents": 30,
            },
        ]
        for s in samples:
            create_document("verificationtask", VerificationTask(**s))

    return {"status": "ok"}


class StartTaskRequest(BaseModel):
    user_email: str


@app.post("/api/tasks/assign", response_model=AssignResponse)
def assign_task(payload: StartTaskRequest):
    """Assign the next available task to the user. Random-ish by last_assigned_at."""
    # Ensure user exists
    users = get_documents("appuser", {"email": payload.user_email})
    if users:
        user = users[0]
    else:
        # Auto-create user on first login
        user_id = create_document("appuser", AppUser(name=payload.user_email.split("@")[0], email=payload.user_email))
        user = db["appuser"].find_one({"_id": ObjectId(user_id)})

    # Pick next task: pending and not assigned or least recently assigned
    task = db["verificationtask"].find_one({"status": "pending"}, sort=[("last_assigned_at", 1)])
    if not task:
        raise HTTPException(status_code=404, detail="No tasks available")

    db["verificationtask"].update_one({"_id": task["_id"]}, {"$set": {"assigned_to": str(user["_id"]), "last_assigned_at": datetime.now(timezone.utc)}})

    task = db["verificationtask"].find_one({"_id": task["_id"]})
    task_d = _doc_to_dict(task)

    return AssignResponse(
        task_id=task_d["id"],
        title=task_d["title"],
        price=task_d["price"],
        location=task_d["location"],
        image_url=task_d["image_url"],
        property_type=task_d["property_type"],
        reward_cents=task_d.get("reward_cents", 30),
        instructions=task_d.get("instructions", "Please review this property information and confirm whether the listing is still active."),
    )


class SubmitRequest(BaseModel):
    user_email: str
    task_id: str
    choice: str  # 'active' | 'inactive' | 'unknown'


@app.post("/api/tasks/submit")
def submit_task(payload: SubmitRequest):
    # Validate user
    users = get_documents("appuser", {"email": payload.user_email})
    if not users:
        raise HTTPException(status_code=404, detail="User not found")
    user = users[0]

    # Validate task
    try:
        oid = ObjectId(payload.task_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task id")

    task = db["verificationtask"].find_one({"_id": oid})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Record result
    reward_cents = int(task.get("reward_cents", 30))
    create_document(
        "taskresult",
        TaskResult(
            task_id=str(task["_id"]),
            user_id=str(user["_id"]),
            choice=payload.choice,  # validated by schema
            reward_cents=reward_cents,
            submitted_at=datetime.now(timezone.utc),
        ),
    )

    # Mark task completed
    db["verificationtask"].update_one({"_id": task["_id"]}, {"$set": {"status": "completed"}})

    # Credit wallet
    db["appuser"].update_one({"_id": user["_id"]}, {"$inc": {"wallet_balance_cents": reward_cents}})

    return {
        "message": f"Task completed! ${reward_cents/100:.2f} has been added to your wallet.",
        "reward_cents": reward_cents,
    }


@app.get("/api/users/{email}/wallet")
def get_wallet(email: str):
    users = get_documents("appuser", {"email": email})
    if not users:
        raise HTTPException(status_code=404, detail="User not found")
    user = users[0]
    return {"wallet_balance_cents": int(user.get("wallet_balance_cents", 0))}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
