from pydantic import BaseModel, ConfigDict


class SportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    name: str


class BookmakerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    name: str
    is_anj_licensed: bool
