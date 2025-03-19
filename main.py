from fastapi import FastAPI, Request, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
import datetime

import firebase_admin
from firebase_admin import credentials, firestore
from firebase_admin.firestore import ArrayUnion, ArrayRemove


# Initialize Firebase Admin SDK
cred = credentials.Certificate("f1-app-d2ac7-firebase-adminsdk-fbsvc-596f9d853c.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Data model for a Task Board
class TaskBoard(BaseModel):
    name: str
    createdBy: str             # User ID of the creator
    members: List[str]         # List of user IDs invited to this board

# Data model for a Task
class Task(BaseModel):
    title: str
    description: Optional[str] = ""
    assignedTo: List[str]      # List of user IDs this task is assigned to
    dueDate: Optional[datetime.datetime] = None
    completed: bool = False

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    dueDate: Optional[datetime.datetime] = None
    completed: Optional[bool] = None

@app.post("/boards")
async def create_board(board: TaskBoard):
    board_doc = db.collection("taskBoards").document()  # Auto-generated document ID
    board_data = board.dict()
    board_doc.set(board_data)
    return {"id": board_doc.id, "message": "Board created successfully"}

@app.get("/boards")
async def list_boards(userId: str):
    boards_ref = db.collection("taskBoards")
    query = boards_ref.where("members", "array_contains", userId)
    docs = query.stream()
    boards = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        boards.append(data)
    return boards

@app.post("/boards/{board_id}/tasks")
async def create_task(board_id: str, task: Task):
    board_ref = db.collection("taskBoards").document(board_id)
    if not board_ref.get().exists:
        raise HTTPException(status_code=404, detail="Board not found")
    task_doc = board_ref.collection("tasks").document()  # Auto-generated ID for the task
    task_data = task.dict()
    task_data["completed"] = False
    task_data["createdAt"] = firestore.SERVER_TIMESTAMP
    task_doc.set(task_data)
    return {"id": task_doc.id, "message": "Task created successfully"}

@app.get("/boards/{board_id}/tasks")
async def list_tasks(board_id: str):
    board_ref = db.collection("taskBoards").document(board_id)
    if not board_ref.get().exists:
        raise HTTPException(status_code=404, detail="Board not found")
    tasks_ref = board_ref.collection("tasks")
    docs = tasks_ref.stream()
    tasks = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        tasks.append(data)
    return tasks

# Endpoint to get board details (including creator info)
@app.get("/boards/{board_id}/details")
async def get_board_details(board_id: str):
    board_ref = db.collection("taskBoards").document(board_id)
    doc = board_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Board not found")
    data = doc.to_dict()
    data["id"] = doc.id
    return data

# Endpoint to add a user to a board (only allowed for the board creator)
@app.patch("/boards/{board_id}/add_user")
async def add_user_to_board(board_id: str, payload: dict):
    """
    Expects JSON payload:
      {
         "user_email": "<email-to-add>",
         "current_user_id": "<uid-of-requester>"
      }
    """
    board_ref = db.collection("taskBoards").document(board_id)
    doc = board_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Board not found")
    board_data = doc.to_dict()

    if board_data.get("createdBy") != payload.get("current_user_id"):
        raise HTTPException(status_code=403, detail="Only the board creator can add users")

    try:
        from firebase_admin import auth as firebase_auth
        user_record = firebase_auth.get_user_by_email(payload.get("user_email"))
    except Exception as e:  # noqa: F841
        raise HTTPException(status_code=400, detail="User not found")
    
    board_ref.update({
        "members": ArrayUnion([user_record.uid])
    })
    return {"message": "User added successfully"}

# Endpoint to update (edit) a task (any member can edit)
@app.put("/boards/{board_id}/tasks/{task_id}")
async def edit_task(board_id: str, task_id: str, task: TaskUpdate):
    board_ref = db.collection("taskBoards").document(board_id)
    task_ref = board_ref.collection("tasks").document(task_id)
    if not task_ref.get().exists:
        raise HTTPException(status_code=404, detail="Task not found")
    task_data = task.dict(exclude_unset=True)
    if "assignedTo" in task_data and task_data["assignedTo"]:
        task_data["highlight"] = firestore.DELETE_FIELD
        task_ref.update(task_data)
    return {"message": "Task updated successfully"}

@app.patch("/boards/{board_id}/rename")
async def rename_board(board_id: str, payload: dict):
    """
    Expects a JSON payload:
      {
         "newName": "<new board name>",
         "current_user_id": "<uid-of-requester>"
      }
    Only the board creator can rename the board.
    """
    board_ref = db.collection("taskBoards").document(board_id)
    doc = board_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Board not found")
    board_data = doc.to_dict()
    if board_data.get("createdBy") != payload.get("current_user_id"):
        raise HTTPException(status_code=403, detail="Only the board owner can rename the board")
    new_name = payload.get("newName")
    if not new_name:
        raise HTTPException(status_code=400, detail="New board name is required")
    board_ref.update({"name": new_name})
    return {"message": "Board renamed successfully"}

# Endpoint to delete a task (any member can delete)
@app.delete("/boards/{board_id}/tasks/{task_id}")
async def delete_task(board_id: str, task_id: str):
    board_ref = db.collection("taskBoards").document(board_id)
    task_ref = board_ref.collection("tasks").document(task_id)
    if not task_ref.get().exists:
        raise HTTPException(status_code=404, detail="Task not found")
    task_ref.delete()
    return {"message": "Task deleted successfully"}

# Endpoint to update task completion status (existing)
@app.patch("/boards/{board_id}/tasks/{task_id}")
async def update_task_completion(board_id: str, task_id: str, payload: dict):
    board_ref = db.collection("taskBoards").document(board_id)
    task_ref = board_ref.collection("tasks").document(task_id)
    if not task_ref.get().exists:
        raise HTTPException(status_code=404, detail="Task not found")
    
    update_data = {}
    if payload.get("completed") is True:
        update_data["completed"] = True
        update_data["completedAt"] = firestore.SERVER_TIMESTAMP
    else:
        update_data["completed"] = False
        update_data["completedAt"] = None

    task_ref.update(update_data)
    return {"message": "Task updated successfully"}

@app.patch("/boards/{board_id}/remove_user")
async def remove_user_from_board(board_id: str, payload: dict):
    """
    Expects payload:
      {
         "userIdToRemove": "<user id to remove>",
         "current_user_id": "<uid-of-requester>"
      }
    Only the board creator can remove a user.
    After removal:
      - The user is removed from the board's "members" array.
      - All tasks in the board that have that user in "assignedTo" are updated:
           The user is removed from the "assignedTo" array,
           and a new field "highlight" is set to "red".
    """
    board_ref = db.collection("taskBoards").document(board_id)
    doc = board_ref.get()
    if not doc.exists:
         raise HTTPException(status_code=404, detail="Board not found")
    board_data = doc.to_dict()
    if board_data.get("createdBy") != payload.get("current_user_id"):
         raise HTTPException(status_code=403, detail="Only the board creator can remove a user")
    user_id_to_remove = payload.get("userIdToRemove")
    if not user_id_to_remove:
         raise HTTPException(status_code=400, detail="User ID to remove is required")
    # Remove the user from the board members
    board_ref.update({
         "members": ArrayRemove([user_id_to_remove])
    })
    # Update tasks: for each task that has the user assigned, remove the user and set highlight to "red"
    tasks_ref = board_ref.collection("tasks")
    tasks_query = tasks_ref.where("assignedTo", "array_contains", user_id_to_remove)
    for task_doc in tasks_query.stream():
         task_ref = board_ref.collection("tasks").document(task_doc.id)
         task_ref.update({
             "assignedTo": ArrayRemove([user_id_to_remove]),
             "highlight": "red"
         })
    return {"message": "User removed from board successfully"}

@app.delete("/boards/{board_id}")
async def delete_board(board_id: str, payload: dict):
    """
    Expects payload:
      { "current_user_id": "<uid-of-requester>" }
    Only the board creator can remove the board, and only if:
      - The board's members array contains only the creator.
      - The board's tasks subcollection is empty.
    """
    board_ref = db.collection("taskBoards").document(board_id)
    board_doc = board_ref.get()
    if not board_doc.exists:
        raise HTTPException(status_code=404, detail="Board not found")
    board_data = board_doc.to_dict()
    current_user_id = payload.get("current_user_id")
    if board_data.get("createdBy") != current_user_id:
        raise HTTPException(status_code=403, detail="Only the board creator can remove the board")
    # Check that only the creator remains in members
    if "members" in board_data and len(board_data["members"]) > 1:
        raise HTTPException(status_code=400, detail="Remove all non-owning users before deleting the board")
    # Check that there are no tasks in the board
    tasks_ref = board_ref.collection("tasks")
    tasks = list(tasks_ref.stream())
    if tasks:
        raise HTTPException(status_code=400, detail="Remove all tasks before deleting the board")
    # Conditions met; delete the board
    board_ref.delete()
    return {"message": "Board removed successfully"}

# HTML endpoints
@app.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/dashboard")
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/boards/{board_id}")
async def view_board(request: Request, board_id: str):
    return templates.TemplateResponse("board.html", {"request": request, "board_id": board_id})

@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})
