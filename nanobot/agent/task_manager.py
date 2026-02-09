"""
Task Manager - Persistent task storage and management
"""
import json
from pathlib import Path
from typing import Any, Optional
from datetime import datetime
from loguru import logger


class Task:
    """Represents a named task that can be executed on-demand or scheduled."""
    
    def __init__(
        self,
        name: str,
        description: str,
        command: str,
        created_at: Optional[str] = None,
    ):
        self.name = name
        self.description = description
        self.command = command
        self.created_at = created_at or datetime.now().isoformat()
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "command": self.command,
            "created_at": self.created_at,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Task":
        return cls(
            name=data["name"],
            description=data["description"],
            command=data["command"],
            created_at=data.get("created_at"),
        )


class TaskManager:
    """Manages persistent tasks with CRUD operations."""
    
    def __init__(self, storage_path: Path):
        self.storage_path = storage_path
        self.tasks: dict[str, Task] = {}
        self._load()
    
    def _load(self) -> None:
        """Load tasks from storage."""
        if not self.storage_path.exists():
            logger.info(f"Task storage not found, creating new: {self.storage_path}")
            self._save()
            return
        
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.tasks = {
                    name: Task.from_dict(task_data)
                    for name, task_data in data.get("tasks", {}).items()
                }
            logger.info(f"Loaded {len(self.tasks)} tasks from {self.storage_path}")
        except Exception as e:
            logger.error(f"Failed to load tasks: {e}")
            self.tasks = {}
    
    def _save(self) -> None:
        """Save tasks to storage."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "tasks": {
                    name: task.to_dict()
                    for name, task in self.tasks.items()
                }
            }
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.debug(f"Saved {len(self.tasks)} tasks to {self.storage_path}")
        except Exception as e:
            logger.error(f"Failed to save tasks: {e}")
    
    def create(self, name: str, description: str, command: str) -> Task:
        """Create a new task."""
        if name in self.tasks:
            raise ValueError(f"Task '{name}' already exists")
        
        task = Task(name=name, description=description, command=command)
        self.tasks[name] = task
        self._save()
        logger.info(f"Created task: {name}")
        return task
    
    def get(self, name: str) -> Optional[Task]:
        """Get a task by name."""
        return self.tasks.get(name)
    
    def list(self) -> list[Task]:
        """List all tasks."""
        return list(self.tasks.values())
    
    def delete(self, name: str) -> bool:
        """Delete a task by name."""
        if name not in self.tasks:
            return False
        
        del self.tasks[name]
        self._save()
        logger.info(f"Deleted task: {name}")
        return True
    
    def update(self, name: str, description: Optional[str] = None, command: Optional[str] = None) -> bool:
        """Update a task."""
        task = self.tasks.get(name)
        if not task:
            return False
        
        if description is not None:
            task.description = description
        if command is not None:
            task.command = command
        
        self._save()
        logger.info(f"Updated task: {name}")
        return True
