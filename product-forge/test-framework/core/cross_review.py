"""
Cross Review - Cross-agent code review and feedback system.

Phase 1.4 (CRITICAL): Quality assurance through cross-agent review.
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, asdict, field
from enum import Enum


class ReviewStatus(str, Enum):
    """Status of a review request."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class FeedbackSeverity(str, Enum):
    """Severity of feedback."""
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    NIT = "nit"


@dataclass
class ReviewRequest:
    """A review request from one agent to another."""
    id: str
    project: str
    target_agent: str
    reviewer_agent: str
    stage: int
    artifact: str  # Path to the artifact being reviewed
    status: str = ReviewStatus.PENDING.value
    created_at: str = ""
    completed_at: Optional[str] = None
    verdict: Optional[str] = None  # approved, changes_required, rejected
    feedback_ids: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()


@dataclass
class Feedback:
    """Feedback from a reviewer."""
    id: str
    review_id: str
    severity: str
    category: str
    message: str
    addressed: bool = False
    addressed_by: Optional[str] = None
    addressed_at: Optional[str] = None
    response: Optional[str] = None
    created_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()


class CrossReviewManager:
    """Manages cross-agent reviews and feedback."""
    
    REVIEWS_DIR = "reviews"
    
    # Auto-review mappings: which agents review which
    AUTO_REVIEW_MAPPINGS = {
        "implement": ["code-review", "security"],
        "design": ["architect", "product-analyzer"],
        "architect": ["design", "code-review"],
        "validate": ["implement", "fix"],
    }
    
    # Severity weights for quality score
    SEVERITY_WEIGHTS = {
        FeedbackSeverity.CRITICAL.value: 20,
        FeedbackSeverity.MAJOR.value: 10,
        FeedbackSeverity.MINOR.value: 3,
        FeedbackSeverity.NIT.value: 1,
    }
    
    def __init__(self, project: str, products_dir: str = "products"):
        self.project = project
        self.products_dir = Path(products_dir)
        self.reviews_dir = self.products_dir / project / self.REVIEWS_DIR
        self.reviews_dir.mkdir(parents=True, exist_ok=True)
        # Canonical store (owned by core/cross_review.py): one file holds reviews + feedback.
        self.canonical_file = self.reviews_dir / "cross-reviews.json"
        # Legacy names kept only for one-time migration of pre-existing files.
        self.reviews_file = self.reviews_dir / "reviews.json"
        self.feedback_file = self.reviews_dir / "feedback.json"
        self._migrate_legacy()

    # ---- canonical store (single file: reviews + feedback) ----
    def _empty(self) -> dict:
        return {"$schema": "cross-review-v1", "version": "1.0.0",
                "review_requests": [], "feedback": [], "summary": {}, "metadata": {}}

    def _load_canonical(self) -> dict:
        try:
            return json.loads(self.canonical_file.read_text())
        except (json.JSONDecodeError, OSError):
            return self._empty()

    def _save_canonical(self, data: dict) -> None:
        self.canonical_file.parent.mkdir(parents=True, exist_ok=True)
        self.canonical_file.write_text(json.dumps(data, indent=2, default=str))

    def _migrate_legacy(self) -> None:
        """Merge legacy reviews.json + feedback.json into the canonical file once."""
        if self.canonical_file.exists():
            return
        try:
            rev = json.loads(self.reviews_file.read_text()).get("reviews", []) if self.reviews_file.exists() else []
            fb = json.loads(self.feedback_file.read_text()).get("feedback", []) if self.feedback_file.exists() else []
            if rev or fb:
                data = self._empty()
                data["review_requests"] = rev
                data["feedback"] = fb
                data["metadata"] = {"migrated_from": ["reviews.json", "feedback.json"]}
                self._save_canonical(data)
                for legacy in (self.reviews_file, self.feedback_file):
                    try:
                        legacy.rename(legacy.with_suffix(legacy.suffix + ".migrated"))
                    except OSError:
                        pass
        except Exception:
            pass

    def _load_reviews(self) -> dict:
        return {"reviews": self._load_canonical().get("review_requests", [])}

    def _save_reviews(self, data: dict) -> None:
        d = self._load_canonical()
        d["review_requests"] = data.get("reviews", [])
        self._save_canonical(d)

    def _load_feedback(self) -> dict:
        return {"feedback": self._load_canonical().get("feedback", [])}

    def _save_feedback(self, data: dict) -> None:
        d = self._load_canonical()
        d["feedback"] = data.get("feedback", [])
        self._save_canonical(d)
    
    def request_review(
        self,
        target_agent: str,
        reviewer_agent: str,
        stage: int,
        artifact: str,
        metadata: Optional[dict] = None,
    ) -> ReviewRequest:
        """Request a review from one agent to another."""
        review_id = f"rev_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
        
        request = ReviewRequest(
            id=review_id,
            project=self.project,
            target_agent=target_agent,
            reviewer_agent=reviewer_agent,
            stage=stage,
            artifact=artifact,
            metadata=metadata or {},
        )
        
        data = self._load_reviews()
        data["reviews"].append(asdict(request))
        self._save_reviews(data)
        
        return request
    
    def request_auto_reviews(
        self,
        target_agent: str,
        stage: int,
        artifact: str,
    ) -> list[ReviewRequest]:
        """Request automatic reviews based on standard mappings."""
        reviewers = self.AUTO_REVIEW_MAPPINGS.get(target_agent, ["code-review"])
        
        requests = []
        for reviewer in reviewers:
            request = self.request_review(target_agent, reviewer, stage, artifact)
            requests.append(request)
        
        return requests
    
    def get_review(self, review_id: str) -> Optional[ReviewRequest]:
        """Get a review by ID."""
        data = self._load_reviews()
        
        for r in data["reviews"]:
            if r["id"] == review_id:
                return ReviewRequest(**r)
        
        return None
    
    def list_reviews(self, status: Optional[str] = None, target_agent: Optional[str] = None) -> list[ReviewRequest]:
        """List reviews with optional filters."""
        data = self._load_reviews()
        reviews = data["reviews"]
        
        if status:
            reviews = [r for r in reviews if r["status"] == status]
        if target_agent:
            reviews = [r for r in reviews if r["target_agent"] == target_agent]
        
        return [ReviewRequest(**r) for r in reviews]
    
    def update_review_status(
        self,
        review_id: str,
        status: str,
        verdict: Optional[str] = None,
    ) -> bool:
        """Update review status."""
        data = self._load_reviews()
        
        for r in data["reviews"]:
            if r["id"] == review_id:
                r["status"] = status
                if verdict:
                    r["verdict"] = verdict
                if status == ReviewStatus.COMPLETED.value:
                    r["completed_at"] = datetime.utcnow().isoformat()
                self._save_reviews(data)
                return True
        
        return False
    
    def add_feedback(
        self,
        review_id: str,
        severity: str,
        category: str,
        message: str,
    ) -> Feedback:
        """Add feedback to a review."""
        feedback_id = f"fb_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
        
        feedback = Feedback(
            id=feedback_id,
            review_id=review_id,
            severity=severity,
            category=category,
            message=message,
        )
        
        # Link to review
        data = self._load_reviews()
        for r in data["reviews"]:
            if r["id"] == review_id:
                r["feedback_ids"].append(feedback_id)
                break
        self._save_reviews(data)
        
        # Save feedback
        fb_data = self._load_feedback()
        fb_data["feedback"].append(asdict(feedback))
        self._save_feedback(fb_data)
        
        return feedback
    
    def address_feedback(
        self,
        feedback_id: str,
        addressed_by: str,
        response: Optional[str] = None,
    ) -> bool:
        """Mark feedback as addressed."""
        fb_data = self._load_feedback()
        
        for fb in fb_data["feedback"]:
            if fb["id"] == feedback_id:
                fb["addressed"] = True
                fb["addressed_by"] = addressed_by
                fb["addressed_at"] = datetime.utcnow().isoformat()
                if response:
                    fb["response"] = response
                self._save_feedback(fb_data)
                return True
        
        return False
    
    def get_open_feedback(self) -> list[Feedback]:
        """Get all open (unaddressed) feedback."""
        fb_data = self._load_feedback()
        return [
            Feedback(**fb) for fb in fb_data["feedback"]
            if not fb.get("addressed", False)
        ]
    
    def get_feedback_for_review(self, review_id: str) -> list[Feedback]:
        """Get all feedback for a specific review."""
        fb_data = self._load_feedback()
        return [
            Feedback(**fb) for fb in fb_data["feedback"]
            if fb.get("review_id") == review_id
        ]
    
    def get_review_metrics(self) -> dict:
        """Get review metrics for the project."""
        reviews = self.list_reviews()
        fb_data = self._load_feedback()
        all_feedback = [Feedback(**fb) for fb in fb_data["feedback"]]
        
        total = len(reviews)
        completed = sum(1 for r in reviews if r.status == ReviewStatus.COMPLETED.value)
        approved = sum(1 for r in reviews if r.verdict == "approved")
        changes_required = sum(1 for r in reviews if r.verdict == "changes_required")
        rejected = sum(1 for r in reviews if r.verdict == "rejected")
        
        return {
            "total_reviews": total,
            "completed": completed,
            "pending": total - completed,
            "approved": approved,
            "changes_required": changes_required,
            "rejected": rejected,
            "total_feedback": len(all_feedback),
            "open_feedback": len([f for f in all_feedback if not f.addressed]),
            "by_severity": self._count_by_field(all_feedback, "severity"),
            "by_category": self._count_by_field(all_feedback, "category"),
        }
    
    def get_agent_quality_score(self, agent: str) -> dict:
        """Calculate quality score for an agent based on feedback."""
        reviews = self.list_reviews(target_agent=agent)
        total_penalty = 0
        
        for review in reviews:
            feedback_list = self.get_feedback_for_review(review.id)
            for fb in feedback_list:
                if not fb.addressed:
                    total_penalty += self.SEVERITY_WEIGHTS.get(fb.severity, 0)
        
        # Start at 100, deduct penalties
        quality_score = max(0, 100 - total_penalty)
        
        return {
            "agent": agent,
            "quality_score": quality_score,
            "total_reviews": len(reviews),
            "open_feedback_count": sum(
                len([f for f in self.get_feedback_for_review(r.id) if not f.addressed])
                for r in reviews
            ),
        }
    
    def _count_by_field(self, items: list, field: str) -> dict:
        """Count items grouped by a field."""
        counts = {}
        for item in items:
            value = getattr(item, field, "unknown")
            counts[value] = counts.get(value, 0) + 1
        return counts
