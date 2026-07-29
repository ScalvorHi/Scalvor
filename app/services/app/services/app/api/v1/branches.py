"""
API для работы с ветками проектов.
Создание, редактирование, удаление, перемещение.
"""
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from app.core.database import get_db
from app.api.deps import get_current_active_user
from app.models.user import User
from app.models.project import Project
from app.models.branch import Branch, BranchNote

router = APIRouter(prefix="/branches", tags=["branches"])


class BranchCreate(BaseModel):
    project_id: str
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    color: str = "#ff69b4"
    parent_branch_id: Optional[str] = None


class BranchUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    is_archived: Optional[bool] = None


class BranchMove(BaseModel):
    new_parent_id: Optional[str] = None
    order_index: Optional[int] = None


class NoteCreate(BaseModel):
    title: Optional[str] = None
    content: str
    note_type: str = "text"
    attachments: dict = Field(default_factory=dict)
    position_x: int = 0
    position_y: int = 0


class NoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    note_type: Optional[str] = None
    attachments: Optional[dict] = None
    position_x: Optional[int] = None
    position_y: Optional[int] = None


@router.get("/project/{project_id}")
async def list_branches(
    project_id: str,
    include_archived: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Получить все ветки проекта."""
    project_uuid = uuid.UUID(project_id)
    project = await db.get(Project, project_uuid)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Проект не найден")

    query = select(Branch).where(Branch.project_id == project_uuid)
    if not include_archived:
        query = query.where(Branch.is_archived == False)
    query = query.order_by(Branch.order_index)

    result = await db.execute(query)
    branches = result.scalars().all()

    # Строим дерево
    branch_map = {str(b.id): b for b in branches}
    tree = []
    for b in branches:
        b_data = {
            "id": str(b.id),
            "name": b.name,
            "description": b.description,
            "color": b.color,
            "parent_branch_id": str(b.parent_branch_id) if b.parent_branch_id else None,
            "order_index": b.order_index,
            "is_archived": b.is_archived,
            "is_default": b.is_default,
            "tags": b.tags,
            "targets": b.targets,
            "config": b.config,
            "created_at": b.created_at.isoformat(),
            "updated_at": b.updated_at.isoformat(),
            "children": [],
            "notes_count": 0,
            "scans_count": 0,
        }
        branch_map[str(b.id)] = b_data

    for b in branches:
        b_data = branch_map[str(b.id)]
        if b.parent_branch_id and str(b.parent_branch_id) in branch_map:
            branch_map[str(b.parent_branch_id)]["children"].append(b_data)
        else:
            tree.append(b_data)

    return {"branches": tree, "total": len(branches)}


@router.post("/")
async def create_branch(
    data: BranchCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Создать новую ветку."""
    project = await db.get(Project, uuid.UUID(data.project_id))
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Проект не найден")

    parent_uuid = uuid.UUID(data.parent_branch_id) if data.parent_branch_id else None
    if parent_uuid:
        parent = await db.get(Branch, parent_uuid)
        if not parent or parent.project_id != project.id:
            raise HTTPException(status_code=400, detail="Родительская ветка не найдена")

    # Определяем порядковый номер
    result = await db.execute(
        select(Branch).where(
            Branch.project_id == project.id,
            Branch.parent_branch_id == parent_uuid,
        )
    )
    siblings = len(result.scalars().all())

    branch = Branch(
        project_id=project.id,
        name=data.name,
        description=data.description,
        color=data.color,
        parent_branch_id=parent_uuid,
        order_index=siblings,
    )
    db.add(branch)
    await db.flush()
    await db.refresh(branch)

    return {
        "id": str(branch.id),
        "name": branch.name,
        "description": branch.description,
        "color": branch.color,
        "parent_branch_id": str(branch.parent_branch_id) if branch.parent_branch_id else None,
        "order_index": branch.order_index,
        "created_at": branch.created_at.isoformat(),
    }


@router.get("/{branch_id}")
async def get_branch(
    branch_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Получить детали ветки."""
    branch = await db.get(Branch, uuid.UUID(branch_id))
    if not branch:
        raise HTTPException(status_code=404, detail="Ветка не найдена")

    project = await db.get(Project, branch.project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нет доступа")

    # Считаем заметки и сканы
    notes_result = await db.execute(
        select(BranchNote).where(BranchNote.branch_id == branch.id)
    )
    notes = notes_result.scalars().all()

    return {
        "id": str(branch.id),
        "project_id": str(branch.project_id),
        "name": branch.name,
        "description": branch.description,
        "color": branch.color,
        "parent_branch_id": str(branch.parent_branch_id) if branch.parent_branch_id else None,
        "order_index": branch.order_index,
        "is_archived": branch.is_archived,
        "is_default": branch.is_default,
        "targets": branch.targets,
        "config": branch.config,
        "tags": branch.tags,
        "notes_count": len(notes),
        "notes": [
            {
                "id": str(n.id),
                "title": n.title,
                "content": n.content[:200],
                "note_type": n.note_type,
                "created_at": n.created_at.isoformat(),
            }
            for n in notes[:50]
        ],
        "created_at": branch.created_at.isoformat(),
        "updated_at": branch.updated_at.isoformat(),
    }


@router.patch("/{branch_id}")
async def update_branch(
    branch_id: str,
    data: BranchUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Обновить ветку."""
    branch = await db.get(Branch, uuid.UUID(branch_id))
    if not branch:
        raise HTTPException(status_code=404, detail="Ветка не найдена")

    project = await db.get(Project, branch.project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нет доступа")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(branch, field, value)

    await db.flush()
    return {"status": "ok", "id": str(branch.id)}


@router.patch("/{branch_id}/move")
async def move_branch(
    branch_id: str,
    data: BranchMove,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Переместить ветку в дереве."""
    branch = await db.get(Branch, uuid.UUID(branch_id))
    if not branch:
        raise HTTPException(status_code=404, detail="Ветка не найдена")

    project = await db.get(Project, branch.project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нет доступа")

    if data.new_parent_id is not None:
        if data.new_parent_id == "":
            branch.parent_branch_id = None
        else:
            new_parent = await db.get(Branch, uuid.UUID(data.new_parent_id))
            if not new_parent or new_parent.project_id != project.id:
                raise HTTPException(status_code=400, detail="Новая родительская ветка не найдена")
            branch.parent_branch_id = new_parent.id

    if data.order_index is not None:
        branch.order_index = data.order_index

    await db.flush()
    return {"status": "ok", "id": str(branch.id)}


@router.delete("/{branch_id}")
async def delete_branch(
    branch_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Удалить ветку и всё содержимое."""
    branch = await db.get(Branch, uuid.UUID(branch_id))
    if not branch:
        raise HTTPException(status_code=404, detail="Ветка не найдена")

    project = await db.get(Project, branch.project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нет доступа")

    await db.delete(branch)
    await db.flush()
    return {"status": "deleted", "id": branch_id}


@router.post("/{branch_id}/notes")
async def add_note(
    branch_id: str,
    data: NoteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Добавить заметку в ветку."""
    branch = await db.get(Branch, uuid.UUID(branch_id))
    if not branch:
        raise HTTPException(status_code=404, detail="Ветка не найдена")

    project = await db.get(Project, branch.project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нет доступа")

    note = BranchNote(
        branch_id=branch.id,
        title=data.title,
        content=data.content,
        note_type=data.note_type,
        attachments=data.attachments,
        position_x=data.position_x,
        position_y=data.position_y,
    )
    db.add(note)
    await db.flush()
    await db.refresh(note)

    return {
        "id": str(note.id),
        "branch_id": str(note.branch_id),
        "title": note.title,
        "note_type": note.note_type,
        "created_at": note.created_at.isoformat(),
    }


@router.get("/{branch_id}/notes")
async def list_notes(
    branch_id: str,
    note_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Получить все заметки ветки."""
    branch = await db.get(Branch, uuid.UUID(branch_id))
    if not branch:
        raise HTTPException(status_code=404, detail="Ветка не найдена")

    query = select(BranchNote).where(BranchNote.branch_id == branch.id)
    if note_type:
        query = query.where(BranchNote.note_type == note_type)
    query = query.order_by(BranchNote.created_at.desc())

    result = await db.execute(query)
    notes = result.scalars().all()

    return {
        "notes": [
            {
                "id": str(n.id),
                "title": n.title,
                "content": n.content,
                "note_type": n.note_type,
                "attachments": n.attachments,
                "position_x": n.position_x,
                "position_y": n.position_y,
                "created_at": n.created_at.isoformat(),
                "updated_at": n.updated_at.isoformat(),
            }
            for n in notes
        ],
        "total": len(notes),
    }


@router.patch("/{branch_id}/notes/{note_id}")
async def update_note(
    branch_id: str,
    note_id: str,
    data: NoteUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Обновить заметку."""
    note = await db.get(BranchNote, uuid.UUID(note_id))
    if not note or str(note.branch_id) != branch_id:
        raise HTTPException(status_code=404, detail="Заметка не найдена")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(note, field, value)

    await db.flush()
    return {"status": "ok", "id": str(note.id)}


@router.delete("/{branch_id}/notes/{note_id}")
async def delete_note(
    branch_id: str,
    note_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Удалить заметку."""
    note = await db.get(BranchNote, uuid.UUID(note_id))
    if not note or str(note.branch_id) != branch_id:
        raise HTTPException(status_code=404, detail="Заметка не найдена")

    await db.delete(note)
    await db.flush()
    return {"status": "deleted", "id": note_id}
