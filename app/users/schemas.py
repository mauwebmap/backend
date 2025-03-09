from pydantic import BaseModel


class AdminCreate(BaseModel):
    username: str
    password: str


class AdminResponse(BaseModel):
    username: str
    is_active: bool

    class Config:
        orm_mode = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"