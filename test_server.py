# test_server.py
from fastapi import FastAPI

app = FastAPI()

@app.get("/api/leaderboard")
def read_leaderboard():
    return {"message": "The TEST server is working!"}