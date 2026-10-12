from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import mysql.connector
import bcrypt
from typing import Optional
from datetime import datetime  
import time

def get_db_connection():
    try:
        # Try to ping the database to see if connection is alive
        db.ping(reconnect=True, attempts=3, delay=1)
        return db
    except:
        # If failed, create new connection
        return mysql.connector.connect(
            host="localhost",
            port="3307",
            user="root",
            password="",
            database="skill_swap_db",
            connection_timeout=30,
            autocommit=True,
            use_pure=True
        )

# Use this before each query
def execute_query(query, params=None):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(query, params or ())
    conn.commit()
    return cursor

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

db = mysql.connector.connect(
    host="localhost",
    port="3306",
    user="root",
    password="",
    database="skill_swap_db"
)
cursor = db.cursor(dictionary=True)

class UserRegister(BaseModel):
    name: str
    email: str
    password: str
    location: Optional[str] = ""

class UserLogin(BaseModel):
    email: str
    password: str

class Message(BaseModel):
    to_user: int
    message: str

@app.post("/api/register")
def register(user: UserRegister):
    try:
        hashed = bcrypt.hashpw(user.password.encode(), bcrypt.gensalt())
        query = "INSERT INTO users (name, email, password, location) VALUES (%s, %s, %s, %s)"
        cursor.execute(query, (user.name, user.email, hashed, user.location))
        db.commit()
        return {"success": True, "message": "Account created successfully", "user_id": cursor.lastrowid}
    except mysql.connector.IntegrityError:
        raise HTTPException(status_code=400, detail="Email already exists")

@app.post("/api/login")
def login(user: UserLogin):
    cursor.execute("SELECT * FROM users WHERE email = %s", (user.email,))
    db_user = cursor.fetchone()
    if not db_user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not bcrypt.checkpw(user.password.encode(), db_user['password'].encode()):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return {
        "success": True,
        "user": {
            "id": db_user['id'],
            "name": db_user['name'],
            "email": db_user['email'],
            "location": db_user['location'],
            "rating": db_user['rating']
        }
    }

# ========== USERS API ==========
@app.get("/api/users/{user_id}")
def get_users(user_id: int):
    cursor.execute("SELECT id, name, email, location, rating FROM users WHERE id != %s", (user_id,))
    users = cursor.fetchall()
    return {"users": users}

# ========== SKILLS API ==========
@app.get("/api/skills/{user_id}")
def get_skills(user_id: int):
    cursor.execute("SELECT skill_name, skill_type FROM user_skills WHERE user_id = %s", (user_id,))
    skills = cursor.fetchall()
    return {"skills": skills}
# ========== ADD SKILL ==========
@app.post("/api/skills/{user_id}")
def add_skill(user_id: int, skill: dict): 
    cursor.execute(
        "INSERT INTO user_skills (user_id, skill_name, skill_type) VALUES (%s, %s, %s)",
        (user_id, skill['skill_name'], skill['skill_type'])
    )
    db.commit()
    return {"success": True, "message": "Skill added"}

# ========== MESSAGES API ==========
@app.post("/api/messages/{from_user}")
def send_message(from_user: int, msg: Message):
    cursor.execute(
        "INSERT INTO messages (from_user, to_user, message) VALUES (%s, %s, %s)",
        (from_user, msg.to_user, msg.message)
    )
    db.commit()
    return {"success": True, "message": "Message sent"}

@app.get("/api/messages/{user1}/{user2}")
def get_messages(user1: int, user2: int):
    cursor.execute("""
        SELECT * FROM messages 
        WHERE (from_user = %s AND to_user = %s) OR (from_user = %s AND to_user = %s)
        ORDER BY created_at ASC
    """, (user1, user2, user2, user1))
    messages = cursor.fetchall()
    
    cursor.execute("UPDATE messages SET is_read = TRUE WHERE from_user = %s AND to_user = %s", (user2, user1))
    db.commit()
    
    for msg in messages:
        if isinstance(msg.get('created_at'), datetime):
            msg['created_at'] = msg['created_at'].strftime("%Y-%m-%d %H:%M:%S")
    
    return {"messages": messages}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8004) 