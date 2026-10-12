from __future__ import annotations

from dataclasses import dataclass

from .catalog import LearningCatalog
from .config import Settings
from .knowledge import KnowledgeStore
from .memory import MistakeMemory
from .platform_service import LearningPlatform
from .platform_store import PlatformStore
from .sandbox import CppRunner, build_cpp_runner


@dataclass(slots=True)
class AppServices:
    settings: Settings
    knowledge: KnowledgeStore
    memory: MistakeMemory
    runner: CppRunner
    platform: LearningPlatform

    @classmethod
    def create(cls, settings: Settings) -> AppServices:
        settings.ensure_directories()
        knowledge = KnowledgeStore(settings.database_path)
        memory = MistakeMemory(settings.database_path)
        knowledge.initialize()
        memory.initialize()
        knowledge.bootstrap(settings.knowledge_dir)
        runner = build_cpp_runner(settings)
        store = PlatformStore(settings.database_path)
        store.initialize()
        return cls(
            settings=settings,
            knowledge=knowledge,
            memory=memory,
            runner=runner,
            platform=LearningPlatform(
                store, LearningCatalog(settings.project_root / "content"), runner
            ),
        )
