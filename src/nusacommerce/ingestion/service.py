"""Fixed-window extraction, shared run lock, atomic publication and backfill."""
import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from .models import ExtractionWindow
from .repository import OrderIngestionRepository

logger = logging.getLogger(__name__)


class IncrementalOrderIngestion:
    def __init__(self, repository: OrderIngestionRepository, *,
                 pipeline_name="orders_incremental",
                 initial_start=datetime(2026,1,1,tzinfo=timezone.utc),
                 lookback=timedelta(minutes=15), page_size=1000):
        if page_size < 1 or lookback < timedelta(0):
            raise ValueError("Invalid page size or lookback")
        ExtractionWindow(initial_start,initial_start)
        self.repository, self.pipeline_name = repository, pipeline_name
        self.initial_start, self.lookback, self.page_size = initial_start, lookback, page_size

    def run(self, safe_cutoff):
        ExtractionWindow(safe_cutoff,safe_cutoff)
        with self.repository.pipeline_lock(self.pipeline_name):
            checkpoint = self.repository.load_checkpoint(self.pipeline_name)
            if checkpoint is not None and safe_cutoff < checkpoint:
                raise ValueError("Safe cutoff cannot move backwards; use backfill")
            start = self.initial_start if checkpoint is None else max(
                self.initial_start,checkpoint-self.lookback)
            return self._run_window(ExtractionWindow(start,safe_cutoff), advance=True)

    def backfill(self, start, end):
        with self.repository.pipeline_lock(self.pipeline_name):
            return self._run_window(ExtractionWindow(start,end), advance=False)

    def _run_window(self, window, *, advance):
        run_id = uuid4()
        self.repository.create_run(run_id,self.pipeline_name,window)
        extracted = 0
        cursor_time = cursor_id = None
        try:
            while True:
                page = self.repository.fetch_order_page(window,self.page_size,cursor_time,cursor_id)
                if page.empty:
                    break
                extracted += self.repository.stage_page(run_id,page)
                last = page.iloc[-1]
                cursor_time = last["updated_at"].to_pydatetime()
                cursor_id = last["order_id"]
            inserted = self.repository.finalize_run(
                run_id,self.pipeline_name,window,extracted,advance_checkpoint=advance)
        except Exception as exc:
            try:
                self.repository.mark_run_failed(run_id,extracted,type(exc).__name__)
            except Exception:
                logger.error("failure_status_unavailable run_id=%s",run_id)
            logger.error("ingestion_failed run_id=%s code=%s",run_id,type(exc).__name__)
            raise
        logger.info("ingestion_succeeded run_id=%s extracted=%s inserted=%s",run_id,extracted,inserted)
        return {"pipeline": self.pipeline_name,"run_id":str(run_id),
                "window_start":window.start.isoformat(),"window_end":window.end.isoformat(),
                "status":"succeeded","extracted":extracted,"inserted":inserted,
                "duplicates":extracted-inserted,"checkpoint_advanced":advance}
