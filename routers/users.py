from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/users", tags=["users"])


class User(BaseModel):
    id: int | None = None
    name: str
    email: str


class UserUpdate(BaseModel):
    name: str | None = None
    email: str | None = None


# 模拟数据库
_users_db: dict[int, User] = {}
_user_id_counter = 1


@router.get("/")
async def list_users():
    """获取所有用户列表"""
    return list(_users_db.values())


@router.get("/{user_id}")
async def get_user(user_id: int):
    """根据 ID 获取用户"""
    if user_id not in _users_db:
        raise HTTPException(status_code=404, detail="User not found")
    return _users_db[user_id]


@router.post("/")
async def create_user(user: User):
    """创建新用户"""
    global _user_id_counter
    user.id = _user_id_counter
    _users_db[_user_id_counter] = user
    _user_id_counter += 1
    return user


@router.put("/{user_id}")
async def update_user(user_id: int, user_update: UserUpdate):
    """更新用户信息"""
    if user_id not in _users_db:
        raise HTTPException(status_code=404, detail="User not found")
    existing = _users_db[user_id]
    if user_update.name:
        existing.name = user_update.name
    if user_update.email:
        existing.email = user_update.email
    return existing


@router.delete("/{user_id}")
async def delete_user(user_id: int):
    """删除用户"""
    if user_id not in _users_db:
        raise HTTPException(status_code=404, detail="User not found")
    del _users_db[user_id]
    return {"message": "User deleted"}
