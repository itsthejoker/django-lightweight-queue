from abc import ABCMeta, abstractmethod
from typing import Tuple, Optional

from ..job import Job
from ..types import QueueName, WorkerNumber
from ..progress_logger import ProgressLogger, NULL_PROGRESS_LOGGER


class BaseBackend(metaclass=ABCMeta):
    def startup(self, queue: QueueName) -> None:
        pass

    @abstractmethod
    def enqueue(self, job: Job, queue: QueueName) -> None:
        raise NotImplementedError()

    @abstractmethod
    def dequeue(self, queue: QueueName, worker_num: WorkerNumber, timeout: int) -> Optional[Job]:
        raise NotImplementedError()

    @abstractmethod
    def length(self, queue: QueueName) -> int:
        raise NotImplementedError()

    def processed_job(self, queue: QueueName, worker_num: WorkerNumber, job: Job) -> None:
        pass


class BackendWithDeduplicate(BaseBackend, metaclass=ABCMeta):
    @abstractmethod
    def deduplicate(
        self,
        queue: QueueName,
        *,
        progress_logger: ProgressLogger = NULL_PROGRESS_LOGGER
    ) -> Tuple[int, int]:
        pass
