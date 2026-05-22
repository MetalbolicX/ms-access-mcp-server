from pydantic import BaseModel, Field


class VBAModuleInfo(BaseModel):
    name: str
    type: str
    has_code: bool = False


class VBAProjectInfo(BaseModel):
    name: str
    description: str = ""
    modules: list[VBAModuleInfo] = Field(default_factory=list)
