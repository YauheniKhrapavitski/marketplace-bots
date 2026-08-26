from app.config import Settings
from app.workers.scheduler import create_scheduler


def test_scheduler_can_run_questions_without_wb_feedbacks() -> None:
    scheduler = create_scheduler(
        Settings(
            telegram_admin_ids="1",
            app_encryption_key="x" * 32,
            feedback_scheduler_enabled=False,
            question_scheduler_enabled=True,
        )
    )

    job_ids = {job.id for job in scheduler.get_jobs()}

    assert "question_sync" in job_ids
    assert "feedback_sync" not in job_ids


def test_scheduler_does_not_run_questions_when_feedbacks_are_enabled() -> None:
    scheduler = create_scheduler(
        Settings(
            telegram_admin_ids="1",
            app_encryption_key="x" * 32,
            feedback_scheduler_enabled=True,
            question_scheduler_enabled=True,
        )
    )

    job_ids = {job.id for job in scheduler.get_jobs()}

    assert "feedback_sync" in job_ids
    assert "question_sync" not in job_ids
