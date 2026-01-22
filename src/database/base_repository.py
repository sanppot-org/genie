"""Base Repository for common CRUD operations."""

from abc import ABC, abstractmethod
from typing import Any, Protocol

from sqlalchemy.orm import Session


class HasId(Protocol):
    """id 속성을 가진 엔티티를 위한 Protocol."""

    id: Any


class ReadOnlyRepository[T, ID](ABC):
    """읽기 전용 Repository 베이스 클래스.

    MATERIALIZED VIEW 등 쓰기가 불가능한 데이터 소스를 위한 베이스 클래스입니다.

    Type parameters:
        T: Entity type
        ID: Primary key type
    """

    def __init__(self, session: Session) -> None:
        """Initialize repository with database session.

        Args:
            session: SQLAlchemy session
        """
        self.session = session

    @abstractmethod
    def _get_model_class(self) -> type[T]:
        """Get the model class for this repository.

        Returns:
            Model class type
        """

    def find_by_id(self, entity_id: ID) -> T | None:
        """Find entity by ID.

        Args:
            entity_id: Primary key value

        Returns:
            Entity if found, None otherwise
        """
        return self.session.query(self._get_model_class()).filter_by(id=entity_id).first()

    def find_all(self) -> list[T]:
        """Find all entities (no ordering - for models without id).

        Returns:
            List of all entities
        """
        return self.session.query(self._get_model_class()).all()


class BaseRepository[T: HasId, ID](ReadOnlyRepository[T, ID], ABC):
    """읽기/쓰기 가능한 Repository 베이스 클래스.

    일반 테이블을 위한 CRUD 기능을 제공합니다.
    id 속성을 가진 엔티티만 사용 가능합니다.

    Type parameters:
        T: Entity type (must have id attribute)
        ID: Primary key type
    """

    @abstractmethod
    def _get_unique_constraint_fields(self) -> tuple[str, ...]:
        """Get unique constraint field names for upsert logic.

        Returns:
            Tuple of field names that form unique constraint
        """

    def find_all(self) -> list[T]:
        """Find all entities (ordered by id ascending).

        Returns:
            List of all entities ordered by id
        """
        model_class = self._get_model_class()
        return self.session.query(model_class).order_by(model_class.id).all()

    def save(self, entity: T) -> T:
        """Save or update entity (upsert).

        If entity with same unique constraint fields exists, updates it.
        Otherwise, creates new entity.

        Args:
            entity: Entity to save

        Returns:
            Saved entity
        """
        # Find existing entity by unique constraint fields
        unique_fields = self._get_unique_constraint_fields()
        filters = {field: getattr(entity, field) for field in unique_fields}
        existing = self.session.query(self._get_model_class()).filter_by(**filters).first()

        if existing:
            for key, value in entity.__dict__.items():
                if not key.startswith("_") and key != "id":
                    setattr(existing, key, value)
            result = existing
        else:
            self.session.add(entity)
            result = entity

        self.session.flush()
        self.session.commit()
        self.session.refresh(result)
        return result

    def delete_by_id(self, entity_id: ID) -> bool:
        """Delete entity by ID.

        Args:
            entity_id: Primary key value

        Returns:
            True if deleted, False if not found
        """
        entity = self.find_by_id(entity_id)
        if entity:
            self.session.delete(entity)
            self.session.commit()
            return True
        return False
