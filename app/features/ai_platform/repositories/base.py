from typing import TypeVar, Generic, Type, Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete
from pydantic import BaseModel

ModelType = TypeVar("ModelType")
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)

class BaseRepository(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: Type[ModelType], db: Session):
        self.model = model
        self.db = db

    def get(self, id: UUID, company_id: UUID) -> Optional[ModelType]:
        stmt = select(self.model).where(
            self.model.id == id,
            self.model.company_id == company_id
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_multi(self, company_id: UUID, skip: int = 0, limit: int = 100) -> List[ModelType]:
        stmt = select(self.model).where(
            self.model.company_id == company_id
        ).offset(skip).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def create(self, company_id: UUID, obj_in: CreateSchemaType, **kwargs) -> ModelType:
        obj_in_data = obj_in.model_dump()
        db_obj = self.model(company_id=company_id, **obj_in_data, **kwargs)
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def update(self, db_obj: ModelType, obj_in: UpdateSchemaType) -> ModelType:
        obj_data = obj_in.model_dump(exclude_unset=True)
        for field, value in obj_data.items():
            setattr(db_obj, field, value)
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def delete(self, id: UUID, company_id: UUID) -> bool:
        db_obj = self.get(id=id, company_id=company_id)
        if not db_obj:
            return False
        self.db.delete(db_obj)
        self.db.commit()
        return True
